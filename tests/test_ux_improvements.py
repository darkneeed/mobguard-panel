from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.app import create_app
from api.context import APIContainer
from api.permissions import PERMISSION_RULES_READ, PERMISSION_MODULES_READ

# Force sqlite mode for tests
os.environ["PYTEST_CURRENT_TEST"] = "true"

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def client_and_container():
    app = create_app()
    container = app.state.container
    
    # Bypass authorization by overriding get_session
    from api.dependencies import get_session
    app.dependency_overrides[get_session] = lambda: {
        "role": "owner",
        "permissions": ["rules.read", "rules.write", "modules.read", "modules.write"],
        "telegram_id": 12345,
        "totp_verified": True
    }
    
    client = TestClient(app)
    return client, container

def test_config_health_endpoint(client_and_container):
    client, container = client_and_container
    
    response = client.get("/admin/settings/config-health")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert len(data["checks"]) == 6
    
    # Verify check structures
    for check in data["checks"]:
        assert "key" in check
        assert "status" in check
        assert "label" in check
        assert "detail" in check
        assert "link" in check
        assert check["status"] in ("ok", "warn", "error")

@pytest.mark.anyio
async def test_asn_lookup_endpoint(client_and_container):
    client, container = client_and_container
    
    # Mock lookup_ip_multi_source to avoid network requests
    with patch("api.routers.tools.asn_lookup_service.lookup_ip_multi_source") as mock_lookup:
        mock_lookup.return_value = {
            "ip": "1.1.1.1",
            "asn": 13335,
            "isp": "Cloudflare",
            "country": "US",
            "is_mobile": False,
            "network_type": "datacenter",
            "sources_count": 5,
            "in_lists": {
                "pure_mobile_asns": False,
                "pure_home_asns": False,
                "mixed_asns": False,
                "exclude_isp_keywords": True
            },
            "cached": False,
            "cached_at": "2026-06-10T00:00:00"
        }
        
        response = client.post(
            "/admin/tools/asn-lookup",
            json={"ip": "1.1.1.1", "force": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["asn"] == 13335
        assert data["network_type"] == "datacenter"
        assert data["in_lists"]["exclude_isp_keywords"] is True

def test_remnawave_inbounds_endpoint(client_and_container):
    client, container = client_and_container
    
    # Mock PanelClient get_inbounds
    with patch("api.services.runtime_state.panel_client") as mock_panel_client_getter:
        mock_client = MagicMock()
        mock_client.get_inbounds.return_value = [
            {"uuid": "111", "profileUuid": "222", "tag": "vless-mobile", "type": "vless"}
        ]
        mock_panel_client_getter.return_value = mock_client
        
        response = client.get("/admin/tools/remnawave-inbounds")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert len(data["inbounds"]) == 1
        assert data["inbounds"][0]["tag"] == "vless-mobile"
