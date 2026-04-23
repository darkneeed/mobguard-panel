import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.routers import metrics as metrics_router
from api.routers import modules as modules_router
from api.services import modules as module_service
from mobguard_platform import AnalysisStore, PlatformStore


class MetricsAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-metrics-api-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "mobile_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
                    "settings": {
                        "threshold_mobile": 60,
                        "review_ui_base_url": "https://mobguard.example.com",
                    },
                    "_meta": {"revision": 3, "updated_at": "2026-04-11T10:00:00", "updated_by": "system"},
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
        self.container = SimpleNamespace(store=self.store, analysis_store=self.analysis_store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_metrics_overview_returns_stale_snapshot_quickly_when_sqlite_is_locked(self):
        seeded = metrics_router.get_overview(_={}, container=self.container)
        self.assertFalse(seeded["pipeline"]["stale"])

        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", side_effect=sqlite3.OperationalError("database is locked")):
            payload = metrics_router.get_overview(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertEqual(payload["quality"], seeded["quality"])
        self.assertTrue(payload["pipeline"]["stale"])

    def test_metrics_overview_returns_fast_503_when_snapshot_is_missing_and_sqlite_is_locked(self):
        self.store._read_cache.clear()
        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", return_value=None):
            with patch.object(self.store, "refresh_overview_snapshot", side_effect=sqlite3.OperationalError("database is locked")):
                with self.assertRaises(HTTPException) as ctx:
                    metrics_router.get_overview(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("temporarily unavailable", ctx.exception.detail)

    def test_admin_modules_returns_pipeline_freshness_fields_without_blocking(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-a",
                "module_name": "Node A",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-a",
        )

        seeded = modules_router.admin_list_modules(_={}, container=self.container)
        self.assertIn("snapshot_updated_at", seeded["pipeline"])
        self.assertIn("snapshot_age_seconds", seeded["pipeline"])
        self.assertIn("stale", seeded["pipeline"])

        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", side_effect=sqlite3.OperationalError("database is locked")):
            payload = modules_router.admin_list_modules(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertIn("snapshot_updated_at", payload["pipeline"])
        self.assertIn("snapshot_age_seconds", payload["pipeline"])
        self.assertTrue(payload["pipeline"]["stale"])
