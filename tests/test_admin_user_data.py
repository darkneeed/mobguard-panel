import sqlite3
import unittest
from unittest.mock import patch

from api import main
from api.services.runtime_state import (
    build_user_export_payload,
    enrich_panel_user_devices,
    enrich_panel_user_usage_context,
)
from mobguard_platform.panel_client import PanelClient


class FakeStore:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE review_cases (
                id INTEGER PRIMARY KEY,
                uuid TEXT,
                username TEXT,
                system_id INTEGER,
                telegram_id TEXT,
                status TEXT,
                review_reason TEXT,
                ip TEXT,
                verdict TEXT,
                confidence_band TEXT,
                opened_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE analysis_events (
                id INTEGER PRIMARY KEY,
                uuid TEXT,
                username TEXT,
                system_id INTEGER,
                telegram_id TEXT,
                created_at TEXT,
                ip TEXT,
                tag TEXT,
                verdict TEXT,
                confidence_band TEXT,
                score INTEGER,
                isp TEXT,
                asn INTEGER,
                reasons_json TEXT,
                signal_flags_json TEXT,
                bundle_json TEXT
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO review_cases (
                id, uuid, username, system_id, telegram_id, status, review_reason, ip, verdict,
                confidence_band, opened_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "a878b04c-31a9-4b81-9c2c-3d0b19a2e1ad",
                "alice",
                42,
                "1001",
                "OPEN",
                "review",
                "10.0.0.1",
                "HOME",
                "PROBABLE_HOME",
                "2026-04-09T10:00:00",
                "2026-04-09T10:05:00",
            ),
        )
        self.conn.execute(
            """
            INSERT INTO analysis_events (
                id, uuid, username, system_id, telegram_id, created_at, ip, tag, verdict,
                confidence_band, score, isp, asn, reasons_json, signal_flags_json, bundle_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                "a878b04c-31a9-4b81-9c2c-3d0b19a2e1ad",
                "alice",
                42,
                "1001",
                "2026-04-09T10:04:00",
                "10.0.0.1",
                "TAG",
                "HOME",
                "PROBABLE_HOME",
                75,
                "ISP",
                12345,
                '[{"code":"provider_home_marker","source":"provider_profile","direction":"HOME","weight":-18}]',
                '{"provider_evidence":{"provider_key":"beeline","provider_classification":"mixed","service_type_hint":"home","service_conflict":false,"review_recommended":true}}',
                '{"reasons":[{"code":"provider_home_marker","source":"provider_profile","direction":"HOME","weight":-18}],"signal_flags":{"provider_evidence":{"provider_key":"beeline","provider_classification":"mixed","service_type_hint":"home","service_conflict":false,"review_recommended":true}}}',
            ),
        )
        self.conn.commit()

    def _connect(self):
        return self.conn

    def _table_exists(self, conn, table_name):
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def get_live_rules_state(self):
        return {
            "rules": {
                "exempt_ids": ["42", "", "oops"],
                "exempt_tg_ids": ["1001", None, "bad"],
            }
        }


class AdminUserDataTests(unittest.TestCase):
    def test_get_user_card_coerces_optional_ids_and_skips_invalid_exempt_values(self):
        fake_store = FakeStore()
        identity = {
            "uuid": "a878b04c-31a9-4b81-9c2c-3d0b19a2e1ad",
            "username": "alice",
            "system_id": "42",
            "telegram_id": "1001",
            "panel_user": None,
        }

        with patch.object(main, "store", fake_store), patch.object(
            main, "_resolve_user_identity", return_value=identity
        ):
            payload = main._get_user_card(identity["uuid"])

        self.assertEqual(payload["identity"]["system_id"], 42)
        self.assertEqual(payload["identity"]["telegram_id"], "1001")
        self.assertTrue(payload["flags"]["exempt_system_id"])
        self.assertTrue(payload["flags"]["exempt_telegram_id"])
        self.assertEqual(payload["review_cases"][0]["id"], 1)
        self.assertEqual(payload["analysis_events"][0]["id"], 10)
        self.assertEqual(payload["analysis_events"][0]["provider_evidence"]["provider_key"], "beeline")
        self.assertEqual(payload["usage_profile"]["ip_count"], 1)
        self.assertEqual(payload["usage_profile"]["provider_count"], 1)

    def test_build_user_export_payload_adds_metadata_and_counts(self):
        fake_store = FakeStore()
        identity = {
            "uuid": "a878b04c-31a9-4b81-9c2c-3d0b19a2e1ad",
            "username": "alice",
            "system_id": "42",
            "telegram_id": "1001",
            "panel_user": {"status": "active"},
        }

        payload = build_user_export_payload(fake_store, identity["uuid"], identity)

        self.assertEqual(payload["export_meta"]["identifier"], identity["uuid"])
        self.assertEqual(payload["export_meta"]["record_counts"]["review_cases"], 1)
        self.assertEqual(payload["export_meta"]["record_counts"]["analysis_events"], 1)
        self.assertEqual(payload["export_meta"]["record_counts"]["usage_profile_signals"], 0)
        self.assertEqual(payload["analysis_events"][0]["provider_evidence"]["service_type_hint"], "home")


class PanelClientTests(unittest.TestCase):
    def test_uuid_lookup_prefers_resolve_endpoint_and_falls_back_to_short_uuid_endpoint(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []
        uuid = "a878b04c-31a9-4b81-9c2c-3d0b19a2e1ad"

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == f"/api/users/by-short-uuid/{uuid}":
                return {"response": {"uuid": uuid, "username": "alice"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            payload = client.get_user_data(uuid)

        self.assertEqual(payload["uuid"], uuid)
        self.assertEqual(
            calls,
            [
                ("POST", "/api/users/resolve", {"uuid": uuid}),
                ("GET", f"/api/users/{uuid}", None),
                ("GET", f"/api/users/by-short-uuid/{uuid}", None),
            ],
        )

    def test_username_lookup_prefers_resolve_endpoint(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/users/resolve":
                return {"response": {"uuid": "uuid-1", "username": "alice"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            payload = client.get_user_data("alice")

        self.assertEqual(payload["username"], "alice")
        self.assertEqual(calls, [("POST", "/api/users/resolve", {"username": "alice"})])

    def test_repeat_lookup_uses_user_cache(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            return {"response": {"uuid": "uuid-1", "username": "alice"}}

        with patch.object(client, "_request", side_effect=fake_request):
            first = client.get_user_data("alice")
            second = client.get_user_data("alice")

        self.assertEqual(first["uuid"], "uuid-1")
        self.assertEqual(second["uuid"], "uuid-1")
        self.assertEqual(calls, [("POST", "/api/users/resolve", {"username": "alice"})])

    def test_numeric_typed_lookups_do_not_collide_between_system_and_telegram_ids(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/users/resolve" and body == {"id": 42}:
                return {"response": {"uuid": "uuid-system-42", "id": 42, "username": "system-user"}}
            if endpoint == "/api/users/resolve" and body == {"telegramId": "42"}:
                return {"response": {"uuid": "uuid-telegram-42", "telegramId": "42", "username": "tg-user"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            system_payload = client.get_user_data_by_system_id(42)
            telegram_payload = client.get_user_data_by_telegram_id(42)

        self.assertEqual(system_payload["uuid"], "uuid-system-42")
        self.assertEqual(telegram_payload["uuid"], "uuid-telegram-42")
        self.assertEqual(
            calls,
            [
                ("POST", "/api/users/resolve", {"id": 42}),
                ("POST", "/api/users/resolve", {"telegramId": "42"}),
            ],
        )

    def test_typed_lookup_cache_returns_same_identity_without_cross_type_reuse(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/users/resolve" and body == {"id": 7}:
                return {"response": {"uuid": "uuid-system-7", "id": 7}}
            if endpoint == "/api/users/resolve" and body == {"telegramId": "7"}:
                return {"response": {"uuid": "uuid-telegram-7", "telegramId": "7"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            first_system = client.get_user_data_by_system_id(7)
            second_system = client.get_user_data_by_system_id(7)
            first_telegram = client.get_user_data_by_telegram_id(7)
            second_telegram = client.get_user_data_by_telegram_id(7)

        self.assertEqual(first_system["uuid"], "uuid-system-7")
        self.assertEqual(second_system["uuid"], "uuid-system-7")
        self.assertEqual(first_telegram["uuid"], "uuid-telegram-7")
        self.assertEqual(second_telegram["uuid"], "uuid-telegram-7")
        self.assertEqual(
            calls,
            [
                ("POST", "/api/users/resolve", {"id": 7}),
                ("POST", "/api/users/resolve", {"telegramId": "7"}),
            ],
        )

    def test_username_lookup_falls_back_to_documented_username_endpoint_when_resolve_is_unavailable(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/users/by-username/alice":
                return {"response": {"uuid": "uuid-1", "username": "alice"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            payload = client.get_user_data("alice")

        self.assertEqual(payload["username"], "alice")
        self.assertEqual(
            [endpoint for _, endpoint, _ in calls],
            [
                "/api/users/resolve",
                "/api/users/resolve",
                "/api/users/by-username/alice",
            ],
        )

    def test_resolve_internal_squad_uuid_uses_exact_name(self):
        client = PanelClient("https://panel.example.com", "secret")

        with patch.object(
            client,
            "_request",
            return_value={
                "response": {
                    "internalSquads": [
                        {"uuid": "uuid-full", "name": "FULL"},
                        {"uuid": "uuid-limited", "name": "MOBILE_BLOCKED"},
                    ]
                }
            },
        ):
            squad_uuid = client.resolve_internal_squad_uuid("MOBILE_BLOCKED")

        self.assertEqual(squad_uuid, "uuid-limited")

    def test_apply_access_squad_updates_active_internal_squads(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/internal-squads":
                return {
                    "response": {
                        "internalSquads": [
                            {"uuid": "uuid-full", "name": "FULL"},
                            {"uuid": "uuid-limited", "name": "MOBILE_BLOCKED"},
                        ]
                    }
                }
            if endpoint == "/api/users":
                return {"response": {"uuid": "user-uuid"}}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            updated = client.apply_access_squad("user-uuid", "MOBILE_BLOCKED")

        self.assertTrue(updated)
        self.assertEqual(
            calls,
            [
                ("GET", "/api/internal-squads", None),
                (
                    "PATCH",
                    "/api/users",
                    {"uuid": "user-uuid", "activeInternalSquads": ["uuid-limited"]},
                ),
            ],
        )

    def test_update_user_traffic_limit_preserves_patch_shape(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            return {"response": {"uuid": "user-uuid", "trafficLimitBytes": 123}}

        with patch.object(client, "_request", side_effect=fake_request):
            updated = client.update_user_traffic_limit("user-uuid", 123, "NO_RESET")

        self.assertTrue(updated)
        self.assertEqual(
            calls,
            [
                (
                    "PATCH",
                    "/api/users",
                    {
                        "uuid": "user-uuid",
                        "trafficLimitBytes": 123,
                        "trafficLimitStrategy": "NO_RESET",
                    },
                )
            ],
        )

    def test_get_user_hwid_devices_uses_upstream_endpoint(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/hwid/devices/user-uuid":
                return {"response": [{"hwid": "hwid-1", "platform": "Android"}]}
            return None

        with patch.object(client, "_request", side_effect=fake_request):
            payload = client.get_user_hwid_devices("user-uuid")

        self.assertEqual(payload[0]["hwid"], "hwid-1")
        self.assertEqual([endpoint for _, endpoint, _ in calls], ["/api/hwid/devices/user-uuid"])

    def test_enrich_panel_user_devices_attaches_explicit_hwid_inventory(self):
        client = PanelClient("https://panel.example.com", "secret")
        with patch.object(
            client,
            "get_user_hwid_devices",
            return_value=[{"hwid": "hwid-1", "platform": "Android", "deviceModel": "Pixel 8"}],
        ):
            enriched = enrich_panel_user_devices(client, {"uuid": "user-uuid", "username": "alice"})

        self.assertEqual(enriched["hwidDevices"][0]["hwid"], "hwid-1")
        self.assertEqual(enriched["hwidDeviceCount"], 1)

    def test_enrich_panel_user_devices_fetches_hwid_inventory_even_with_generic_device_lists(self):
        client = PanelClient("https://panel.example.com", "secret")
        with patch.object(
            client,
            "get_user_hwid_devices",
            return_value=[{"hwid": "hwid-1", "platform": "Android", "deviceModel": "Pixel 8"}],
        ) as mocked_devices:
            enriched = enrich_panel_user_devices(
                client,
                {
                    "uuid": "user-uuid",
                    "username": "alice",
                    "devices": [{"deviceModel": "Legacy Device"}],
                },
            )

        mocked_devices.assert_called_once_with("user-uuid")
        self.assertEqual(enriched["hwidDevices"][0]["hwid"], "hwid-1")
        self.assertEqual(enriched["devices"][0]["deviceModel"], "Legacy Device")

    def test_get_user_traffic_stats_uses_bandwidth_stats_endpoint(self):
        client = PanelClient("https://panel.example.com", "secret")
        calls = []

        def fake_request(method, endpoint, body=None):
            calls.append((method, endpoint, body))
            return {"response": {"series": [{"timestamp": "2026-04-22T10:00:00", "node-a": 123}]}}

        with patch.object(client, "_request", side_effect=fake_request):
            payload = client.get_user_traffic_stats("user-uuid", start="2026-04-21", end="2026-04-23", top_nodes_limit=25)

        self.assertEqual(payload["series"][0]["node-a"], 123)
        self.assertEqual(
            [endpoint for _, endpoint, _ in calls],
            ["/api/bandwidth-stats/users/user-uuid?start=2026-04-21&end=2026-04-23&topNodesLimit=25"],
        )

    def test_enrich_panel_user_usage_context_attaches_traffic_stats(self):
        client = PanelClient("https://panel.example.com", "secret")
        with patch.object(client, "get_user_hwid_devices", return_value=[]), patch.object(
            client,
            "get_user_traffic_stats",
            return_value={"series": [{"timestamp": "2026-04-22T10:00:00", "node-a": 456}]},
        ):
            enriched = enrich_panel_user_usage_context(client, {"uuid": "user-uuid", "username": "alice"})

        self.assertEqual(enriched["usageProfileTrafficStats"]["series"][0]["node-a"], 456)


if __name__ == "__main__":
    unittest.main()
