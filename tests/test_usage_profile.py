import json
import os
import shutil
import tempfile
import unittest
import sqlite3
from unittest.mock import patch
import datetime as real_datetime

class MockDatetime(real_datetime.datetime):
    @classmethod
    def utcnow(cls):
        return real_datetime.datetime(2026, 4, 20, 12, 0, 0)
    
    @classmethod
    def fromisoformat(cls, *args, **kwargs):
        return real_datetime.datetime.fromisoformat(*args, **kwargs)
from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore
from mobguard_platform.usage_profile import (
    build_usage_profile_admin_lines,
    build_usage_profile_priority,
    build_usage_profile_snapshot,
    build_usage_profile_template_context,
    shared_account_suspected_from_usage_profile,
)


class UsageProfileTests(unittest.TestCase):
    def setUp(self):
        self.mock_dt_patcher = patch("mobguard_platform.usage_profile.datetime", MockDatetime)
        self.mock_dt_patcher.start()
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
        
        class SQLiteTestStorage:
            def __init__(self, db_path):
                self.db_path = db_path
            def connect(self, **kwargs):
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                return conn

        self.storage = SQLiteTestStorage(self.db_path)
        self.store = PlatformStore(self.db_path, self.base_config, self.config_path, storage=self.storage)
        self.store._table_exists = lambda conn, name: conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None
        self.store.init_schema()

    def tearDown(self):
        self.mock_dt_patcher.stop()
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

        self.assertIn("IP", context["usage_profile_summary"])
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
        self.assertTrue(any("Сценарий:" in line for line in lines))
        self.assertTrue(any("Профиль использования:" in line for line in lines))

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
        self.assertIn("трафик", snapshot["usage_profile_summary"])

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

    def test_multiple_exact_devices_are_context_only_without_hwid_limit_exceeded(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            device_id="ios-1",
            device_label="iPhone 15",
            os_family="iOS",
        )
        self._record_event(
            "2026-04-11T10:10:00",
            "1.1.1.2",
            "Provider RU",
            "node-a",
            "Node A",
            device_id="and-1",
            device_label="Pixel 8",
            os_family="Android",
        )

        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )

        self.assertEqual(snapshot["exact_device_count"], 2)
        self.assertFalse(shared_account_suspected_from_usage_profile(snapshot))

    def test_shared_account_suspected_only_when_hwid_limit_is_exceeded(self):
        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
            panel_user={
                "hwidDeviceLimit": 1,
                "hwidDevices": [
                    {"hwid": "hwid-1", "deviceModel": "Pixel 8"},
                    {"hwid": "hwid-2", "deviceModel": "iPhone 15"},
                ],
            },
        )

        self.assertEqual(snapshot["hwid_device_limit"], 1)
        self.assertEqual(snapshot["hwid_device_count_exact"], 2)
        self.assertTrue(shared_account_suspected_from_usage_profile(snapshot))

    def test_shared_account_suspected_when_device_os_mismatch_is_detected(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider RU",
            "node-a",
            "Node A",
            device_id="stable-1",
            device_label="Shared handset",
            os_family="iOS",
        )
        self._record_event(
            "2026-04-11T10:10:00",
            "1.1.1.2",
            "Provider RU",
            "node-a",
            "Node A",
            device_id="stable-1",
            device_label="Shared handset",
            os_family="Android",
        )

        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )

        self.assertIn("device_os_mismatch", snapshot["soft_reasons"])
        self.assertFalse(shared_account_suspected_from_usage_profile(snapshot))

    def test_shared_account_suspected_when_geo_impossible_travel_is_detected(self):
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
        )

        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )

        self.assertIn("geo_impossible_travel", snapshot["soft_reasons"])
        self.assertFalse(shared_account_suspected_from_usage_profile(snapshot))

    def test_shared_account_suspected_when_cross_node_and_provider_fanout_overlap(self):
        self._record_event(
            "2026-04-11T10:00:00",
            "1.1.1.1",
            "Provider A",
            "node-a",
            "Node A",
        )
        self._record_event(
            "2026-04-11T10:10:00",
            "1.1.1.2",
            "Provider B",
            "node-b",
            "Node B",
        )
        self._record_event(
            "2026-04-11T10:20:00",
            "1.1.1.3",
            "Provider C",
            "node-b",
            "Node B",
        )

        snapshot = build_usage_profile_snapshot(
            self.store,
            {"uuid": "uuid-1", "username": "alice", "system_id": 42, "telegram_id": "1001"},
        )

        self.assertIn("cross_node_fanout", snapshot["soft_reasons"])
        self.assertIn("provider_fanout", snapshot["soft_reasons"])
        self.assertFalse(shared_account_suspected_from_usage_profile(snapshot))

    def test_determine_risk_title_scenarios(self):
        from mobguard_platform.usage_profile import determine_risk_title

        # Scenario 1: Traffic burst, no limit (unlimited)
        profile_unlimited = {
            "soft_reasons": ["traffic_burst"],
            "traffic_limit_bytes": 0
        }
        self.assertEqual(determine_risk_title(profile_unlimited), "ВСПЛЕСК ТРАФИКА")

        # Scenario 2: Traffic burst, limit is None (unlimited fallback)
        profile_none_limit = {
            "soft_reasons": ["traffic_burst"],
            "traffic_limit_bytes": None
        }
        self.assertEqual(determine_risk_title(profile_none_limit), "ВСПЛЕСК ТРАФИКА")

        # Scenario 3: Traffic burst, positive limit
        profile_limited = {
            "soft_reasons": ["traffic_burst"],
            "traffic_limit_bytes": 10 * 1024 * 1024 * 1024
        }
        self.assertEqual(determine_risk_title(profile_limited), "ПРЕВЫШЕНИЕ ТРАФИКА")

        # Scenario 4: Prioritize Device Rotation over Traffic Burst
        profile_both = {
            "soft_reasons": ["traffic_burst", "device_rotation"],
            "traffic_limit_bytes": 0
        }
        self.assertEqual(determine_risk_title(profile_both), "ПРЕВЫШЕНИЕ КОЛИЧЕСТВА УСТРОЙСТВ")

        # Scenario 5: Prioritize Connection Type (provider_fanout) over Traffic Burst
        profile_connection = {
            "soft_reasons": ["traffic_burst", "provider_fanout"],
            "traffic_limit_bytes": 0
        }
        self.assertEqual(determine_risk_title(profile_connection), "НЕВЕРНЫЙ ТИП ПОДКЛЮЧЕНИЯ")


if __name__ == "__main__":
    unittest.main()
