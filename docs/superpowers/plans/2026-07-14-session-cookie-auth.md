# Session-cookie Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the MCP server authenticate to Superset with a static browser session cookie as an SSO alternative to the username/password JWT flow.

**Architecture:** Introduce an `AuthStrategy` interface in `auth.py` with two implementations — `JwtAuthManager` (the existing logic, renamed) and a new `CookieAuthManager`. `SupersetClient` depends on the interface and calls `apply_auth()`/`get_csrf_token()`. A pure `build_auth_strategy()` factory auto-selects the mode from config; `server.py` wires env vars into it.

**Tech Stack:** Python 3.12+, httpx (async), fastmcp, python-dotenv. Tests via pytest + pytest-asyncio + respx.

## Global Constraints

- Python `>=3.12` (`requires-python` in `pyproject.toml`).
- Ruff: line-length 120, lint rules `E, F, I, UP` — code must pass `uv run ruff check src/` and `uv run ruff format --check src/`.
- Runtime deps stay limited to `fastmcp`, `httpx`, `pydantic`, `python-dotenv`. New libs go under `[project.optional-dependencies].dev` only.
- Superset CSRF endpoint: `GET /api/v1/security/csrf_token/`, returns `{"result": "<token>"}`.
- Default cookie name is `session` (Flask default).
- Tools under `src/mcp_superset/tools/` import the ready-made `superset_client` and must NOT be modified.

---

### Task 1: Test infrastructure + `AuthStrategy` interface + rename to `JwtAuthManager`

Set up pytest, define the `AuthStrategy` Protocol, and rename the existing `AuthManager` to `JwtAuthManager` with an `apply_auth()` method and an `auth_failure_hint` property. Behavior of the JWT flow is unchanged. `server.py` and `client.py` are updated only to keep the repo running.

**Files:**
- Modify: `pyproject.toml` (add dev deps + pytest config)
- Modify: `src/mcp_superset/auth.py` (add Protocol, rename class, add methods)
- Modify: `src/mcp_superset/server.py:12,36` (import + construct `JwtAuthManager`)
- Modify: `src/mcp_superset/client.py:7,17` (type hint only, still uses existing methods)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_jwt_auth.py`

**Interfaces:**
- Produces:
  - `class AuthStrategy(Protocol)` with attribute `auth_failure_hint: str | None`, and methods `async apply_auth(client, headers) -> None`, `async get_csrf_token(client) -> str`, `invalidate() -> None`, `invalidate_csrf() -> None`.
  - `class JwtAuthManager(base_url: str, username: str | None, password: str | None, provider: str = "db")` — same public methods as the old `AuthManager` plus `async apply_auth(client, headers)` and property `auth_failure_hint` (returns `None`).

- [ ] **Step 1: Add dev deps and pytest config**

Edit `pyproject.toml`. Replace the `dev` extras block:

```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.8",
    "mypy>=1.13",
    "twine>=6.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]
```

Then append at the end of the file:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Install dev deps**

Run: `uv sync --extra dev`
Expected: resolves and installs pytest, pytest-asyncio, respx.

- [ ] **Step 3: Create test package files**

Create `tests/__init__.py`:

```python
```

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures for mcp-superset tests."""
```

- [ ] **Step 4: Write the failing test**

Create `tests/test_jwt_auth.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_jwt_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'JwtAuthManager'`.

- [ ] **Step 6: Add the `AuthStrategy` Protocol to `auth.py`**

At the top of `src/mcp_superset/auth.py`, replace the imports and add the Protocol above the class:

```python
"""Authentication strategies for Superset — JWT and session cookie."""

import time
from typing import Protocol

import httpx


class AuthStrategy(Protocol):
    """Common interface for Superset authentication schemes."""

    auth_failure_hint: str | None

    async def apply_auth(self, client: httpx.AsyncClient, headers: dict[str, str]) -> None:
        """Inject auth (Authorization or Cookie) into request headers."""
        ...

    async def get_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid CSRF token, fetching one if necessary."""
        ...

    def invalidate(self) -> None:
        """Reset cached auth state, forcing re-authentication."""
        ...

    def invalidate_csrf(self) -> None:
        """Reset only the cached CSRF token."""
        ...
```

- [ ] **Step 7: Rename the class and add the new members**

In `src/mcp_superset/auth.py`, rename `class AuthManager:` to `class JwtAuthManager:`. Update its docstring first line to `"""Manages JWT authentication with Superset REST API."""`. Then add these two members inside the class (place `apply_auth` right after `get_token`, and the property near the top after `__init__`):

```python
    @property
    def auth_failure_hint(self) -> str | None:
        """No special hint — a JWT can be re-obtained via login/refresh."""
        return None

    async def apply_auth(self, client: httpx.AsyncClient, headers: dict[str, str]) -> None:
        """Set the Authorization header with a valid Bearer token.

        Args:
            client: httpx async client used for HTTP requests.
            headers: Mutable header dict to inject the token into.
        """
        token = await self.get_token(client)
        headers["Authorization"] = f"Bearer {token}"
```

- [ ] **Step 8: Update `server.py` to the new class name**

In `src/mcp_superset/server.py`:
- Line 12: change `from mcp_superset.auth import AuthManager` → `from mcp_superset.auth import JwtAuthManager`
- Line 36: change `auth_manager = AuthManager(` → `auth_manager = JwtAuthManager(`

- [ ] **Step 9: Update `client.py` type hint**

In `src/mcp_superset/client.py`:
- Line 7: change `from mcp_superset.auth import AuthManager` → `from mcp_superset.auth import AuthStrategy`
- Line 17: change the signature `def __init__(self, auth_manager: AuthManager, base_url: str):` → `def __init__(self, auth_manager: AuthStrategy, base_url: str):`

(The client still calls `get_token`/`get_csrf_token` for now — those still exist on `JwtAuthManager`, so it runs.)

- [ ] **Step 10: Run tests to verify they pass**

Run: `uv run pytest tests/test_jwt_auth.py -v`
Expected: PASS (2 passed).

- [ ] **Step 11: Lint**

Run: `uv run ruff check src/ && uv run ruff format --check src/`
Expected: no errors.

- [ ] **Step 12: Commit**

```bash
git add pyproject.toml uv.lock src/mcp_superset/auth.py src/mcp_superset/server.py src/mcp_superset/client.py tests/
git commit -m "refactor: introduce AuthStrategy interface, rename AuthManager to JwtAuthManager"
```

---

### Task 2: `CookieAuthManager`

Add the session-cookie auth strategy: sends `Cookie: <name>=<value>`, fetches CSRF using the cookie, and exposes the SSO-expiry hint.

**Files:**
- Modify: `src/mcp_superset/auth.py` (append new class)
- Test: `tests/test_cookie_auth.py`

**Interfaces:**
- Consumes: `AuthStrategy` protocol from Task 1.
- Produces: `class CookieAuthManager(base_url: str, cookie_value: str, cookie_name: str = "session")` implementing `AuthStrategy`. `apply_auth` sets `headers["Cookie"] = f"{cookie_name}={cookie_value}"`. `get_csrf_token` GETs `/api/v1/security/csrf_token/` with the cookie and caches `result`. `invalidate()` is a no-op. `invalidate_csrf()` clears the cache. `auth_failure_hint` returns the SSO refresh message.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cookie_auth.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cookie_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'CookieAuthManager'`.

- [ ] **Step 3: Implement `CookieAuthManager`**

Append to `src/mcp_superset/auth.py`:

```python
class CookieAuthManager:
    """Authenticates with Superset using a static session cookie (SSO).

    Sends the browser session cookie on every request and fetches CSRF
    tokens authenticated by that cookie. The session cannot be renewed
    server-side — when it expires the operator must supply a fresh cookie.
    """

    def __init__(self, base_url: str, cookie_value: str, cookie_name: str = "session"):
        self.base_url = base_url.rstrip("/")
        self.cookie_value = cookie_value
        self.cookie_name = cookie_name
        self._csrf_token: str | None = None

    @property
    def auth_failure_hint(self) -> str | None:
        """Explain the likely cause of a 401 in cookie mode."""
        return "Session cookie rejected or expired — refresh SUPERSET_SESSION_COOKIE from your browser."

    def _cookie_header(self) -> str:
        return f"{self.cookie_name}={self.cookie_value}"

    async def apply_auth(self, client: httpx.AsyncClient, headers: dict[str, str]) -> None:
        """Set the Cookie header with the session cookie.

        Args:
            client: httpx async client (unused; kept for interface parity).
            headers: Mutable header dict to inject the cookie into.
        """
        headers["Cookie"] = self._cookie_header()

    async def get_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid CSRF token, fetching one via the cookie if needed.

        Args:
            client: httpx async client used for HTTP requests.

        Returns:
            A CSRF token string.
        """
        if self._csrf_token:
            return self._csrf_token
        url = f"{self.base_url}/api/v1/security/csrf_token/"
        headers = {"Cookie": self._cookie_header(), "Referer": self.base_url}
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        self._csrf_token = resp.json()["result"]
        return self._csrf_token

    def invalidate(self) -> None:
        """No-op: an expired SSO session cannot be renewed server-side."""

    def invalidate_csrf(self) -> None:
        """Reset only the cached CSRF token."""
        self._csrf_token = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cookie_auth.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/ && uv run ruff format --check src/`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_superset/auth.py tests/test_cookie_auth.py
git commit -m "feat: add CookieAuthManager for session-cookie auth"
```

---

### Task 3: Client uses `apply_auth` and surfaces the auth hint

Switch `SupersetClient` from building the `Authorization` header by hand to calling `auth.apply_auth()`, in both `_get_headers` and `post_form`. On a 401 that persists after the retry, append the strategy's `auth_failure_hint` to the error.

**Files:**
- Modify: `src/mcp_superset/client.py` (`_get_headers`, `post_form`, `_request` error block)
- Test: `tests/test_client_auth.py`

**Interfaces:**
- Consumes: `AuthStrategy.apply_auth`, `AuthStrategy.get_csrf_token`, `AuthStrategy.auth_failure_hint`, `CookieAuthManager`, `JwtAuthManager`, `SupersetAPIError`.
- Produces: no new public symbols; `SupersetClient` behavior now works for both strategies.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_auth.py`:

```python
"""Tests for SupersetClient auth wiring across strategies."""

import httpx
import pytest
import respx

from mcp_superset.auth import CookieAuthManager
from mcp_superset.client import SupersetClient, SupersetAPIError

BASE = "https://superset.example.com"


@respx.mock
async def test_client_sends_cookie_on_get():
    respx.get(f"{BASE}/api/v1/chart/").mock(
        return_value=httpx.Response(200, json={"result": [], "count": 0})
    )
    auth = CookieAuthManager(base_url=BASE, cookie_value="abc123")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert respx.calls.last.request.headers["Cookie"] == "session=abc123"


@respx.mock
async def test_client_persistent_401_includes_cookie_hint():
    respx.get(f"{BASE}/api/v1/chart/").mock(
        return_value=httpx.Response(401, json={"msg": "Unauthorized"})
    )
    auth = CookieAuthManager(base_url=BASE, cookie_value="stale")
    client = SupersetClient(auth_manager=auth, base_url=BASE)
    try:
        with pytest.raises(SupersetAPIError) as exc_info:
            await client.get("/api/v1/chart/")
    finally:
        await client.close()

    assert "SUPERSET_SESSION_COOKIE" in exc_info.value.detail
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_auth.py -v`
Expected: FAIL — first test fails because `_get_headers` calls `self.auth.get_token(...)`, which `CookieAuthManager` does not have (`AttributeError`).

- [ ] **Step 3: Rewrite `_get_headers` to use `apply_auth`**

In `src/mcp_superset/client.py`, replace the body of `_get_headers` (currently lines ~25-44):

```python
    async def _get_headers(self, need_csrf: bool = False) -> dict[str, str]:
        """Build request headers with auth and optionally a CSRF token.

        Args:
            need_csrf: True for mutating requests (POST/PUT/DELETE).

        Returns:
            Dictionary of HTTP headers.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": self.base_url,
        }
        await self.auth.apply_auth(self._client, headers)
        if need_csrf:
            csrf = await self.auth.get_csrf_token(self._client)
            headers["X-CSRFToken"] = csrf
        return headers
```

- [ ] **Step 4: Add the auth hint to the `_request` error block**

In `src/mcp_superset/client.py`, in `_request`, replace the final error block (currently lines ~108-118):

```python
        if resp.status_code >= 400:
            error_detail = ""
            try:
                error_body = resp.json()
                error_detail = error_body.get("message", "") or error_body.get("errors", str(error_body))
            except Exception:
                error_detail = resp.text[:500]
            if resp.status_code == 401 and self.auth.auth_failure_hint:
                error_detail = f"{error_detail} — {self.auth.auth_failure_hint}".lstrip(" —")
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API {method} {endpoint}: {resp.status_code} — {error_detail}",
            )
```

- [ ] **Step 5: Rewrite `post_form` auth to use `apply_auth`**

In `src/mcp_superset/client.py`, in `post_form`, replace the header construction (currently lines ~234-240):

```python
        url = f"{self.base_url}{endpoint}"
        headers = {"Referer": self.base_url}
        await self.auth.apply_auth(self._client, headers)
        csrf = await self.auth.get_csrf_token(self._client)
        headers["X-CSRFToken"] = csrf
```

And in the 401-retry block of `post_form` (currently lines ~247-252), replace:

```python
        if resp.status_code == 401:
            self.auth.invalidate()
            await self.auth.apply_auth(self._client, headers)
            headers["X-CSRFToken"] = await self.auth.get_csrf_token(self._client)
            resp = await self._client.post(
                url=url,
                headers=headers,
                files=files,
                data=data or {},
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests, including Task 1 & 2 tests).

- [ ] **Step 7: Lint**

Run: `uv run ruff check src/ && uv run ruff format --check src/`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/mcp_superset/client.py tests/test_client_auth.py
git commit -m "refactor: client uses apply_auth and surfaces cookie-expiry hint"
```

---

### Task 4: `build_auth_strategy` factory + `server.py` wiring

Add a pure factory that selects the strategy from config, then wire `server.py` to read the new env vars and call it.

**Files:**
- Modify: `src/mcp_superset/auth.py` (append `build_auth_strategy`)
- Modify: `src/mcp_superset/server.py` (env vars, validation, construction)
- Test: `tests/test_build_auth_strategy.py`

**Interfaces:**
- Consumes: `JwtAuthManager`, `CookieAuthManager` from earlier tasks.
- Produces: `def build_auth_strategy(base_url: str, session_cookie: str | None, cookie_name: str, username: str | None, password: str | None, provider: str) -> AuthStrategy`. Raises `ValueError` when `base_url` is empty or neither auth method is fully configured. Cookie mode takes precedence over creds when both are present.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build_auth_strategy.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_auth_strategy.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_auth_strategy'`.

- [ ] **Step 3: Implement the factory**

Append to `src/mcp_superset/auth.py`:

```python
def build_auth_strategy(
    base_url: str,
    session_cookie: str | None,
    cookie_name: str,
    username: str | None,
    password: str | None,
    provider: str,
) -> AuthStrategy:
    """Select and build the auth strategy from configuration.

    Cookie mode is used when a session cookie is supplied; otherwise the
    username/password JWT flow is used. Raises if neither is configured.

    Args:
        base_url: Superset instance URL.
        session_cookie: Session cookie value, or None.
        cookie_name: Cookie name (defaults handled by the caller).
        username: Superset username, or None.
        password: Superset password, or None.
        provider: Auth provider for JWT login (e.g. "db", "ldap").

    Returns:
        A configured AuthStrategy.

    Raises:
        ValueError: If base_url is empty or no auth method is fully configured.
    """
    if not base_url:
        raise ValueError("SUPERSET_BASE_URL is required. Set it in .env or environment variables.")
    if session_cookie:
        return CookieAuthManager(base_url, session_cookie, cookie_name)
    if username and password:
        return JwtAuthManager(base_url, username, password, provider)
    raise ValueError(
        "No authentication configured. Set SUPERSET_SESSION_COOKIE (SSO), "
        "or both SUPERSET_USERNAME and SUPERSET_PASSWORD."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_auth_strategy.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Wire `server.py` to the factory**

In `src/mcp_superset/server.py`, replace the config + validation + construction block (currently lines 12, 24-41). First fix the import on line 12:

```python
from mcp_superset.auth import build_auth_strategy
```

Then replace lines 24-41 (from `# Configuration` through the `AuthManager(...)` construction) with:

```python
# Configuration
SUPERSET_BASE_URL = os.getenv("SUPERSET_BASE_URL", "")
SUPERSET_USERNAME = os.getenv("SUPERSET_USERNAME")
SUPERSET_PASSWORD = os.getenv("SUPERSET_PASSWORD")
SUPERSET_AUTH_PROVIDER = os.getenv("SUPERSET_AUTH_PROVIDER", "db")
SUPERSET_SESSION_COOKIE = os.getenv("SUPERSET_SESSION_COOKIE")
SUPERSET_SESSION_COOKIE_NAME = os.getenv("SUPERSET_SESSION_COOKIE_NAME", "session")

# Initialize auth strategy (cookie mode if a session cookie is set, else JWT)
auth_manager = build_auth_strategy(
    base_url=SUPERSET_BASE_URL,
    session_cookie=SUPERSET_SESSION_COOKIE,
    cookie_name=SUPERSET_SESSION_COOKIE_NAME,
    username=SUPERSET_USERNAME,
    password=SUPERSET_PASSWORD,
    provider=SUPERSET_AUTH_PROVIDER,
)
```

(This removes the old standalone `if not SUPERSET_BASE_URL` / `if not SUPERSET_USERNAME` checks — `build_auth_strategy` now raises with clearer messages.)

- [ ] **Step 6: Smoke-test server import in cookie mode**

Run:
```bash
SUPERSET_BASE_URL=https://superset.example.com \
SUPERSET_SESSION_COOKIE=dummycookie \
SUPERSET_MCP_ENV_FILE=/dev/null \
uv run python -c "import mcp_superset.server as s; print(type(s.auth_manager).__name__)"
```
Expected: prints `CookieAuthManager`.

- [ ] **Step 7: Run full test suite + lint**

Run: `uv run pytest tests/ -v && uv run ruff check src/ && uv run ruff format --check src/`
Expected: all pass, no lint errors.

- [ ] **Step 8: Commit**

```bash
git add src/mcp_superset/auth.py src/mcp_superset/server.py tests/test_build_auth_strategy.py
git commit -m "feat: auto-select cookie/JWT auth from config in server wiring"
```

---

### Task 5: Documentation

Document the new mode in the env example and both READMEs.

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `README_RU.md`

**Interfaces:**
- Consumes: env vars `SUPERSET_SESSION_COOKIE`, `SUPERSET_SESSION_COOKIE_NAME` from Task 4.
- Produces: docs only.

- [ ] **Step 1: Update `.env.example`**

Replace the contents of `.env.example` with:

```bash
# Superset instance URL (without trailing slash)
SUPERSET_BASE_URL=https://superset.example.com

# ── Authentication: choose ONE mode ──────────────────────────

# Mode A — JWT login (username/password). Used when no session cookie is set.
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=your_password
# Authentication provider (db, ldap)
SUPERSET_AUTH_PROVIDER=db

# Mode B — Session cookie (SSO/OAuth). If set, this takes precedence over
# the username/password above. Paste the Superset session cookie from your
# browser. Re-paste it when the SSO session expires.
# SUPERSET_SESSION_COOKIE=your_session_cookie_value
# Cookie name (defaults to "session")
# SUPERSET_SESSION_COOKIE_NAME=session

# MCP server settings (optional)
SUPERSET_MCP_HOST=127.0.0.1
SUPERSET_MCP_PORT=8001
```

- [ ] **Step 2: Find the auth/configuration section in `README.md`**

Run: `grep -n "SUPERSET_USERNAME\|SUPERSET_PASSWORD\|Authentication\|Configuration" README.md`
Expected: line numbers of the configuration/auth section to edit.

- [ ] **Step 3: Add a session-cookie subsection to `README.md`**

Immediately after the block that documents `SUPERSET_USERNAME` / `SUPERSET_PASSWORD` (located in Step 2), insert:

```markdown
#### Session-cookie authentication (SSO/OAuth)

When Superset is behind SSO (OAuth/OIDC/SAML), password login via the REST
API is unavailable. Instead, supply a browser **session cookie**:

| Variable | Description |
| --- | --- |
| `SUPERSET_SESSION_COOKIE` | Session cookie value copied from your browser. When set, this mode is used instead of username/password. |
| `SUPERSET_SESSION_COOKIE_NAME` | Cookie name. Defaults to `session`. |

Copy the cookie from your browser's dev tools (Application → Cookies →
your Superset domain → `session`). The MCP server sends it on every request
and fetches CSRF tokens with it. The session cannot be renewed server-side,
so when it expires you must paste a fresh value and restart the server.
```

- [ ] **Step 4: Add the equivalent subsection to `README_RU.md`**

Run: `grep -n "SUPERSET_USERNAME\|SUPERSET_PASSWORD\|Аутентификация\|Настройка" README_RU.md`
Then, after the `SUPERSET_USERNAME`/`SUPERSET_PASSWORD` block, insert:

```markdown
#### Аутентификация через session cookie (SSO/OAuth)

Если Superset работает за SSO (OAuth/OIDC/SAML), вход по логину и паролю
через REST API недоступен. Вместо этого укажите **session cookie** из браузера:

| Переменная | Описание |
| --- | --- |
| `SUPERSET_SESSION_COOKIE` | Значение session cookie из браузера. Если задано, используется вместо логина и пароля. |
| `SUPERSET_SESSION_COOKIE_NAME` | Имя cookie. По умолчанию `session`. |

Скопируйте cookie из инструментов разработчика браузера (Application →
Cookies → домен Superset → `session`). MCP-сервер отправляет её с каждым
запросом и получает с ней CSRF-токены. Сессию нельзя продлить на стороне
сервера — после истечения вставьте новое значение и перезапустите сервер.
```

- [ ] **Step 5: Verify docs render / no broken tables**

Run: `grep -n "SUPERSET_SESSION_COOKIE" .env.example README.md README_RU.md`
Expected: matches in all three files.

- [ ] **Step 6: Commit**

```bash
git add .env.example README.md README_RU.md
git commit -m "docs: document session-cookie (SSO) authentication mode"
```

---

## Self-Review

**Spec coverage:**
- §1 Auth strategy interface → Task 1 (Protocol, JwtAuthManager) + Task 2 (CookieAuthManager). ✓
- §2 Client changes → Task 3. ✓
- §3 Config & wiring (env vars, validation, mode selection) → Task 4. ✓
- §4 Error handling (SSO-specific 401 message) → Task 2 (`auth_failure_hint`) + Task 3 (surfaced in client). ✓
- §5 Testing (pytest/pytest-asyncio/respx, coverage points) → Task 1 setup; tests across Tasks 1–4. ✓
- §6 Docs (.env.example, README.md, README_RU.md) → Task 5. ✓
- "Tools need no changes" → Global Constraints note; no task touches `tools/`. ✓

**Placeholder scan:** No TBD/TODO; every code and test step shows complete code. Doc-insertion steps use `grep` to locate exact anchors rather than guessing line numbers.

**Type consistency:** `apply_auth(client, headers)`, `get_csrf_token(client)`, `auth_failure_hint` property, `invalidate`/`invalidate_csrf`, and `build_auth_strategy(...)` signature are used identically across Tasks 1–4. `CookieAuthManager(base_url, cookie_value, cookie_name="session")` attributes (`cookie_value`, `cookie_name`, `_csrf_token`) referenced consistently in tests and the factory.
