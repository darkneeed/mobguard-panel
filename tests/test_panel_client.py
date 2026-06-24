import json
import unittest
from unittest.mock import patch

from mobguard_platform.panel_client import PanelClient


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class PanelClientBaseUrlTests(unittest.TestCase):
    def test_nodes_request_uses_single_api_prefix_for_root_base_url(self):
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=5):  # type: ignore[no-untyped-def]
            seen_urls.append(request.full_url)
            return _FakeResponse({"response": {"items": []}})

        with patch("mobguard_platform.panel_client.urlopen", side_effect=fake_urlopen):
            client = PanelClient("https://panel.example.com", "token")
            client.get_nodes_online_usage()

        self.assertEqual(seen_urls, ["https://panel.example.com/api/nodes"])

    def test_nodes_request_uses_single_api_prefix_for_api_base_url(self):
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=5):  # type: ignore[no-untyped-def]
            seen_urls.append(request.full_url)
            return _FakeResponse({"response": {"items": []}})

        with patch("mobguard_platform.panel_client.urlopen", side_effect=fake_urlopen):
            client = PanelClient("https://panel.example.com/api", "token")
            client.get_nodes_online_usage()

        self.assertEqual(seen_urls, ["https://panel.example.com/api/nodes"])


class PanelClientIPControlHWIDTests(unittest.TestCase):
    def test_create_hwid_device_hits_correct_endpoint(self):
        seen_requests: list[tuple[str, str, dict]] = []

        def fake_urlopen(request, timeout=5):
            body = None
            if request.data:
                body = json.loads(request.data.decode("utf-8"))
            seen_requests.append((request.method, request.full_url, body))
            return _FakeResponse({"response": {"ok": True}})

        with patch("mobguard_platform.panel_client.urlopen", side_effect=fake_urlopen):
            client = PanelClient("https://panel.example.com", "token")
            success = client.create_hwid_device("user-uuid", "hwid-value")

        self.assertTrue(success)
        self.assertEqual(len(seen_requests), 1)
        method, url, body = seen_requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://panel.example.com/api/hwid/devices")
        self.assertEqual(body, {"userUuid": "user-uuid", "hwid": "hwid-value"})

    def test_drop_user_connections_hits_correct_endpoint(self):
        seen_requests: list[tuple[str, str, dict]] = []

        def fake_urlopen(request, timeout=5):
            body = None
            if request.data:
                body = json.loads(request.data.decode("utf-8"))
            seen_requests.append((request.method, request.full_url, body))
            return _FakeResponse({"response": {"ok": True}})

        with patch("mobguard_platform.panel_client.urlopen", side_effect=fake_urlopen):
            client = PanelClient("https://panel.example.com", "token")
            success = client.drop_user_connections("user-uuid")

        self.assertTrue(success)
        self.assertEqual(len(seen_requests), 1)
        method, url, body = seen_requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://panel.example.com/api/ip-control/drop-connections")
        self.assertEqual(body, {
            "dropBy": {
                "by": "userUuids",
                "userUuids": ["user-uuid"]
            },
            "targetNodes": {
                "target": "allNodes"
            }
        })

