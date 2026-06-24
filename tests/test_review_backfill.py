import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.services import reviews as review_service
from mobguard_platform import AnalysisStore, PlatformStore


class ReviewBackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-review-backfill-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "settings": {
                        "review_ui_base_url": "https://mobguard.example.com",
                        "remnawave_api_url": "https://panel.example.com",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.store.sync_runtime_config(json.loads(self.config_path.read_text(encoding="utf-8")))
        self.container = SimpleNamespace(
            runtime=SimpleNamespace(
                env_path=self.root / ".env",
                config=json.loads(self.config_path.read_text(encoding="utf-8")),
            ),
            store=self.store,
            analysis_store=self.analysis_store,
        )

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
                    None,
                    None,
                    211,
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
                    "node-a:unknown:1.2.3.4:TAG",
                    "OPEN",
                    "unsure",
                    "node-a",
                    "Node A",
                    None,
                    None,
                    211,
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
            conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-04-12T10:05:00",
                    "node-a",
                    "Node A",
                    None,
                    None,
                    211,
                    None,
                    "1.2.3.5",
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
            second_event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id,
                    ip, tag, verdict, confidence_band, score, isp, asn, punitive_eligible,
                    latest_event_id, repeat_count, reason_codes_json, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "node-a:unknown:1.2.3.5:TAG",
                    "OPEN",
                    "unsure",
                    "node-a",
                    "Node A",
                    None,
                    None,
                    211,
                    None,
                    "1.2.3.5",
                    "TAG",
                    "UNSURE",
                    "UNSURE",
                    0,
                    "ISP",
                    None,
                    0,
                    second_event_id,
                    1,
                    "[]",
                    "2026-04-12T10:05:00",
                    "2026-04-12T10:06:00",
                ),
            )
            conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detail_uses_persisted_snapshot_without_remote_identity_backfill(self):
        listing = review_service.list_reviews(self.container, {"page": 1, "page_size": 25, "status": "OPEN"})
        detail = review_service.get_review(self.container, 1)

        self.assertIsNone(listing["items"][0]["username"])
        self.assertIsNone(listing["items"][0]["uuid"])
        self.assertIsNone(listing["items"][0]["telegram_id"])
        self.assertIn("usage_profile", detail)
        self.assertIsNotNone(detail["usage_profile"])
        self.assertIsNone(detail["username"])
        self.assertIsNone(detail["uuid"])
        self.assertIsNone(detail["telegram_id"])

    def test_scope_backfill_rebuilds_subject_ip_context_and_drops_stale_usage_snapshots(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO read_model_snapshots (snapshot_type, scope_key, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "review_usage_profile",
                    "1",
                    json.dumps({"usage_profile_summary": "stale snapshot"}, ensure_ascii=False),
                    "2026-04-12T10:00:00",
                ),
            )
            conn.execute(
                """
                UPDATE review_cases
                SET usage_profile_summary = ?, usage_profile_soft_reasons_json = ?
                WHERE id = ?
                """,
                ("stale summary", '["stale_reason"]', 1),
            )
            conn.commit()

        summary = self.store.run_review_scope_backfill(force=True)
        with self.store._connect() as conn:
            snapshot_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM read_model_snapshots WHERE snapshot_type = ?",
                ("review_usage_profile",),
            ).fetchone()["cnt"]
        listing = review_service.list_reviews(self.container, {"page": 1, "page_size": 25, "status": "OPEN"})
        detail = review_service.get_review(self.container, 1)

        self.assertTrue(summary["ran"])
        self.assertGreaterEqual(summary["recomputed_cases"], 1)
        self.assertGreaterEqual(summary["deleted_usage_snapshots"], 1)
        self.assertEqual(listing["items"][0]["target_scope_type"], "subject_ip")
        self.assertEqual(
            {entry["ip"] for entry in detail["same_device_ip_history"]},
            {"1.2.3.4", "1.2.3.5"},
        )
        self.assertNotEqual(detail["usage_profile_summary"], "stale summary")
        self.assertEqual(snapshot_count, 0)

    def test_enrich_usage_profile_merges_cached_snapshot(self):
        from unittest.mock import patch

        # 1. Setup a cached snapshot in the DB for case 1
        cached_burst = {
            "source": "traffic_bytes",
            "bytes": 20000000000,
            "min_bytes": 10000000000,
            "bytes_text": "20.0 GB",
            "min_bytes_text": "10.0 GB",
            "window_minutes": 60,
        }
        cached_devices = [
            {"device_id": "dev-1", "label": "Device 1", "os_family": "iOS", "ip": "1.1.1.1"}
        ]

        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO read_model_snapshots (snapshot_type, scope_key, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "review_usage_profile",
                    "1",
                    json.dumps({
                        "traffic_burst": cached_burst,
                        "devices": cached_devices,
                        "hwid_device_limit": 1,
                        "hwid_device_count_exact": 2,
                    }, ensure_ascii=False),
                    "2026-04-12T10:00:00",
                ),
            )
            conn.commit()

        # 2. Mock panel_client to return a mock client with dummy user data
        mock_user_data = {
            "uuid": "user-uuid",
            "username": "user-name",
            "telegramId": 123456,
            "trafficLimitBytes": 10000000000,
        }

        with patch("api.services.reviews.panel_client") as mock_panel_client:
            mock_client = mock_panel_client.return_value
            mock_client.get_user_data.return_value = mock_user_data

            # Call list_reviews which in turn calls _enrich_review_usage_profile
            listing = review_service.list_reviews(self.container, {"page": 1, "page_size": 25, "status": "OPEN"})

            # Verify that the usage_profile has the merged traffic burst and device list
            item = next(it for it in listing["items"] if it["id"] == 1)
            self.assertIn("usage_profile", item)
            up = item["usage_profile"]
            self.assertIsNotNone(up)

            # Check traffic burst is merged
            self.assertEqual(up["traffic_burst"]["bytes"], 20000000000)
            self.assertIn("traffic_burst", up["soft_reasons"])

            # Check devices list is merged
            self.assertEqual(len(up["devices"]), 1)
            self.assertEqual(up["devices"][0]["device_id"], "dev-1")
            self.assertEqual(up["devices"][0]["ip"], "1.1.1.1")
            self.assertEqual(up["hwid_device_limit"], 1)
            self.assertEqual(up["hwid_device_count_exact"], 2)


if __name__ == "__main__":
    unittest.main()
