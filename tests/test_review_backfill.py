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


if __name__ == "__main__":
    unittest.main()
