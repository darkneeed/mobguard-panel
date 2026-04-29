import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.services.telegram_notifier import emit_ingest_notifications
from mobguard_platform import AnalysisStore, DecisionBundle, PlatformStore


class RecordingNotifier:
    def __init__(self):
        self.admin_calls: list[tuple[str, dict]] = []
        self.user_calls: list[tuple[int, str, dict]] = []

    async def notify_admin(self, text: str, **kwargs):
        self.admin_calls.append((text, kwargs))
        return True

    async def notify_user(self, telegram_id: int, text: str, **kwargs):
        self.user_calls.append((telegram_id, text, kwargs))
        return True


class TelegramNotifierFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-telegram-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.env_path = self.root / ".env"
        self.env_path.write_text(
            "\n".join(
                (
                    "TG_ADMIN_BOT_TOKEN=admin-token",
                    "TG_MAIN_BOT_TOKEN=user-token",
                    "TG_ADMIN_BOT_USERNAME=mobguard_bot",
                )
            ),
            encoding="utf-8",
        )
        self.config = {
            "settings": {
                "review_ui_base_url": "https://mobguard.example.com",
                "tg_admin_chat_id": "-1001234567890",
                "tg_topic_id": 58,
                "telegram_admin_notifications_enabled": True,
                "telegram_user_notifications_enabled": True,
                "telegram_notify_admin_review_enabled": True,
                "telegram_notify_admin_warning_only_enabled": True,
                "telegram_notify_user_warning_only_enabled": True,
                "telegram_message_min_interval_seconds": 0.0,
                "dry_run": True,
            }
        }
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, self.config, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.store.sync_runtime_config(self.config)
        self.notifier = RecordingNotifier()
        self.container = SimpleNamespace(
            runtime=SimpleNamespace(
                env_path=self.env_path,
                env={},
                config=self.config,
            ),
            store=self.store,
            analysis_store=self.analysis_store,
            telegram_notifier=self.notifier,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_review_notifications_use_shared_runtime_templates(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            asn=12345,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        bundle.log.append("Provider review required")
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")
        bundle.case_id = summary.id

        asyncio.run(
            emit_ingest_notifications(
                self.container,
                user,
                bundle,
                "TAG",
                "provider_conflict",
                None,
            )
        )

        self.assertEqual(len(self.notifier.admin_calls), 1)
        text, kwargs = self.notifier.admin_calls[0]
        self.assertIn("Case ID", text)
        self.assertIn("alice", text)
        self.assertIn("Provider review required", text)
        self.assertTrue(str(kwargs.get("dedupe_key") or "").startswith("review:"))
        self.assertEqual(self.notifier.user_calls, [])

    def test_observe_mode_suppresses_user_warning_messages(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.21",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            asn=12345,
            isp="MTS",
        )
        bundle.event_id = 7
        bundle.log.append("Long session lifetime: 48.0h")

        asyncio.run(
            emit_ingest_notifications(
                self.container,
                user,
                bundle,
                "TAG",
                None,
                {
                    "type": "warning",
                    "warning_count": 1,
                    "warning_only": True,
                },
            )
        )

        self.assertEqual(len(self.notifier.admin_calls), 1)
        self.assertEqual(self.notifier.user_calls, [])


if __name__ == "__main__":
    unittest.main()
