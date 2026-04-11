import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.services import settings as settings_service
from mobguard_platform.runtime import load_runtime_context


class APISettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-api-settings-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        (self.root / ".env").write_text(
            "\n".join(
                [
                    "TG_MAIN_BOT_TOKEN=main-token",
                    "TG_ADMIN_BOT_TOKEN=admin-token",
                    "TG_ADMIN_BOT_USERNAME=adminbot",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.runtime_dir / "config.json").write_text(
            json.dumps(
                {
                    "settings": {
                        "tg_admin_chat_id": "-1001",
                        "tg_topic_id": 10,
                        "telegram_message_min_interval_seconds": 1.5,
                        "telegram_admin_notifications_enabled": True,
                        "telegram_user_notifications_enabled": True,
                        "telegram_admin_commands_enabled": True,
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_telegram_settings_returns_settings_payload(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        container = SimpleNamespace(runtime=runtime)
        payload = settings_service.get_telegram_settings(container)

        self.assertEqual(payload["settings"]["tg_admin_chat_id"], "-1001")
        self.assertEqual(payload["settings"]["tg_topic_id"], 10)
        self.assertTrue(payload["capabilities"]["admin_bot_enabled"])
        self.assertTrue(payload["capabilities"]["user_bot_enabled"])

    def test_enforcement_settings_roundtrip_includes_squad_names(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        synced = {}

        class DummyStore:
            def sync_runtime_config(self, config):
                synced["config"] = config

        container = SimpleNamespace(runtime=runtime, store=DummyStore())

        initial = settings_service.get_enforcement_settings(container)
        self.assertEqual(initial["settings"]["full_access_squad_name"], "FULL")
        self.assertEqual(initial["settings"]["restricted_access_squad_name"], "MOBILE_BLOCKED")
        self.assertEqual(initial["settings"]["traffic_cap_increment_gb"], 10)
        self.assertEqual(initial["settings"]["traffic_cap_threshold_gb"], 100)

        updated = settings_service.update_enforcement_settings(
            container,
            {
                "settings": {
                    "full_access_squad_name": "✨ все",
                    "restricted_access_squad_name": "⚠ ограниченные",
                    "traffic_cap_increment_gb": 12,
                    "traffic_cap_threshold_gb": 140,
                }
            },
        )

        self.assertEqual(updated["settings"]["full_access_squad_name"], "✨ все")
        self.assertEqual(updated["settings"]["restricted_access_squad_name"], "⚠ ограниченные")
        self.assertEqual(updated["settings"]["traffic_cap_increment_gb"], 12)
        self.assertEqual(updated["settings"]["traffic_cap_threshold_gb"], 140)
        self.assertEqual(
            synced["config"]["settings"]["full_access_squad_name"],
            "✨ все",
        )
        config_payload = json.loads((self.runtime_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config_payload["settings"]["restricted_access_squad_name"], "⚠ ограниченные")
        self.assertEqual(config_payload["settings"]["traffic_cap_increment_gb"], 12)


if __name__ == "__main__":
    unittest.main()
