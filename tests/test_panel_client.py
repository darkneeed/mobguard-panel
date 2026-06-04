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
