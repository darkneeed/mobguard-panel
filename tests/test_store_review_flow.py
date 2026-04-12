import os
import json
import shutil
import sqlite3
import tempfile
import unittest

from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore


class StoreReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-store-")
        self.db_path = os.path.join(self.temp_dir, "test.sqlite3")
        self.runtime_dir = os.path.join(self.temp_dir, "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.config_path = os.path.join(self.runtime_dir, "config.json")
        self.base_config = {
            "mixed_asns": [12345],
            "allowed_isp_keywords": ["mobile"],
            "home_isp_keywords": ["fiber"],
            "exclude_isp_keywords": ["hosting"],
            "provider_profiles": [
                {
                    "key": "mts",
                    "classification": "mixed",
                    "aliases": ["mts", "mgts"],
                    "mobile_markers": ["mobile", "lte"],
                    "home_markers": ["fiber", "gpon"],
                    "asns": [12345],
                }
            ],
            "admin_tg_ids": [1001],
            "exempt_tg_ids": [2002],
            "exempt_ids": [3003],
            "mobile_tags": ["TAG"],
            "settings": {
                "mobile_score_threshold": 55,
                "threshold_mobile": 60,
                "threshold_home": 15,
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "provider_mobile_marker_bonus": 18,
                "provider_home_marker_penalty": -18,
                "provider_conflict_review_only": True,
                "learning_promote_asn_min_support": 1,
                "learning_promote_asn_min_precision": 1.0,
                "learning_promote_combo_min_support": 1,
                "learning_promote_combo_min_precision": 1.0,
                "shadow_mode": True,
                "log_file": "/var/log/remnanode/access.log",
                "review_ui_base_url": "https://mobguard.example.com",
            },
        }
        self.store = PlatformStore(self.db_path, self.base_config, self.config_path)
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_review_roundtrip_creates_override_and_pattern(self):
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP",
        )
        bundle.add_reason(
            "keyword_home",
            "generic_keyword",
            -20,
            "soft",
            "HOME",
            "keyword matched",
            {"keywords": ["fiber"]},
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")
        resolved = self.store.resolve_review_case(summary.id, "HOME", "admin", 1001, "confirmed")

        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["system_id"], 42)
        self.assertEqual(resolved["latest_event"]["system_id"], 42)
        self.assertEqual(self.store.get_ip_override(bundle.ip), "HOME")
        pattern = self.store.get_promoted_pattern("asn", "12345")
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["decision"], "HOME")
        provider_pattern = self.store.get_promoted_pattern("provider", "mts")
        self.assertIsNotNone(provider_pattern)
        self.assertEqual(provider_pattern["decision"], "HOME")
        provider_service_pattern = self.store.get_promoted_pattern("provider_service", "mts:home")
        self.assertIsNotNone(provider_service_pattern)
        self.assertEqual(provider_service_pattern["decision"], "HOME")

    def test_live_rules_revision_conflict_is_rejected(self):
        state = self.store.get_live_rules_state()
        updated = self.store.update_live_rules(
            {"settings": {"threshold_mobile": 70}},
            "admin",
            1001,
            expected_revision=state["revision"],
            expected_updated_at=state["updated_at"],
        )
        self.assertEqual(updated["revision"], state["revision"] + 1)

        with self.assertRaises(ValueError):
            self.store.update_live_rules(
                {"settings": {"threshold_mobile": 80}},
                "admin",
                1001,
                expected_revision=state["revision"],
                expected_updated_at=state["updated_at"],
            )

        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["settings"]["threshold_mobile"], 70)
        self.assertEqual(payload["_meta"]["revision"], updated["revision"])
        self.assertEqual(payload["settings"]["log_file"], "/var/log/remnanode/access.log")
        self.assertEqual(payload["mobile_tags"], ["TAG"])
        self.assertEqual(payload["settings"]["db_file"], "runtime/bans.db")
        self.assertEqual(payload["settings"]["geoip_db"], "runtime/GeoLite2-ASN.mmdb")

    def test_legacy_threshold_alias_is_normalized_in_saved_rules(self):
        updated = self.store.update_live_rules(
            {"settings": {"mobile_score_threshold": 72}},
            "admin",
            1001,
        )

        self.assertEqual(updated["rules"]["settings"]["threshold_mobile"], 72)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["settings"]["threshold_mobile"], 72)
        self.assertNotIn("mobile_score_threshold", payload["settings"])

    def test_admin_and_exempt_lists_stay_separate(self):
        state = self.store.get_live_rules_state()

        self.assertEqual(state["rules"]["admin_tg_ids"], [1001])
        self.assertEqual(state["rules"]["exempt_tg_ids"], [2002])
        self.assertEqual(state["rules"]["exempt_ids"], [3003])
        self.assertEqual(state["rules"]["provider_profiles"][0]["key"], "mts")
        self.assertTrue(self.store.is_admin_tg_id(1001))
        self.assertFalse(self.store.is_admin_tg_id(2002))

    def test_provider_profiles_are_persisted_in_saved_rules(self):
        updated = self.store.update_live_rules(
            {
                "provider_profiles": [
                    {
                        "key": "rostelecom",
                        "classification": "mixed",
                        "aliases": ["rostelecom", "onlime"],
                        "mobile_markers": ["mobile", "lte"],
                        "home_markers": ["fiber", "gpon"],
                        "asns": [8359],
                    }
                ],
                "settings": {
                    "provider_mobile_marker_bonus": 20,
                    "provider_home_marker_penalty": -22,
                    "provider_conflict_review_only": True,
                },
            },
            "admin",
            1001,
        )
        self.assertEqual(updated["rules"]["provider_profiles"][0]["key"], "rostelecom")
        self.assertEqual(updated["rules"]["settings"]["provider_mobile_marker_bonus"], 20)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["provider_profiles"][0]["key"], "rostelecom")

    def test_list_review_cases_filters_by_dates_identifiers_and_repeat_count(self):
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        second_user = {"uuid": "uuid-2", "username": "bob", "telegramId": "2002", "id": 77}

        first_bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP-A",
        )
        second_bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=None,
            isp="ISP-B",
        )

        first_event = self.store.record_analysis_event(first_user, first_bundle.ip, "TAG", first_bundle)
        first_case = self.store.ensure_review_case(first_user, first_bundle.ip, "TAG", first_bundle, first_event, "probable_home")
        second_event = self.store.record_analysis_event(second_user, second_bundle.ip, "TAG", second_bundle)
        second_case = self.store.ensure_review_case(second_user, second_bundle.ip, "TAG", second_bundle, second_event, "unsure")

        with self.store._connect() as conn:
            conn.execute(
                "UPDATE review_cases SET opened_at = ?, repeat_count = ? WHERE id = ?",
                ("2026-04-01T10:00:00", 3, first_case.id),
            )
            conn.execute(
                "UPDATE review_cases SET opened_at = ?, repeat_count = ? WHERE id = ?",
                ("2026-04-03T09:00:00", 1, second_case.id),
            )
            conn.commit()

        filtered = self.store.list_review_cases(
            {
                "username": "ali",
                "system_id": 42,
                "telegram_id": "1001",
                "opened_from": "2026-04-01",
                "opened_to": "2026-04-01",
                "repeat_count_min": 2,
                "repeat_count_max": 4,
            }
        )

        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["items"][0]["id"], first_case.id)
        self.assertEqual(filtered["items"][0]["system_id"], 42)
        self.assertEqual(filtered["items"][0]["opened_at"], "2026-04-01T10:00:00")

    def test_quality_metrics_include_promoted_and_legacy_learning_state(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP",
        )
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")
        self.store.resolve_review_case(summary.id, "HOME", "admin", 1001, "confirmed")

        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO unsure_learning (pattern_type, pattern_value, decision, confidence, timestamp)
                VALUES ('asn', '12345', 'HOME', 7, '2026-04-01T10:00:00')
                """
            )
            conn.commit()

        metrics = self.store.get_quality_metrics()

        self.assertIn("learning", metrics)
        self.assertGreaterEqual(metrics["learning"]["promoted"]["active_patterns"], 1)
        self.assertEqual(metrics["learning"]["legacy"]["total_patterns"], 1)
        self.assertEqual(metrics["learning"]["legacy"]["total_confidence"], 7)
        self.assertEqual(metrics["learning"]["thresholds"]["asn_min_support"], 1)
        self.assertEqual(metrics["asn_source"]["type"], "missing")

    def test_quality_metrics_include_mixed_provider_conflict_rate(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-18,
            asn=12345,
            isp="MTS Fiber",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")

        metrics = self.store.get_quality_metrics()

        self.assertEqual(metrics["mixed_providers"]["open_cases"], 1)
        self.assertEqual(metrics["mixed_providers"]["conflict_cases"], 1)
        self.assertEqual(metrics["mixed_providers"]["top_open_cases"][0]["provider_key"], "mts")

    def test_build_review_url_falls_back_to_base_config_when_live_rules_are_empty(self):
        self.assertEqual(
            self.store.build_review_url(7),
            "https://mobguard.example.com/reviews/7",
        )

    def test_review_payload_normalizes_numeric_uuid_to_system_id_for_legacy_rows(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-04-12T10:00:00",
                    "node-a",
                    "Node A",
                    "215",
                    None,
                    None,
                    None,
                    "1.2.3.4",
                    "TAG",
                    "UNSURE",
                    "UNSURE",
                    0,
                    "ISP",
                    None,
                    0,
                    "[]",
                    "{}",
                    "{}",
                ),
            )
            event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id,
                    ip, tag, verdict, confidence_band, score, isp, asn, punitive_eligible,
                    latest_event_id, repeat_count, reason_codes_json, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy:215:1.2.3.4:TAG",
                    "OPEN",
                    "unsure",
                    "node-a",
                    "Node A",
                    "215",
                    None,
                    None,
                    None,
                    "1.2.3.4",
                    "TAG",
                    "UNSURE",
                    "UNSURE",
                    0,
                    "ISP",
                    None,
                    0,
                    event_id,
                    1,
                    "[]",
                    "2026-04-12T10:00:00",
                    "2026-04-12T10:01:00",
                ),
            )
            case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        detail = self.store.get_review_case(case_id)
        listing = self.store.list_review_cases({})

        self.assertIsNone(detail["uuid"])
        self.assertEqual(detail["system_id"], 215)
        self.assertEqual(listing["items"][0]["system_id"], 215)
        self.assertIsNone(listing["items"][0]["uuid"])

    def test_bootstrap_updated_by_is_normalized_to_system(self):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "admin_tg_ids": [1001],
                    "settings": {"threshold_mobile": 60},
                    "_meta": {"revision": 1, "updated_at": "", "updated_by": "bootstrap"},
                },
                handle,
                ensure_ascii=False,
            )
        state = self.store.get_live_rules_state()
        self.assertEqual(state["updated_by"], "system")

    def test_init_schema_migrates_legacy_tables_before_creating_system_id_indexes(self):
        legacy_db_path = os.path.join(self.temp_dir, "legacy.sqlite3")
        with sqlite3.connect(legacy_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    uuid TEXT,
                    username TEXT,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    punitive_eligible INTEGER NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL,
                    signal_flags_json TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE review_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    review_reason TEXT NOT NULL,
                    uuid TEXT,
                    username TEXT,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    latest_event_id INTEGER NOT NULL,
                    repeat_count INTEGER NOT NULL DEFAULT 1,
                    reason_codes_json TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE live_rules (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    rules_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE admin_sessions (
                    token TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE review_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE ip_decisions (
                    ip TEXT PRIMARY KEY,
                    status TEXT,
                    confidence TEXT,
                    details TEXT,
                    asn INTEGER,
                    expires TEXT,
                    log_json TEXT
                )
                """
            )
            conn.commit()

        legacy_store = PlatformStore(legacy_db_path, self.base_config, self.config_path)
        legacy_store.init_schema()

        with legacy_store._connect() as conn:
            analysis_columns = {row["name"] for row in conn.execute("PRAGMA table_info(analysis_events)").fetchall()}
            review_columns = {row["name"] for row in conn.execute("PRAGMA table_info(review_cases)").fetchall()}
            indexes = {
                row["name"] for row in conn.execute("PRAGMA index_list(review_cases)").fetchall()
            }

        self.assertIn("system_id", analysis_columns)
        self.assertIn("system_id", review_columns)
        self.assertIn("idx_review_cases_system_id", indexes)

    def test_health_snapshot_reflects_core_heartbeat(self):
        previous = os.environ.get("IPINFO_TOKEN")
        os.environ["IPINFO_TOKEN"] = "test-token"
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "ok")
            self.assertTrue(snapshot["core"]["healthy"])
            self.assertTrue(snapshot["ipinfo_token_present"])
        finally:
            if previous is None:
                os.environ.pop("IPINFO_TOKEN", None)
            else:
                os.environ["IPINFO_TOKEN"] = previous

    def test_health_snapshot_degrades_without_ipinfo_token(self):
        previous = os.environ.pop("IPINFO_TOKEN", None)
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "degraded")
            self.assertFalse(snapshot["ipinfo_token_present"])
        finally:
            if previous is not None:
                os.environ["IPINFO_TOKEN"] = previous


if __name__ == "__main__":
    unittest.main()
