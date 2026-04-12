import json
import shutil
import tempfile
import unittest
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
                "host": "node-alpha.example.com",
                "port": 2222,
                "access_log_path": "/var/log/remnanode/access.log",
                "config_profiles": ["Default-Profile", "Canary-Profile"],
                "provider": "hetzner",
                "notes": "primary collector",
            },
        )

        module = created["module"]
        install = created["install"]

        self.assertTrue(module["module_id"].startswith("module-"))
        self.assertEqual(module["install_state"], "pending_install")
        self.assertTrue(module["managed"])
        self.assertTrue(module["token_reveal_available"])
        self.assertIn(MODULE_TOKEN_PLACEHOLDER := "__PASTE_TOKEN__", install["compose_yaml"])
        self.assertNotIn(install["module_token"], install["compose_yaml"])
        self.assertIn("https://panel.example.com", install["compose_yaml"])

        detail = module_service.get_module_detail(self.container, module["module_id"])
        self.assertEqual(detail["module"]["host"], "node-alpha.example.com")
        self.assertEqual(detail["module"]["config_profiles"], ["Default-Profile", "Canary-Profile"])
        self.assertTrue(detail["module"]["token_reveal_available"])
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

    def test_create_module_requires_secret_key(self):
        self.env_path.write_text("", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "MOBGUARD_MODULE_SECRET_KEY"):
            module_service.create_managed_module(
                self.container,
                {
                    "module_name": "Node Alpha",
                    "host": "node-alpha.example.com",
                    "port": 2222,
                    "access_log_path": "/var/log/remnanode/access.log",
                    "config_profiles": ["Default-Profile"],
                    "provider": "",
                    "notes": "",
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
            metadata={"host": "legacy.example.com"},
            auto_create=True,
        )
        self.assertFalse(legacy["managed"])

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


if __name__ == "__main__":
    unittest.main()
