import unittest
import asyncio
from unittest.mock import MagicMock, patch
from api.services.bedolaga import (
    ban_user_in_bedolaga,
    get_user_detail_by_tg_or_username
)
from api.services.modules import _resolve_remote_user, _analyze_event
from mobguard_platform import DecisionBundle
from mobguard_core.scoring import ScoringContext

class BedolagaSyncTests(unittest.TestCase):
    def test_ban_user_in_bedolaga_calls_proxy_action(self):
        container = MagicMock()
        with patch("api.services.bedolaga.proxy_bedolaga_action") as mock_proxy:
            mock_proxy.return_value = {"ok": True, "data": {"status": "banned"}}
            result = ban_user_in_bedolaga(container, "testuser", 60, "violator")
            
            mock_proxy.assert_called_once_with(
                container,
                path="/cabinet/admin/ban-system/ban",
                method="POST",
                payload={"username": "testuser", "minutes": 60, "reason": "violator"}
            )
            self.assertEqual(result, {"status": "banned"})

    def test_get_user_detail_by_tg_or_username_by_telegram_id(self):
        container = MagicMock()
        with patch("api.services.bedolaga._client_config", return_value=("https://bedolaga.local", "token", 10)), \
             patch("api.services.bedolaga._perform_request") as mock_req:
            mock_req.return_value = {"ok": True, "data": {"id": 123, "username": "testtg"}}
            
            res = get_user_detail_by_tg_or_username(container, 123456789)
            
            self.assertEqual(res, {"id": 123, "username": "testtg"})
            mock_req.assert_called_once_with(
                "https://bedolaga.local",
                "token",
                10,
                path="/users/by-telegram-id/123456789",
                method="GET"
            )

    def test_get_user_detail_by_tg_or_username_by_username(self):
        container = MagicMock()
        with patch("api.services.bedolaga._client_config", return_value=("https://bedolaga.local", "token", 10)), \
             patch("api.services.bedolaga._perform_request") as mock_req:
            mock_req.return_value = {"ok": True, "data": {"items": [{"id": 123, "username": "testusername"}]}}
            
            res = get_user_detail_by_tg_or_username(container, "testusername")
            
            self.assertEqual(res, {"id": 123, "username": "testusername"})
            mock_req.assert_called_once_with(
                "https://bedolaga.local",
                "token",
                10,
                path="/users",
                method="GET",
                payload={"search": "testusername", "limit": 10}
            )

    @patch("api.services.bedolaga.get_user_detail_by_tg_or_username")
    def test_resolve_remote_user_sets_vip_flag(self, mock_bedolaga):
        mock_bedolaga.return_value = {
            "subscription": {
                "connected_squads": ["VIP"]
            }
        }
        runtime = MagicMock()
        runtime.remnawave_client.enabled = True
        runtime.remnawave_client.get_user_data_by_username = MagicMock(return_value={"uuid": "u1", "username": "vipu"})
        
        payload = {"username": "vipu"}
        res = asyncio.run(_resolve_remote_user(runtime, payload))
        self.assertTrue(res.get("is_vip"))
        self.assertEqual(res.get("uuid"), "u1")

    @patch("api.services.modules.evaluate_mobile_network")
    def test_analyze_event_hwid_device_matched_adds_bonus(self, mock_eval):
        mock_bundle = DecisionBundle(
            ip="1.1.1.1",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-50,
            isp="Some ISP",
            details="Some ISP",
        )
        mock_eval.return_value = mock_bundle
        
        runtime = MagicMock()
        runtime.rules = {
            "settings": {
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "threshold_home": 15,
                "threshold_mobile": 60,
                "hwid_match_bonus": 30,
                "hwid_sharing_penalty": -60
            }
        }
        runtime.settings = runtime.rules["settings"]
        runtime.remnawave_client.enabled = True
        runtime.remnawave_client.get_user_hwid_devices = MagicMock(return_value=[{"hwid": "matching-hwid"}])
        
        user_data = {"uuid": "user-uuid"}
        payload = {"ip": "1.1.1.1", "client_device_id": "matching-hwid"}
        
        result_bundle = asyncio.run(_analyze_event(runtime, user_data, payload, persist_decision=False, persist_behavior_state=False))
        
        self.assertEqual(result_bundle.score, -20)
        self.assertEqual(result_bundle.verdict, "HOME")
        self.assertEqual(result_bundle.confidence_band, "PROBABLE_HOME")
        self.assertTrue(any(r.code == "hwid_match_bonus" for r in result_bundle.reasons))

    @patch("api.services.modules.evaluate_mobile_network")
    def test_analyze_event_hwid_new_device_on_non_mobile_adds_penalty(self, mock_eval):
        mock_bundle = DecisionBundle(
            ip="1.1.1.1",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            isp="Some ISP",
            details="Some ISP",
        )
        mock_eval.return_value = mock_bundle
        
        runtime = MagicMock()
        runtime.rules = {
            "settings": {
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "threshold_home": 15,
                "threshold_mobile": 60,
                "hwid_match_bonus": 30,
                "hwid_sharing_penalty": -60
            }
        }
        runtime.settings = runtime.rules["settings"]
        runtime.remnawave_client.enabled = True
        runtime.remnawave_client.get_user_hwid_devices = MagicMock(return_value=[{"hwid": "old-hwid"}])
        
        user_data = {"uuid": "user-uuid"}
        payload = {"ip": "1.1.1.1", "client_device_id": "new-hwid"}
        
        result_bundle = asyncio.run(_analyze_event(runtime, user_data, payload, persist_decision=False, persist_behavior_state=False))
        
        self.assertEqual(result_bundle.score, -80)
        self.assertEqual(result_bundle.verdict, "HOME")
        self.assertEqual(result_bundle.confidence_band, "HIGH_HOME")
        self.assertIn("sharing_hwid_limit_exceeded", result_bundle.hard_flags)
        self.assertTrue(any(r.code == "sharing_hwid_limit_exceeded" for r in result_bundle.reasons))
