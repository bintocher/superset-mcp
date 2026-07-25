"""Tests for the session-cookie auth strategy."""

import httpx
import respx

from mcp_superset.auth import CookieAuthManager

BASE = "https://superset.example.com"


async def test_apply_auth_sets_cookie_header():
    mgr = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    headers: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        await mgr.apply_auth(client, headers)
    assert headers["Cookie"] == "session=abc123"


async def test_apply_auth_respects_custom_cookie_name():
    mgr = CookieAuthManager(base_url=BASE, cookie_value="abc123", cookie_name="my_sess")
    headers: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        await mgr.apply_auth(client, headers)
    assert headers["Cookie"] == "my_sess=abc123"


@respx.mock
async def test_get_csrf_token_uses_cookie_and_caches():
    route = respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(
        return_value=httpx.Response(200, json={"result": "csrf-xyz"})
    )
    mgr = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    async with httpx.AsyncClient() as client:
        token = await mgr.get_csrf_token(client)
        token_again = await mgr.get_csrf_token(client)

    assert token == "csrf-xyz"
    assert token_again == "csrf-xyz"
    assert route.call_count == 1  # cached, fetched once
    assert route.calls.last.request.headers["Cookie"] == "session=abc123"


def test_invalidate_is_noop_but_invalidate_csrf_clears():
    mgr = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    mgr._csrf_token = "cached"
    mgr.invalidate()
    assert mgr._csrf_token == "cached"  # session cannot be renewed; CSRF untouched
    mgr.invalidate_csrf()
    assert mgr._csrf_token is None


def test_auth_failure_hint_mentions_env_var():
    mgr = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    assert "SUPERSET_SESSION_COOKIE" in mgr.auth_failure_hint
