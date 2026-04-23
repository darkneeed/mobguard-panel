import json
import os
import shutil
import tempfile
import unittest

from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore
from mobguard_platform.usage_profile import (
    build_usage_profile_admin_lines,
    build_usage_profile_priority,
    build_usage_profile_snapshot,
    build_usage_profile_template_context,
)


class UsageProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-usage-profile-")
        self.db_path = os.path.join(self.temp_dir, "test.sqlite3")
        self.runtime_dir = os.path.join(self.temp_dir, "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.config_path = os.path.join(self.runtime_dir, "config.json")
        self.base_config = {
            "settings": {
                "threshold_mobile": 60,
                "threshold_home": 15,
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "review_ui_base_url": "https://mobguard.example.com",
            }
        }
        self.store = PlatformStore(self.db_path, self.base_config, self.config_path)
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _record_event(
        self,
        created_at: str,
        ip: str,
        provider: str,
        module_id: str,
        module_name: str,
        *,
        country: str = "",
        region: str = "",
        city: str = "",
        loc: str = "",
        device_id: str = "",
        device_label: str = "",
        os_family: str = "",
        os_version: str = "",
        app_name: str = "",
        app_version: str = "",
    ) -> int:
        bundle = DecisionBundle(
            ip=ip,
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp=provider,
            punitive_eligible=False,
        )
        if any((country, region, city, loc)):
            bundle.signal_flags["geo"] = {
                "country": country,
                "region": region,
                "city": city,
                "loc": loc,
            }
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "module_id": module_id,
            "module_name": module_name,
        }
        event_id = self.store.record_analysis_event(
            user,
            ip,
            "TAG",
            bundle,
            {
                "client_device_id": device_id,
                "client_device_label": device_label,
                "client_os_family": os_family,
                "client_os_version": os_version,
                "client_app_name": app_name,
                "client_app_version": app_version,
            },
        )
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", (created_at, event_id))
            conn.commit()
        return event_id

    def test_snapshot_flags_geo_travel_and_soft_rotation_without_changing_punitive_state(self):
        event_id = self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            country="RU",
            region="Moscow",
            city="Moscow",
            loc="55.7558,37.6176",
            device_id="ios-1",
            device_label="iPhone 15",
            os_family="iOS",
            os_version="17.4",
            app_name="Happ",
            app_version="1.0.0",
        )
        self._record_event(
            "2026-04-11T12:00:00",
            "2.2.2.2",
            "Provider DE",
            "node-b",
            "Node B",
            country="DE",
            region="Berlin",
            city="Berlin",
            loc="52.5200,13.4050",
            device_id="and-1",
            device_label="Pixel 8",
            os_family="Android",
            os_version="15",
            app_name="Happ",
            app_version="1.2.3",
        )

        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            anchor_started_at="2026-04-11T10:00:00",
        )

        self.assertTrue(snapshot["travel_flags"]["geo_country_jump"])
        self.assertTrue(snapshot["travel_flags"]["geo_impossible_travel"])
        self.assertIn("device_rotation", snapshot["soft_reasons"])
        self.assertIn("cross_node_fanout", snapshot["soft_reasons"])
        self.assertGreater(snapshot["ongoing_duration_seconds"], 0)

        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT punitive_eligible FROM analysis_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertEqual(row["punitive_eligible"], 0)

    def test_snapshot_uses_panel_user_device_fallback(self):
        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            panel_user={
                "hwidDevices": [
                    {
                        "hwid": "hwid-1",
                        "platform": "Android",
                        "osVersion": "15",
                        "deviceModel": "Pixel 8",
                        "appVersion": "1.2.3",
                    }
                ]
            },
        )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["device_count"], 1)
        self.assertIn("Pixel 8", snapshot["device_labels"])

    def test_template_context_contains_summary_and_counters(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            country="RU",
            region="Moscow",
            city="Moscow",
            loc="55.7558,37.6176",
            device_id="ios-1",
            device_label="iPhone 15",
            os_family="iOS",
        )
        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )
        context = build_usage_profile_template_context(snapshot)

        self.assertIn("IPs", context["usage_profile_summary"])
        self.assertEqual(context["usage_profile_ip_count"], 1)
        self.assertEqual(context["usage_profile_device_count"], 1)

    def test_priority_and_admin_lines_include_usage_signals(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            country="RU",
            region="Moscow",
            city="Moscow",
            loc="55.7558,37.6176",
            device_id="ios-1",
            device_label="iPhone 15",
            os_family="iOS",
        )
        self._record_event(
            "2026-04-11T12:00:00",
            "2.2.2.2",
            "Provider DE",
            "node-b",
            "Node B",
            country="DE",
            region="Berlin",
            city="Berlin",
            loc="52.5200,13.4050",
            device_id="and-1",
            device_label="Pixel 8",
            os_family="Android",
        )
        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            anchor_started_at="2026-04-11T10:00:00",
        )

        priority = build_usage_profile_priority(
            snapshot,
            punitive_eligible=False,
            confidence_band="PROBABLE_HOME",
            repeat_count=2,
        )
        lines = build_usage_profile_admin_lines(snapshot, scenario="violation_continues")

        self.assertGreater(priority["priority"], 0)
        self.assertGreater(priority["signal_count"], 0)
        self.assertTrue(any("Scenario:" in line for line in lines))
        self.assertTrue(any("Usage snapshot:" in line for line in lines))

    def test_snapshot_prefers_byte_based_traffic_burst_when_series_is_available(self):
        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            panel_user={
                "uuid": "uuid-1",
                "usageProfileTrafficStats": {
                    "series": [
                        {"timestamp": "2026-04-22T10:00:00", "node-a": 300 * 1024 * 1024},
                        {"timestamp": "2026-04-22T10:10:00", "node-a": 400 * 1024 * 1024},
                        {"timestamp": "2026-04-22T10:20:00", "node-a": 350 * 1024 * 1024},
                    ]
                },
            },
        )

        self.assertEqual(snapshot["traffic_burst"]["source"], "traffic_bytes")
        self.assertEqual(snapshot["traffic_burst"]["point_count"], 3)
        self.assertIn("traffic_burst", snapshot["soft_reasons"])
        self.assertIn("traffic", snapshot["usage_profile_summary"])

    def test_snapshot_can_be_device_scoped_to_avoid_cross_device_travel_noise(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            country="RU",
            region="Moscow",
            city="Moscow",
            loc="55.7558,37.6176",
            device_id="ios-1",
            device_label="iPhone 15",
            os_family="iOS",
        )
        self._record_event(
            "2026-04-11T10:30:00",
            "2.2.2.2",
            "Provider DE",
            "node-b",
            "Node B",
            country="DE",
            region="Berlin",
            city="Berlin",
            loc="52.5200,13.4050",
            device_id="and-1",
            device_label="Pixel 8",
            os_family="Android",
        )

        user_snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )
        device_snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            device_scope_key="device:ios-1",
        )

        self.assertTrue(user_snapshot["travel_flags"]["geo_country_jump"])
        self.assertFalse(device_snapshot["travel_flags"]["geo_country_jump"])
        self.assertEqual(device_snapshot["ip_count"], 1)
        self.assertEqual(device_snapshot["device_count"], 1)


if __name__ == "__main__":
    unittest.main()
