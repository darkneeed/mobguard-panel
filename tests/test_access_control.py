import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api.services import data_admin as data_admin_service
from mobguard_platform.access_control import (
    apply_remote_traffic_cap,
    build_auto_restriction_state,
    apply_remote_access_state,
    apply_remote_access_state_async,
    restore_remote_restriction_state,
    restore_remote_restriction_state_async,
    SQUAD_RESTRICTION_MODE,
    TRAFFIC_CAP_RESTRICTION_MODE,
)


class FakeSyncClient:
    def __init__(self):
        self.calls = []
        self.traffic_calls = []

    def apply_access_squad(self, uuid, squad_name):
        self.calls.append((uuid, squad_name))
        return True

    def update_user_traffic_limit(self, uuid, traffic_limit_bytes, traffic_limit_strategy):
        self.traffic_calls.append((uuid, traffic_limit_bytes, traffic_limit_strategy))
        return True


class FakeAsyncClient:
    def __init__(self, result=True):
        self.calls = []
        self.traffic_calls = []
        self.result = result

    async def apply_access_squad(self, uuid, squad_name):
        self.calls.append((uuid, squad_name))
        return self.result

    async def update_user_traffic_limit(self, uuid, traffic_limit_bytes, traffic_limit_strategy):
        self.traffic_calls.append((uuid, traffic_limit_bytes, traffic_limit_strategy))
        return self.result


class FakeStore:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE violations (
                uuid TEXT PRIMARY KEY,
                strikes INTEGER,
                unban_time TEXT,
                last_forgiven TEXT,
                last_strike_time TEXT,
                warning_time TEXT,
                warning_count INTEGER DEFAULT 0,
                restriction_mode TEXT,
                saved_traffic_limit_bytes INTEGER,
                saved_traffic_limit_strategy TEXT,
                applied_traffic_limit_bytes INTEGER
            );
            CREATE TABLE violation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                ip TEXT,
                isp TEXT,
                asn INTEGER,
                tag TEXT,
                strike_number INTEGER,
                punishment_duration INTEGER,
                timestamp TEXT
            );
            """
        )

    def _connect(self):
        return self.conn


class AccessControlTests(unittest.TestCase):
    def test_sync_helper_applies_restricted_squad_name(self):
        client = FakeSyncClient()
        result = apply_remote_access_state(
            client,
            "uuid-1",
            {
                "full_access_squad_name": "✨ все",
                "restricted_access_squad_name": "⚠ ограниченные",
            },
            restricted=True,
        )

        self.assertTrue(result)
        self.assertEqual(client.calls, [("uuid-1", "⚠ ограниченные")])

    def test_build_auto_restriction_state_prefers_traffic_cap_above_threshold(self):
        state = build_auto_restriction_state(
            {
                "trafficLimitBytes": 0,
                "trafficLimitStrategy": "NO_RESET",
                "userTraffic": {
                    "usedTrafficBytes": 150 * 1024 ** 3,
                    "lifetimeUsedTrafficBytes": 220 * 1024 ** 3,
                },
            },
            {"traffic_cap_increment_gb": 10, "traffic_cap_threshold_gb": 100},
        )

        self.assertEqual(state["restriction_mode"], TRAFFIC_CAP_RESTRICTION_MODE)
        self.assertEqual(state["applied_traffic_limit_bytes"], 160 * 1024 ** 3)

    def test_build_auto_restriction_state_uses_squad_below_threshold(self):
        state = build_auto_restriction_state(
            {
                "trafficLimitBytes": 0,
                "trafficLimitStrategy": "NO_RESET",
                "userTraffic": {
                    "usedTrafficBytes": 50 * 1024 ** 3,
                    "lifetimeUsedTrafficBytes": 220 * 1024 ** 3,
                },
            },
            {"traffic_cap_increment_gb": 10, "traffic_cap_threshold_gb": 100},
        )

        self.assertEqual(state["restriction_mode"], SQUAD_RESTRICTION_MODE)
        self.assertIsNone(state["applied_traffic_limit_bytes"])

    def test_apply_remote_traffic_cap_keeps_stricter_existing_limit(self):
        client = FakeSyncClient()
        result = apply_remote_traffic_cap(
            client,
            "uuid-1",
            {
                "trafficLimitBytes": 70 * 1024 ** 3,
                "trafficLimitStrategy": "MONTH",
                "userTraffic": {"usedTrafficBytes": 80 * 1024 ** 3},
            },
            10,
        )

        self.assertTrue(result["remote_updated"])
        self.assertFalse(result["remote_changed"])
        self.assertTrue(result["preserved_existing_limit"])
        self.assertEqual(result["applied_traffic_limit_bytes"], 70 * 1024 ** 3)
        self.assertEqual(client.traffic_calls, [])

    def test_restore_remote_restriction_state_restores_saved_traffic_limit(self):
        client = FakeSyncClient()
        result = restore_remote_restriction_state(
            client,
            "uuid-1",
            {},
            {
                "restriction_mode": TRAFFIC_CAP_RESTRICTION_MODE,
                "saved_traffic_limit_bytes": 0,
                "saved_traffic_limit_strategy": "NO_RESET",
                "applied_traffic_limit_bytes": 110 * 1024 ** 3,
            },
        )

        self.assertTrue(result["remote_updated"])
        self.assertEqual(client.traffic_calls, [("uuid-1", 0, "NO_RESET")])


class AsyncAccessControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_helper_restores_full_squad_name(self):
        client = FakeAsyncClient()
        result = await apply_remote_access_state_async(
            client,
            "uuid-1",
            {
                "full_access_squad_name": "✨ все",
                "restricted_access_squad_name": "⚠ ограниченные",
            },
            restricted=False,
        )

        self.assertTrue(result)
        self.assertEqual(client.calls, [("uuid-1", "✨ все")])

    async def test_async_restore_noop_when_previous_stricter_limit_was_preserved(self):
        client = FakeAsyncClient()
        result = await restore_remote_restriction_state_async(
            client,
            "uuid-1",
            {},
            {
                "restriction_mode": TRAFFIC_CAP_RESTRICTION_MODE,
                "saved_traffic_limit_bytes": None,
                "saved_traffic_limit_strategy": None,
                "applied_traffic_limit_bytes": 70 * 1024 ** 3,
            },
        )

        self.assertTrue(result["remote_updated"])
        self.assertEqual(client.traffic_calls, [])


class DataAdminAccessTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.container = SimpleNamespace(
            store=self.store,
            runtime=SimpleNamespace(
                config={
                    "settings": {
                        "full_access_squad_name": "FULL",
                        "restricted_access_squad_name": "MOBILE_BLOCKED",
                    }
                }
            ),
        )

    def test_manual_restriction_uses_restricted_squad_name(self):
        panel = SimpleNamespace(
            enabled=True,
            last_error=None,
            calls=[],
            apply_access_squad=lambda uuid, squad_name: panel.calls.append((uuid, squad_name)) or True,
        )
        with patch.object(
            data_admin_service,
            "resolve_user_identity",
            return_value={"uuid": "uuid-1"},
        ), patch.object(
            data_admin_service,
            "panel_client",
            return_value=panel,
        ), patch.object(
            data_admin_service,
            "get_user_card",
            return_value={"identity": {"uuid": "uuid-1"}},
        ):
            payload = data_admin_service.ban_user(self.container, "uuid-1", 15)

        row = self.store.conn.execute(
            "SELECT strikes, unban_time FROM violations WHERE uuid = ?",
            ("uuid-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(panel.calls, [("uuid-1", "MOBILE_BLOCKED")])
        self.assertTrue(payload["remote_updated"])

    def test_failed_full_access_restore_keeps_local_restriction(self):
        self.store.conn.execute(
            """
            INSERT INTO violations (
                uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
                restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            )
            VALUES ('uuid-1', 1, '2026-04-11T12:00:00', NULL, '2026-04-11T11:45:00', NULL, 0, 'SQUAD', NULL, NULL, NULL)
            """
        )
        self.store.conn.commit()

        panel = SimpleNamespace(
            enabled=True,
            last_error="Internal squad 'FULL' was not found",
            calls=[],
            apply_access_squad=lambda uuid, squad_name: panel.calls.append((uuid, squad_name)) or False,
        )
        with patch.object(
            data_admin_service,
            "resolve_user_identity",
            return_value={"uuid": "uuid-1"},
        ), patch.object(
            data_admin_service,
            "panel_client",
            return_value=panel,
        ), patch.object(
            data_admin_service,
            "get_user_card",
            return_value={"identity": {"uuid": "uuid-1"}},
        ):
            payload = data_admin_service.unban_user(self.container, "uuid-1")

        row = self.store.conn.execute(
            "SELECT uuid FROM violations WHERE uuid = ?",
            ("uuid-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(panel.calls, [("uuid-1", "FULL")])
        self.assertFalse(payload["remote_updated"])
        self.assertEqual(payload["remote_error"], "Internal squad 'FULL' was not found")

    def test_manual_traffic_cap_applies_used_plus_requested_gigabytes(self):
        panel = SimpleNamespace(
            enabled=True,
            last_error=None,
            calls=[],
            traffic_calls=[],
            update_user_traffic_limit=lambda uuid, limit, strategy: panel.traffic_calls.append((uuid, limit, strategy)) or True,
        )
        with patch.object(
            data_admin_service,
            "resolve_user_identity",
            return_value={
                "uuid": "uuid-1",
                "panel_user": {
                    "trafficLimitBytes": 0,
                    "trafficLimitStrategy": "NO_RESET",
                    "userTraffic": {"usedTrafficBytes": 120 * 1024 ** 3},
                },
            },
        ), patch.object(
            data_admin_service,
            "panel_client",
            return_value=panel,
        ), patch.object(
            data_admin_service,
            "get_user_card",
            return_value={"identity": {"uuid": "uuid-1"}},
        ):
            payload = data_admin_service.apply_user_traffic_cap(self.container, "uuid-1", 10)

        row = self.store.conn.execute(
            "SELECT saved_traffic_limit_bytes, applied_traffic_limit_bytes FROM manual_traffic_cap_overrides WHERE uuid = ?",
            ("uuid-1",),
        ).fetchone()
        self.assertEqual(panel.traffic_calls, [("uuid-1", 130 * 1024 ** 3, "NO_RESET")])
        self.assertIsNotNone(row)
        self.assertEqual(row["saved_traffic_limit_bytes"], 0)
        self.assertEqual(payload["traffic_cap"]["applied_traffic_limit_bytes"], 130 * 1024 ** 3)

    def test_manual_traffic_cap_restore_replays_saved_limit(self):
        self.store.conn.execute(
            """
            CREATE TABLE manual_traffic_cap_overrides (
                uuid TEXT PRIMARY KEY,
                saved_traffic_limit_bytes INTEGER,
                saved_traffic_limit_strategy TEXT,
                applied_traffic_limit_bytes INTEGER,
                updated_at TEXT
            )
            """
        )
        self.store.conn.execute(
            """
            INSERT INTO manual_traffic_cap_overrides (
                uuid, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes, updated_at
            ) VALUES ('uuid-1', 0, 'NO_RESET', 130000000000, '2026-04-11T12:00:00')
            """
        )
        self.store.conn.commit()

        panel = SimpleNamespace(
            enabled=True,
            last_error=None,
            traffic_calls=[],
            update_user_traffic_limit=lambda uuid, limit, strategy: panel.traffic_calls.append((uuid, limit, strategy)) or True,
        )
        with patch.object(
            data_admin_service,
            "resolve_user_identity",
            return_value={"uuid": "uuid-1"},
        ), patch.object(
            data_admin_service,
            "panel_client",
            return_value=panel,
        ), patch.object(
            data_admin_service,
            "get_user_card",
            return_value={"identity": {"uuid": "uuid-1"}},
        ):
            payload = data_admin_service.restore_user_traffic_cap(self.container, "uuid-1")

        row = self.store.conn.execute(
            "SELECT uuid FROM manual_traffic_cap_overrides WHERE uuid = ?",
            ("uuid-1",),
        ).fetchone()
        self.assertEqual(panel.traffic_calls, [("uuid-1", 0, "NO_RESET")])
        self.assertIsNone(row)
        self.assertTrue(payload["remote_updated"])


if __name__ == "__main__":
    unittest.main()
