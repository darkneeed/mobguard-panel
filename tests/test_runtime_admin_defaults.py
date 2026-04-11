import unittest

from mobguard_platform.runtime_admin_defaults import (
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    normalize_telegram_runtime_settings,
    telegram_event_notifications_enabled,
)
from mobguard_platform.template_utils import render_optional_template


class RuntimeAdminDefaultsTests(unittest.TestCase):
    def test_legacy_shared_flags_are_mapped_to_granular_keys(self):
        normalized = normalize_telegram_runtime_settings(
            {
                "telegram_notify_review_enabled": False,
                "telegram_notify_warning_only_enabled": False,
                "telegram_notify_warning_enabled": False,
                "telegram_notify_ban_enabled": False,
            }
        )

        self.assertFalse(normalized["telegram_notify_admin_review_enabled"])
        self.assertFalse(normalized["telegram_notify_admin_warning_only_enabled"])
        self.assertFalse(normalized["telegram_notify_admin_warning_enabled"])
        self.assertFalse(normalized["telegram_notify_admin_ban_enabled"])
        self.assertFalse(normalized["telegram_notify_user_warning_only_enabled"])
        self.assertFalse(normalized["telegram_notify_user_warning_enabled"])
        self.assertFalse(normalized["telegram_notify_user_ban_enabled"])

    def test_granular_flags_override_legacy_values(self):
        normalized = normalize_telegram_runtime_settings(
            {
                "telegram_notify_warning_enabled": True,
                "telegram_notify_admin_warning_enabled": False,
            }
        )

        self.assertFalse(normalized["telegram_notify_admin_warning_enabled"])
        self.assertTrue(normalized["telegram_notify_user_warning_enabled"])

    def test_event_notifications_respect_master_switch_per_recipient(self):
        settings = {
            "telegram_admin_notifications_enabled": True,
            "telegram_user_notifications_enabled": False,
            "telegram_notify_admin_warning_enabled": True,
            "telegram_notify_user_warning_enabled": True,
        }

        self.assertTrue(telegram_event_notifications_enabled(settings, "admin", "warning"))
        self.assertFalse(telegram_event_notifications_enabled(settings, "user", "warning"))

    def test_admin_review_can_be_disabled_independently(self):
        settings = {
            "telegram_admin_notifications_enabled": True,
            "telegram_notify_admin_review_enabled": False,
        }

        self.assertFalse(telegram_event_notifications_enabled(settings, "admin", "review"))

    def test_default_admin_review_template_still_renders(self):
        rendered = render_optional_template(
            ENFORCEMENT_TEMPLATE_DEFAULTS["admin_review_template"],
            {
                "username": "alice",
                "system_id": 42,
                "telegram_id": 1001,
                "uuid": "uuid-1",
                "ip": "10.10.10.10",
                "isp": "ISP",
                "tag": "TAG",
                "confidence_band": "UNSURE",
                "review_url": "https://mobguard.example.com/reviews/1",
            },
            str,
        )

        self.assertIn("alice", rendered)
        self.assertIn("https://mobguard.example.com/reviews/1", rendered)

    def test_enforcement_defaults_include_traffic_cap_settings(self):
        self.assertEqual(ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_increment_gb"], 10)
        self.assertEqual(ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_threshold_gb"], 100)


if __name__ == "__main__":
    unittest.main()
