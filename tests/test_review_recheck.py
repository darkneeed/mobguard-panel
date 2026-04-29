import asyncio
import json
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api.services import reviews as review_service
from mobguard_platform import AnalysisStore, DecisionBundle, PlatformStore


class ReviewRecheckTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-review-recheck-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "provider_profiles": [
                        {
                            "key": "mts",
                            "classification": "mixed",
                            "aliases": ["mts"],
                            "mobile_markers": ["lte", "mobile"],
                            "home_markers": ["fiber", "gpon"],
                            "asns": [12345],
                        }
                    ],
                    "settings": {
                        "review_ui_base_url": "https://mobguard.example.com",
                        "remnawave_api_url": "https://panel.example.com",
                        "provider_conflict_review_only": True,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, json.loads(self.config_path.read_text(encoding="utf-8")), str(self.config_path))
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

        bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=20,
            asn=12345,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "unknown",
            "service_conflict": False,
            "review_recommended": True,
        }
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recheck_reviews_auto_resolves_cases_without_remaining_review_reason(self):
        refreshed = DecisionBundle(
            ip="10.10.10.20",
            verdict="MOBILE",
            confidence_band="HIGH_MOBILE",
            score=72,
            asn=12345,
            isp="MTS",
        )
        refreshed.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "unknown",
            "service_conflict": False,
            "review_recommended": False,
        }
        refreshed.add_reason(
            "behavior_history_mobile",
            "behavior",
            40,
            "soft",
            "MOBILE",
            "Historical subnet rotation",
            {"subnet": "188.120.1", "distinct_ips": 9},
        )
        refreshed.add_reason(
            "learning_provider",
            "learning",
            6,
            "soft",
            "MOBILE",
            "Promoted provider pattern mts",
            {"pattern_type": "provider", "pattern_value": "mts", "support": 12, "precision": 1.0},
        )

        async def fake_analyze_event(*args, **kwargs):
            return refreshed

        with patch.object(review_service, "_analyze_event", side_effect=fake_analyze_event):
            payload = asyncio.run(
                review_service.recheck_reviews(
                    self.container,
                    {"limit": 10},
                    "system",
                    1001,
                )
            )

        self.assertEqual(payload["summary"]["processed"], 1)
        self.assertEqual(payload["summary"]["closed"], 1)
        self.assertEqual(payload["items"][0]["status"], "RESOLVED")
        detail = self.store.get_review_case(1)
        self.assertEqual(detail["status"], "RESOLVED")
        self.assertEqual(detail["verdict"], "MOBILE")
        self.assertEqual(detail["latest_event"]["verdict"], "MOBILE")
        self.assertEqual(self.store.get_ip_override(refreshed.ip), "MOBILE")

    def test_recheck_reviews_auto_resolves_stationary_home_and_sets_ip_override(self):
        refreshed = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-35,
            asn=12345,
            isp="MTS Fiber",
        )
        refreshed.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": False,
        }
        refreshed.add_reason(
            "behavior_history_home",
            "behavior",
            -25,
            "soft",
            "HOME",
            "Stable same IP over time",
            {"ip": "10.10.10.20", "sample_count": 5, "span_hours": 48},
        )
        refreshed.add_reason(
            "behavior_lifetime",
            "behavior",
            -10,
            "soft",
            "HOME",
            "Long session lifetime",
            {"lifetime_hours": 48},
        )

        async def fake_analyze_event(*args, **kwargs):
            return refreshed

        with patch.object(review_service, "_analyze_event", side_effect=fake_analyze_event):
            payload = asyncio.run(
                review_service.recheck_reviews(
                    self.container,
                    {"limit": 10},
                    "system",
                    1001,
                )
            )

        self.assertEqual(payload["summary"]["processed"], 1)
        self.assertEqual(payload["summary"]["closed"], 1)
        self.assertEqual(payload["items"][0]["status"], "RESOLVED")
        detail = self.store.get_review_case(1)
        self.assertEqual(detail["status"], "RESOLVED")
        self.assertEqual(detail["verdict"], "HOME")
        self.assertEqual(self.store.get_ip_override(refreshed.ip), "HOME")

    def test_provider_sensitive_recheck_skips_when_storage_is_busy(self):
        refreshed = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=20,
            asn=12345,
            isp="MTS",
        )

        with patch.object(review_service, "_analyze_event", new=AsyncMock(return_value=refreshed)), patch.object(
            self.store,
            "async_recheck_review_case",
            new=AsyncMock(side_effect=sqlite3.OperationalError("database is locked")),
        ):
            payload = asyncio.run(
                review_service.recheck_provider_sensitive_reviews(
                    self.container,
                    "system",
                    1001,
                    skip_on_busy=True,
                )
            )

        self.assertTrue(payload["skipped"])
        self.assertEqual(payload["skip_reason"], "database_locked")
        self.assertEqual(payload["summary"]["skipped_busy"], 1)
        self.assertEqual(payload["count"], 0)


if __name__ == "__main__":
    unittest.main()
