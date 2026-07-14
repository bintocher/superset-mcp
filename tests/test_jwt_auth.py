"""Tests for the JWT auth strategy."""

import time

import httpx

from mcp_superset.auth import JwtAuthManager


async def test_apply_auth_sets_bearer_header():
    mgr = JwtAuthManager(base_url="https://superset.example.com", username="u", password="p")
    mgr._access_token = "tok123"
    mgr._token_expires_at = time.time() + 900

    headers: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        await mgr.apply_auth(client, headers)

    assert headers["Authorization"] == "Bearer tok123"


def test_auth_failure_hint_is_none():
    mgr = JwtAuthManager(base_url="https://superset.example.com", username="u", password="p")
    assert mgr.auth_failure_hint is None
