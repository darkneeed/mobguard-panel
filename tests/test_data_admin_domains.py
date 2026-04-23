import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.services import data_admin as data_admin_service
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


if __name__ == "__main__":
    unittest.main()
