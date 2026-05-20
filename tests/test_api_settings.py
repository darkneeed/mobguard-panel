import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api.services import auth as auth_service
from api.services import settings as settings_service
from mobguard_platform.runtime import load_runtime_context


class RecordingNotifier:
    def __init__(self):
        self.admin_calls: list[tuple[str, dict]] = []
        self.force_calls: list[tuple[str, dict]] = []

    async def notify_admin(self, text: str, **kwargs):
        self.admin_calls.append((text, kwargs))
        return True

    async def notify_admin_force(self, text: str, **kwargs):
        self.force_calls.append((text, kwargs))
        return True


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
        self.assertEqual(initial["automation_status"]["mode"], "observe")

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

    def test_access_settings_roundtrip_includes_branding(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        class DummyStore:
            def __init__(self):
                self.synced = {}

            def get_live_rules_state(self):
                return {
                    "revision": 1,
                    "updated_at": "2026-04-12T00:00:00Z",
                    "updated_by": "system",
                    "rules": {
                        "admin_tg_ids": [1],
                        "exempt_tg_ids": [],
                        "exempt_ids": [],
                        "settings": {},
                    },
                }

            def sync_runtime_config(self, config):
                self.synced = config

        store = DummyStore()
        container = SimpleNamespace(runtime=runtime, store=store)

        initial = settings_service.get_access_settings(container)
        self.assertEqual(initial["settings"]["panel_name"], "MobGuard")
        self.assertEqual(initial["settings"]["panel_logo_url"], "")
        self.assertEqual(initial["settings"]["remnawave_api_url"], "")
        self.assertIn("owner_security", initial)
        self.assertFalse(initial["owner_security"]["totp_enabled"])

        updated = settings_service.update_access_settings(
            container,
            {
                "settings": {
                    "panel_name": "Acme Shield",
                    "panel_logo_url": "https://cdn.example.com/logo.png",
                    "remnawave_api_url": "https://panel.example.com/api",
                }
            },
            "admin",
            1001,
            None,
            None,
        )

        self.assertEqual(updated["settings"]["panel_name"], "Acme Shield")
        self.assertEqual(updated["settings"]["panel_logo_url"], "https://cdn.example.com/logo.png")
        self.assertEqual(updated["settings"]["remnawave_api_url"], "https://panel.example.com/api")
        self.assertEqual(store.synced["settings"]["panel_name"], "Acme Shield")
        config_payload = json.loads((self.runtime_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config_payload["settings"]["panel_logo_url"], "https://cdn.example.com/logo.png")
        self.assertEqual(config_payload["settings"]["remnawave_api_url"], "https://panel.example.com/api")

    def test_auth_start_payload_uses_runtime_branding(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        runtime.config.setdefault("settings", {})
        runtime.config["settings"]["panel_name"] = "Acme Shield"
        runtime.config["settings"]["panel_logo_url"] = "https://cdn.example.com/logo.png"

        class DummyStore:
            def get_live_rules_state(self):
                return {
                    "revision": 1,
                    "updated_at": "2026-04-12T00:00:00Z",
                    "updated_by": "system",
                    "rules": {"settings": {"review_ui_base_url": "https://panel.example.com"}},
                }

        payload = auth_service.auth_start_payload(SimpleNamespace(runtime=runtime, store=DummyStore()))

        self.assertEqual(payload["panel_name"], "Acme Shield")
        self.assertEqual(payload["panel_logo_url"], "https://cdn.example.com/logo.png")
        self.assertEqual(payload["review_ui_base_url"], "https://panel.example.com")

    def test_update_detection_settings_runs_provider_recheck_in_busy_safe_mode(self):
        container = SimpleNamespace(store=object())

        with patch.object(settings_service, "update_rules", return_value={"revision": 2}) as mocked_update_rules, patch.object(
            settings_service,
            "recheck_provider_sensitive_reviews",
            return_value={"skipped": True, "skip_reason": "database_locked"},
        ) as mocked_recheck:
            payload = settings_service.update_detection_settings(
                container,
                {"settings": {"provider_conflict_review_only": True}},
                "admin",
                1001,
                1,
                "2026-04-12T00:00:00Z",
            )

        self.assertEqual(payload["revision"], 2)
        mocked_update_rules.assert_called_once()
        mocked_recheck.assert_called_once_with(container, "admin", 1001, skip_on_busy=True)

    def test_update_telegram_settings_sends_applied_notification_in_embedded_mode(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        notifier = RecordingNotifier()

        class DummyStore:
            def sync_runtime_config(self, config):
                self.synced = config

            def get_service_heartbeat(self, service_name, stale_after_seconds=60):
                return {"status": "missing"}

        container = SimpleNamespace(runtime=runtime, store=DummyStore(), telegram_notifier=notifier)

        settings_service.update_telegram_settings(
            container,
            {"settings": {"telegram_user_notifications_enabled": False}},
        )

        self.assertEqual(len(notifier.admin_calls), 1)
        self.assertIn("Конфиг применён", notifier.admin_calls[0][0])

    def test_update_telegram_settings_force_notifies_when_admin_notifications_turn_off_in_embedded_mode(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            runtime = load_runtime_context(self.root, str(self.runtime_dir))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        notifier = RecordingNotifier()

        class DummyStore:
            def sync_runtime_config(self, config):
                self.synced = config

            def get_service_heartbeat(self, service_name, stale_after_seconds=60):
                return {"status": "missing"}

        container = SimpleNamespace(runtime=runtime, store=DummyStore(), telegram_notifier=notifier)

        settings_service.update_telegram_settings(
            container,
            {"settings": {"telegram_admin_notifications_enabled": False}},
        )

        self.assertEqual(len(notifier.force_calls), 1)
        self.assertIn("Уведомления администраторам", notifier.force_calls[0][0])


if __name__ == "__main__":
    unittest.main()
