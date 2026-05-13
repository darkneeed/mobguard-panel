import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from api.services import admin_audit
from api.services import ingest_pipeline
from api.services import modules as module_service
from mobguard_platform import AnalysisStore, PlatformStore


class SQLiteHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-sqlite-hardening-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps({"settings": {"threshold_mobile": 60}}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.store.sync_runtime_config(json.loads(self.config_path.read_text(encoding="utf-8")))
        self.container = SimpleNamespace(store=self.store, analysis_store=self.analysis_store)
        self.session = {
            "subject": "local:owner",
            "role": "owner",
            "auth_method": "local",
            "telegram_id": 1001,
            "username": "owner",
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_admin_action_skips_transient_busy_lock(self):
        container = SimpleNamespace(store=Mock())
        container.store.record_admin_audit_event.side_effect = sqlite3.OperationalError("database is locked")

        with patch("mobguard_platform.storage.sqlite.time.sleep", return_value=None), patch.object(
            admin_audit.logger, "warning"
        ) as mocked_warning:
            payload = admin_audit.record_admin_action(
                container,
                self.session,
                action="settings.telegram.update",
                target_type="settings_section",
                target_id="telegram",
                details={"has_settings": True},
            )

        self.assertFalse(payload["persisted"])
        self.assertEqual(payload["skip_reason"], "database_locked")
        self.assertEqual(container.store.record_admin_audit_event.call_count, 4)
        mocked_warning.assert_called_once()

    def test_record_admin_action_still_raises_non_busy_operational_errors(self):
        container = SimpleNamespace(store=Mock())
        container.store.record_admin_audit_event.side_effect = sqlite3.OperationalError("disk I/O error")

        with self.assertRaises(sqlite3.OperationalError):
            admin_audit.record_admin_action(
                container,
                self.session,
                action="settings.telegram.update",
                target_type="settings_section",
                target_id="telegram",
                details={},
            )

    def test_register_module_retries_transient_busy_connect_error(self):
        repo = self.store.modules_admin
        original_connect = repo.storage.connect
        call_count = {"count": 0}

        def flaky_connect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_connect(*args, **kwargs)

        with patch.object(repo.storage, "connect", side_effect=flaky_connect), patch(
            "mobguard_platform.storage.sqlite.time.sleep", return_value=None
        ):
            payload = repo.register_module(
                "node-a",
                "token-a",
                module_name="Node A",
                version="1.0.0",
                protocol_version="v1",
                auto_create=True,
            )

        self.assertEqual(payload["module_id"], "node-a")
        self.assertGreaterEqual(call_count["count"], 3)

    def test_record_module_heartbeat_retries_transient_busy_connect_error(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        self.store.register_module(
            "node-a",
            "token-a",
            module_name="Node A",
            version="1.0.0",
            protocol_version="v1",
            auto_create=False,
        )
        repo = self.store.modules_admin
        original_connect = repo.storage.connect
        call_count = {"count": 0}

        def flaky_connect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_connect(*args, **kwargs)

        with patch.object(repo.storage, "connect", side_effect=flaky_connect), patch(
            "mobguard_platform.storage.sqlite.time.sleep", return_value=None
        ):
            payload = repo.record_module_heartbeat(
                "node-a",
                status="online",
                version="1.0.1",
                protocol_version="v1",
                config_revision_applied=1,
                details={"health_status": "ok"},
            )

        self.assertEqual(payload["module_id"], "node-a")
        self.assertEqual(payload["health_status"], "ok")
        self.assertGreaterEqual(call_count["count"], 3)

    def test_module_service_register_still_fails_after_retry_exhaustion(self):
        with patch.object(
            self.store.modules_admin.storage,
            "connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ), patch("mobguard_platform.storage.sqlite.time.sleep", return_value=None):
            with self.assertRaises(module_service.ModuleStorageBusyError):
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

    def test_module_service_heartbeat_still_fails_after_retry_exhaustion(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        self.store.register_module(
            "node-a",
            "token-a",
            module_name="Node A",
            version="1.0.0",
            protocol_version="v1",
            auto_create=False,
        )

        with patch.object(
            self.store.modules_admin.storage,
            "connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ), patch("mobguard_platform.storage.sqlite.time.sleep", return_value=None):
            with self.assertRaises(module_service.ModuleStorageBusyError):
                module_service.record_module_heartbeat(
                    self.container,
                    {
                        "module_id": "node-a",
                        "status": "online",
                        "version": "1.0.1",
                        "protocol_version": "v1",
                        "config_revision_applied": 1,
                        "details": {},
                    },
                    "token-a",
                )

    def test_busy_log_warnings_are_throttled(self):
        busy_error = sqlite3.OperationalError("database is locked")
        with patch.dict(ingest_pipeline._LAST_BUSY_LOG_AT, {}, clear=True), patch(
            "api.services.ingest_pipeline.time.monotonic",
            side_effect=[0.0, 5.0, 35.0],
        ), patch.object(ingest_pipeline.logger, "warning") as mocked_warning:
            ingest_pipeline._log_best_effort_skip("Pipeline snapshot refresh", busy_error)
            ingest_pipeline._log_best_effort_skip("Pipeline snapshot refresh", busy_error)
            ingest_pipeline._log_best_effort_skip("Pipeline snapshot refresh", busy_error)

        self.assertEqual(mocked_warning.call_count, 2)


if __name__ == "__main__":
    unittest.main()
