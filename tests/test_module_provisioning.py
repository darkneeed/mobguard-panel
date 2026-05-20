import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from api.services import modules as module_service
from mobguard_platform import AnalysisStore, PlatformStore


class ModuleProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-module-provisioning-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.env_path = self.root / ".env"
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
                env_path=self.env_path,
                config=json.loads(self.config_path.read_text(encoding="utf-8")),
            ),
            store=self.store,
            analysis_store=self.analysis_store,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_module_returns_install_bundle_and_revealable_token(self):
        self.env_path.write_text("MOBGUARD_MODULE_SECRET_KEY=test-secret\n", encoding="utf-8")

        created = module_service.create_managed_module(
            self.container,
            {
                "module_name": "Node Alpha",
                "inbound_tags": ["DEFAULT-INBOUND", "CANARY-INBOUND"],
            },
        )

        module = created["module"]
        install = created["install"]

        self.assertTrue(module["module_id"].startswith("module-"))
        self.assertEqual(module["install_state"], "pending_install")
        self.assertTrue(module["managed"])
        self.assertTrue(module["token_reveal_available"])
        self.assertEqual(module["inbound_tags"], ["DEFAULT-INBOUND", "CANARY-INBOUND"])
        self.assertIn(MODULE_TOKEN_PLACEHOLDER := "__PASTE_TOKEN__", install["compose_yaml"])
        self.assertNotIn(install["module_token"], install["compose_yaml"])
        self.assertIn("https://mobguard.example.com/api", install["compose_yaml"])

        detail = module_service.get_module_detail(self.container, module["module_id"])
        self.assertEqual(detail["module"]["inbound_tags"], ["DEFAULT-INBOUND", "CANARY-INBOUND"])
        self.assertTrue(detail["module"]["token_reveal_available"])
        self.assertIn("healthy", detail["module"])
        self.assertIn("stale_after_seconds", detail["module"])
        self.assertIn(MODULE_TOKEN_PLACEHOLDER, detail["install"]["compose_yaml"])

        revealed = module_service.reveal_module_token(self.container, module["module_id"])
        self.assertEqual(revealed["module_token"], install["module_token"])

        registered = module_service.register_module(
            self.container,
            {
                "module_id": module["module_id"],
                "module_name": "Node Alpha",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            install["module_token"],
        )
        self.assertEqual(registered["module"]["install_state"], "online")
        self.assertTrue(registered["module"]["healthy"])

    def test_module_detail_uses_runtime_heartbeat_window_for_stale_status(self):
        self.env_path.write_text("MOBGUARD_MODULE_SECRET_KEY=test-secret\n", encoding="utf-8")
        config_payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        config_payload.setdefault("settings", {})
        config_payload["settings"]["module_heartbeat_interval_seconds"] = 120
        self.config_path.write_text(json.dumps(config_payload, ensure_ascii=False), encoding="utf-8")
        self.container.runtime.config = config_payload

        created = module_service.create_managed_module(
            self.container,
            {
                "module_name": "Node Alpha",
                "inbound_tags": ["DEFAULT-INBOUND"],
            },
        )
        module = created["module"]
        install = created["install"]
        module_service.register_module(
            self.container,
            {
                "module_id": module["module_id"],
                "module_name": "Node Alpha",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            install["module_token"],
        )

        with self.store._connect() as conn:
            conn.execute(
                "UPDATE modules SET last_seen_at = ? WHERE module_id = ?",
                ((datetime.utcnow().replace(microsecond=0) - timedelta(seconds=240)).isoformat(), module["module_id"]),
            )
            conn.commit()

        detail = module_service.get_module_detail(self.container, module["module_id"])

        self.assertEqual(detail["module"]["stale_after_seconds"], 480)
        self.assertTrue(detail["module"]["healthy"])

    def test_create_module_requires_secret_key(self):
        self.env_path.write_text("", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "MOBGUARD_MODULE_SECRET_KEY"):
            module_service.create_managed_module(
                self.container,
                {
                    "module_name": "Node Alpha",
                    "inbound_tags": ["DEFAULT-INBOUND"],
                },
            )

    def test_unknown_module_is_rejected_after_auto_register_removal(self):
        with self.assertRaisesRegex(ValueError, "Module is not registered"):
            module_service.register_module(
                self.container,
                {
                    "module_id": "node-missing",
                    "module_name": "Missing",
                    "version": "1.0.0",
                    "protocol_version": "v1",
                },
                "token-missing",
            )

    def test_existing_legacy_module_row_still_authenticates(self):
        legacy = self.store.register_module(
            "legacy-node",
            "legacy-token",
            module_name="Legacy Node",
            version="0.9.0",
            protocol_version="v1",
            metadata={"config_profiles": ["LEGACY-INBOUND"]},
            auto_create=True,
        )
        self.assertFalse(legacy["managed"])
        self.assertEqual(legacy["inbound_tags"], ["LEGACY-INBOUND"])

        registered = module_service.register_module(
            self.container,
            {
                "module_id": "legacy-node",
                "module_name": "Legacy Node",
                "version": "0.9.1",
                "protocol_version": "v1",
            },
            "legacy-token",
        )

        self.assertEqual(registered["module"]["module_id"], "legacy-node")
        self.assertEqual(registered["module"]["install_state"], "online")
        self.assertFalse(registered["module"]["managed"])
        self.assertEqual(registered["module"]["inbound_tags"], ["LEGACY-INBOUND"])

    def test_remnawave_client_reads_runtime_config_and_env_file(self):
        self.env_path.write_text("REMNAWAVE_API_TOKEN=runtime-token\n", encoding="utf-8")

        client = module_service._remnawave_client(self.container)

        self.assertEqual(client.base_url, "https://panel.example.com")
        self.assertEqual(client.token, "runtime-token")
        self.assertTrue(client.enabled)

    def test_request_module_restart_exposes_control_in_module_config(self):
        self.env_path.write_text("MOBGUARD_MODULE_SECRET_KEY=test-secret\n", encoding="utf-8")
        created = module_service.create_managed_module(
            self.container,
            {"module_name": "Node Restart", "inbound_tags": ["DEFAULT-INBOUND"]},
        )
        module_id = created["module"]["module_id"]
        module_service.register_module(
            self.container,
            {
                "module_id": module_id,
                "module_name": "Node Restart",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            created["install"]["module_token"],
        )

        restarted = module_service.request_module_restart(
            self.container,
            module_id,
            requested_by="owner:test",
        )
        module = restarted["module"]
        control = module.get("metadata", {}).get("module_control", {})
        restart_token = str(control.get("restart_token") or "").strip()

        self.assertTrue(restart_token)
        self.assertEqual(control.get("requested_by"), "owner:test")

        config_payload = module_service.get_module_config(self.container, module)["config"]
        self.assertEqual(config_payload.get("module_control", {}).get("restart_token"), restart_token)


if __name__ == "__main__":
    unittest.main()
