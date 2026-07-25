"""Tests for SupersetClient auth wiring across strategies."""

import httpx
import pytest
import respx

from mcp_superset.auth import CookieAuthManager, JwtAuthManager
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


@respx.mock
async def test_mutating_request_sends_cookie_and_csrf():
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(return_value=httpx.Response(200, json={"result": "csrf-xyz"}))
    respx.post(f"{BASE}/api/v1/chart/").mock(return_value=httpx.Response(200, json={"id": 1}))
    auth = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        await client.post("/api/v1/chart/", json_data={"slice_name": "x"})
    finally:
        await client.close()

    request = respx.calls.last.request
    assert request.headers["Cookie"] == "session=abc123"
    assert request.headers["X-CSRFToken"] == "csrf-xyz"


@respx.mock
async def test_post_form_keeps_multipart_content_type():
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(return_value=httpx.Response(200, json={"result": "csrf-xyz"}))
    respx.post(f"{BASE}/api/v1/database/import/").mock(return_value=httpx.Response(200, json={"message": "OK"}))
    auth = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        await client.post_form("/api/v1/database/import/", files={"formData": ("f.zip", b"x")})
    finally:
        await client.close()

    request = respx.calls.last.request
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    assert request.headers["X-CSRFToken"] == "csrf-xyz"


@respx.mock
async def test_failed_csrf_fetch_raises_superset_error_with_hint():
    """A rejected session must not leak a raw httpx.HTTPStatusError to callers."""
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(
        return_value=httpx.Response(401, json={"msg": "Unauthorized"})
    )
    auth = CookieAuthManager(base_url=BASE, cookie_value="stale")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        with pytest.raises(SupersetAPIError) as exc_info:
            await client.post("/api/v1/chart/", json_data={"slice_name": "x"})
    finally:
        await client.close()

    assert exc_info.value.status_code == 401
    assert "SUPERSET_SESSION_COOKIE" in exc_info.value.detail


@respx.mock
async def test_failed_login_raises_superset_error():
    """A wrong password must surface as SupersetAPIError, not a raw httpx error."""
    respx.post(f"{BASE}/api/v1/security/login").mock(return_value=httpx.Response(401, json={"message": "Bad login"}))
    auth = JwtAuthManager(base_url=BASE, username="u", password="wrong")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        with pytest.raises(SupersetAPIError) as exc_info:
            await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert exc_info.value.status_code == 401
    assert "Bad login" in exc_info.value.detail


@respx.mock
async def test_jwt_retries_once_after_401():
    respx.post(f"{BASE}/api/v1/security/login").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok1", "refresh_token": "ref1"}),
            httpx.Response(200, json={"access_token": "tok2", "refresh_token": "ref2"}),
        ]
    )
    chart = respx.get(f"{BASE}/api/v1/chart/").mock(
        side_effect=[
            httpx.Response(401, json={"msg": "Token expired"}),
            httpx.Response(200, json={"result": [], "count": 0}),
        ]
    )
    auth = JwtAuthManager(base_url=BASE, username="u", password="p")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert chart.call_count == 2
    assert chart.calls[0].request.headers["Authorization"] == "Bearer tok1"
    assert chart.calls[1].request.headers["Authorization"] == "Bearer tok2"
