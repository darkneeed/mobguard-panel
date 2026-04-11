import sqlite3
import unittest
from unittest.mock import patch

from api import main
from api.services.runtime_state import build_user_export_payload
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
        self.assertEqual(payload["analysis_events"][0]["provider_evidence"]["service_type_hint"], "home")


class PanelClientTests(unittest.TestCase):
    def test_uuid_lookup_falls_back_to_short_uuid_endpoint(self):
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
            [endpoint for _, endpoint, _ in calls],
            [
                f"/api/users/{uuid}",
                f"/api/users/by-short-uuid/{uuid}",
            ],
        )

    def test_username_lookup_prefers_documented_username_endpoint(self):
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
        self.assertEqual([endpoint for _, endpoint, _ in calls], ["/api/users/by-username/alice"])

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


if __name__ == "__main__":
    unittest.main()
