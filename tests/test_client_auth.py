"""Tests for SupersetClient auth wiring across strategies."""

import httpx
import pytest
import respx

from mcp_superset.auth import CookieAuthManager
from mcp_superset.client import SupersetAPIError, SupersetClient

BASE = "https://superset.example.com"


@respx.mock
async def test_client_sends_cookie_on_get():
    respx.get(f"{BASE}/api/v1/chart/").mock(return_value=httpx.Response(200, json={"result": [], "count": 0}))
    auth = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert respx.calls.last.request.headers["Cookie"] == "session=abc123"


@respx.mock
async def test_client_persistent_401_includes_cookie_hint():
    respx.get(f"{BASE}/api/v1/chart/").mock(return_value=httpx.Response(401, json={"msg": "Unauthorized"}))
    auth = CookieAuthManager(base_url=BASE, cookie_value="stale")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        with pytest.raises(SupersetAPIError) as exc_info:
            await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert "SUPERSET_SESSION_COOKIE" in exc_info.value.detail


@respx.mock
async def test_post_form_persistent_401_includes_cookie_hint():
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(return_value=httpx.Response(200, json={"result": "csrf-xyz"}))
    respx.post(f"{BASE}/api/v1/database/import/").mock(return_value=httpx.Response(401, json={"msg": "Unauthorized"}))
    auth = CookieAuthManager(base_url=BASE, cookie_value="stale")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        with pytest.raises(SupersetAPIError) as exc_info:
            await client.post_form("/api/v1/database/import/", files={"formData": ("f.zip", b"x")})
    finally:
        await client.close()

    assert "SUPERSET_SESSION_COOKIE" in exc_info.value.detail
