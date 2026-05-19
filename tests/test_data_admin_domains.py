import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.services import data_admin as data_admin_service
from api.services import decisions as decisions_service
from mobguard_platform import AnalysisStore, DecisionBundle, PlatformStore


class DataAdminDomainTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-data-admin-domains-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(json.dumps({"settings": {}}, ensure_ascii=False), encoding="utf-8")
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.container = SimpleNamespace(
            store=self.store,
            analysis_store=self.analysis_store,
            runtime=SimpleNamespace(config={"settings": {}}),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_overrides_and_cache_facade_return_expected_payloads(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO exact_ip_overrides (
                    ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("1.2.3.4", "HOME", "review_resolution", "admin", 1001, "2026-04-12T00:00:00", "2026-04-12T00:00:00", None),
            )
            conn.execute(
                """
                INSERT INTO unsure_patterns (ip_pattern, decision, timestamp)
                VALUES (?, ?, ?)
                """,
                ("1.2.3.*", "MOBILE", "2026-04-12T00:00:00"),
            )
            conn.execute(
                """
                INSERT INTO ip_decisions (ip, status, confidence, details, asn, expires, log_json, bundle_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("1.2.3.4", "HOME", "HIGH_HOME", "ISP", 12345, "2026-04-20T00:00:00", "[]", "{}"),
            )
            conn.commit()

        overrides = data_admin_service.list_overrides(self.container)
        cache = data_admin_service.list_cache(self.container)

        self.assertEqual(overrides["exact_ip"][0]["ip"], "1.2.3.4")
        self.assertEqual(overrides["unsure_patterns"][0]["ip_pattern"], "1.2.3.*")
        self.assertEqual(cache["items"][0]["ip"], "1.2.3.4")

    def test_learning_facade_groups_provider_rows(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO unsure_learning (pattern_type, pattern_value, decision, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("provider", "mts", "HOME", 5, "2026-04-12T00:00:00"),
            )
            conn.execute(
                """
                INSERT INTO learning_patterns_active (
                    pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("provider_service", "mts:home", "HOME", 3, 1.0, "2026-04-12T00:00:00", "{}"),
            )
            conn.execute(
                """
                INSERT INTO learning_pattern_stats (
                    pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("provider", "mts", "HOME", 3, 3, 1.0, "2026-04-12T00:00:00", "{}"),
            )
            conn.commit()

        payload = data_admin_service.get_learning_admin(self.container)

        self.assertEqual(payload["legacy_provider"][0]["pattern_value"], "mts")
        self.assertEqual(payload["promoted_provider_service_active"][0]["pattern_value"], "mts:home")
        self.assertEqual(payload["promoted_provider_stats"][0]["pattern_value"], "mts")

    def test_analysis_events_facade_filters_and_links_review_cases(self):
        bundle = DecisionBundle(
            ip="1.2.3.4",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP A",
        )
        event_id = self.store.record_analysis_event(
            {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"},
            "1.2.3.4",
            "TAG-A",
            bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        self.store.ensure_review_case(
            {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"},
            "1.2.3.4",
            "TAG-A",
            bundle,
            event_id,
            "probable_home",
        )

        payload = data_admin_service.list_analysis_events(
            self.container,
            {"device_id": "dev-1", "has_review_case": True, "page": 1, "page_size": 50, "sort": "created_desc"},
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["client_device_id"], "dev-1")
        self.assertTrue(payload["items"][0]["has_review_case"])
        self.assertEqual(payload["items"][0]["review_case_status"], "OPEN")

    def test_analysis_events_facade_does_not_infer_shared_account_from_multiple_devices(self):
        bundle = DecisionBundle(
            ip="5.6.7.8",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP A",
        )
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "module_id": "node-a",
            "module_name": "Node A",
        }
        event_id = self.store.record_analysis_event(
            user,
            "5.6.7.8",
            "TAG-A",
            bundle,
            observation={"client_device_label": "Account context"},
        )
        self.store.ensure_review_case(user, "5.6.7.8", "TAG-A", bundle, event_id, "unsure")
        self.store.record_analysis_event(
            user,
            "5.6.7.9",
            "TAG-A",
            bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Phone 1"},
        )
        self.store.record_analysis_event(
            user,
            "5.6.7.10",
            "TAG-A",
            bundle,
            observation={"client_device_id": "dev-2", "client_device_label": "Phone 2"},
        )

        payload = data_admin_service.list_analysis_events(
            self.container,
            {"ip": "5.6.7.8", "page": 1, "page_size": 50, "sort": "created_desc"},
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["target_scope_type"], "subject_ip")
        self.assertFalse(payload["items"][0]["shared_account_suspected"])

    def test_auto_decisions_facade_excludes_review_cases_and_manual_overrides(self):
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "module_id": "node-a",
            "module_name": "Node A",
        }
        auto_bundle = DecisionBundle(
            ip="7.7.7.7",
            verdict="MOBILE",
            confidence_band="HIGH_MOBILE",
            score=74,
            asn=12345,
            isp="ISP A",
        )
        auto_event_id = self.store.record_analysis_event(
            user,
            "7.7.7.7",
            "TAG-A",
            auto_bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        manual_bundle = DecisionBundle(
            ip="7.7.7.8",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-90,
            asn=12345,
            isp="ISP B",
            source="manual_override",
        )
        self.store.record_analysis_event(user, "7.7.7.8", "TAG-A", manual_bundle)
        review_bundle = DecisionBundle(
            ip="7.7.7.9",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-18,
            asn=12345,
            isp="ISP C",
        )
        review_event_id = self.store.record_analysis_event(user, "7.7.7.9", "TAG-A", review_bundle)
        self.store.ensure_review_case(user, "7.7.7.9", "TAG-A", review_bundle, review_event_id, "probable_home")
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO enforcement_jobs (
                    job_key, event_uid, analysis_event_id, review_case_id, module_id, subject_uuid,
                    job_type, status, processing_owner, processing_started_at, attempt_count,
                    next_attempt_at, last_error, last_error_at, applied_at, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job:auto-1",
                    "evt-auto-1",
                    auto_event_id,
                    None,
                    "node-a",
                    "uuid-1",
                    "access_state",
                    "applied",
                    1,
                    "2026-04-12T12:00:00",
                    "",
                    "",
                    "2026-04-12T12:00:30",
                    json.dumps({"uuid": "uuid-1"}, ensure_ascii=False),
                    "2026-04-12T12:00:00",
                    "2026-04-12T12:00:30",
                ),
            )
            conn.commit()

        payload = decisions_service.list_decisions_auto(
            self.container,
            {"page": 1, "page_size": 50, "sort": "created_desc"},
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["ip"], "7.7.7.7")
        self.assertEqual(payload["items"][0]["decision_source"], "rule_engine")
        self.assertEqual(payload["items"][0]["enforcement_status"], "applied")
        self.assertEqual(payload["items"][0]["enforcement_job_type"], "access_state")

    def test_auto_decisions_facade_includes_events_after_review_case_is_closed(self):
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "module_id": "node-a",
            "module_name": "Node A",
        }
        bundle = DecisionBundle(
            ip="8.8.8.8",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-22,
            asn=12345,
            isp="ISP C",
        )
        self.store.record_analysis_event(user, "8.8.8.7", "TAG-A", bundle)
        review_event_id = self.store.record_analysis_event(user, "8.8.8.8", "TAG-A", bundle)
        review_case = self.store.ensure_review_case(
            user,
            "8.8.8.8",
            "TAG-A",
            bundle,
            review_event_id,
            "probable_home",
        )
        self.store.resolve_review_case(
            review_case.id,
            "MOBILE",
            "admin",
            1001,
            "close case for auto decisions",
        )

        payload = decisions_service.list_decisions_auto(
            self.container,
            {"page": 1, "page_size": 50, "sort": "created_desc"},
        )

        ips = {item["ip"] for item in payload["items"]}
        self.assertIn("8.8.8.7", ips)
        self.assertIn("8.8.8.8", ips)

    def test_console_facade_merges_system_logs_and_module_inputs(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_console_events (
                    service_name, logger_name, level, message, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "mobguard-api",
                    "api.services.ingest_pipeline",
                    "WARNING",
                    "Pipeline snapshot refresh skipped because SQLite is busy",
                    json.dumps({"lineno": 720}, ensure_ascii=False),
                    "2026-04-12T12:00:02",
                ),
            )
            conn.execute(
                """
                INSERT INTO ingested_raw_events (
                    event_uid, module_id, module_name, received_at, occurred_at, log_offset,
                    subject_uuid, username, system_id, telegram_id, ip, tag, raw_payload_json,
                    processing_state, processing_owner, processing_started_at, attempt_count,
                    next_attempt_at, last_error, last_error_at, processed_at, analysis_event_id, review_case_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt-1",
                    "node-a",
                    "Node A",
                    "2026-04-12T12:00:01",
                    "2026-04-12T12:00:00",
                    10,
                    "uuid-1",
                    "alice",
                    42,
                    "1001",
                    "1.2.3.4",
                    "TAG-A",
                    json.dumps({"ip": "1.2.3.4", "tag": "TAG-A"}, ensure_ascii=False),
                    "queued",
                    "",
                    "",
                    0,
                    "2026-04-12T12:00:01",
                    "",
                    "",
                    None,
                    None,
                    None,
                ),
            )
            conn.execute(
                """
                INSERT INTO modules (
                    module_id, module_name, token_hash, token_ciphertext, status, version, protocol_version,
                    config_revision_applied, first_seen_at, last_seen_at, install_state, managed,
                    health_status, error_text, last_validation_at, spool_depth, access_log_exists, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "node-a",
                    "Node A",
                    "hash",
                    "",
                    "online",
                    "1.0.0",
                    "v1",
                    3,
                    "2026-04-12T11:59:00",
                    "2026-04-12T12:00:00",
                    "online",
                    0,
                    "ok",
                    "",
                    "2026-04-12T12:00:00",
                    0,
                    1,
                    "{}",
                ),
            )
            conn.execute(
                """
                INSERT INTO module_heartbeats (
                    module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "node-a",
                    "online",
                    "1.0.0",
                    "v1",
                    3,
                    json.dumps({"health_status": "ok"}, ensure_ascii=False),
                    "2026-04-12T12:00:03",
                ),
            )
            conn.commit()

        payload = data_admin_service.list_console_entries(
            self.container,
            {"page": 1, "page_size": 10},
        )

        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["items"][0]["source"], "module_heartbeat")
        self.assertEqual(payload["items"][1]["source"], "system")
        self.assertEqual(payload["items"][2]["source"], "module_event")
        self.assertEqual(payload["source_counts"]["system"], 1)
        self.assertEqual(payload["source_counts"]["module_event"], 1)
        self.assertEqual(payload["source_counts"]["module_heartbeat"], 1)


if __name__ == "__main__":
    unittest.main()
