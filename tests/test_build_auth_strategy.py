"""Tests for auth-strategy selection from config."""

import pytest

from mcp_superset.auth import (
    CookieAuthManager,
    JwtAuthManager,
    build_auth_strategy,
)

BASE = "https://superset.example.com"


def test_selects_cookie_when_cookie_set():
    strategy = build_auth_strategy(BASE, "cookieval", "session", None, None, "db")
    assert isinstance(strategy, CookieAuthManager)
    assert strategy.cookie_value == "cookieval"


def test_selects_jwt_when_credentials_set():
    strategy = build_auth_strategy(BASE, None, "session", "admin", "pw", "db")
    assert isinstance(strategy, JwtAuthManager)


def test_cookie_takes_precedence_over_credentials():
    strategy = build_auth_strategy(BASE, "cookieval", "session", "admin", "pw", "db")
    assert isinstance(strategy, CookieAuthManager)


def test_custom_cookie_name_passed_through():
    strategy = build_auth_strategy(BASE, "cookieval", "my_sess", None, None, "db")
    assert isinstance(strategy, CookieAuthManager)
    assert strategy.cookie_name == "my_sess"


def test_empty_base_url_raises():
    with pytest.raises(ValueError, match="SUPERSET_BASE_URL"):
        build_auth_strategy("", "cookieval", "session", None, None, "db")


def test_no_auth_configured_raises():
    with pytest.raises(ValueError, match="SUPERSET_SESSION_COOKIE"):
        build_auth_strategy(BASE, None, "session", None, None, "db")
