import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.routers import health as health_router
from mobguard_platform import AnalysisStore, PlatformStore


class HealthAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-health-api-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "settings": {
                        "threshold_mobile": 60,
                    },
                    "_meta": {"revision": 1, "updated_at": "2026-04-11T10:00:00", "updated_by": "system"},
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

    def test_ready_returns_backend_info_when_db_and_schema_are_ready(self):
        payload = health_router.ready(container=self.container)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["backend"], "sqlite")
        self.assertEqual(payload["target"], self.db_path)

    def test_ready_returns_503_when_required_tables_are_missing(self):
        with patch.object(self.store.health, "get_readiness", return_value={
            "ready": False,
            "backend": "postgres",
            "target": "postgres",
            "missing_tables": ["live_rules", "analysis_events"],
            "error": "",
        }):
            with self.assertRaises(HTTPException) as ctx:
                health_router.ready(container=self.container)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("missing required tables", ctx.exception.detail)
        self.assertIn("live_rules", ctx.exception.detail)

    def test_ready_returns_503_when_db_connection_check_fails(self):
        with patch.object(self.store.health, "get_readiness", return_value={
            "ready": False,
            "backend": "postgres",
            "target": "postgres",
            "missing_tables": [],
            "error": "connection refused",
        }):
            with self.assertRaises(HTTPException) as ctx:
                health_router.ready(container=self.container)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "connection refused")


if __name__ == "__main__":
    unittest.main()
