# Session-cookie authentication for mcp-superset

**Date:** 2026-07-14
**Status:** Approved (design)

## Motivation

The MCP server currently authenticates with Superset via a username/password →
JWT flow (`POST /api/v1/security/login`, then CSRF, with automatic JWT refresh).
When Superset is fronted by SSO (OAuth/OIDC/SAML), password-based login through
the REST API is not available. Operators in that situation already hold a valid
browser **Flask session cookie** and want the MCP server to reuse it instead of
credentials.

## Decisions

- **Driver:** SSO/OAuth — the JWT login path cannot be used, so session-cookie
  auth must be a real alternative auth mode, not merely an add-on.
- **Cookie source:** static environment variable. The operator re-pastes the
  cookie when the SSO session expires. Single-user / local setup.
- **Integration approach:** an auth strategy interface with two implementations
  (chosen over a mode flag on one class, or raw cookie-jar injection) so each
  auth scheme has one clear purpose and the CSRF machinery stays shared.
- **Mode selection:** auto — if the session-cookie env var is set, use cookie
  auth; otherwise fall back to the existing username/password JWT flow.

## Design

### 1. Auth strategy interface (`auth.py`)

Refactor around a common contract both modes implement:

```python
class AuthStrategy(Protocol):
    async def apply_auth(self, client: httpx.AsyncClient, headers: dict[str, str]) -> None: ...
    async def get_csrf_token(self, client: httpx.AsyncClient) -> str: ...
    def invalidate(self) -> None: ...
    def invalidate_csrf(self) -> None: ...
```

- **`JwtAuthManager`** — today's `AuthManager` logic, renamed. Behavior
  unchanged. `apply_auth` sets `Authorization: Bearer <jwt>` (obtaining/
  refreshing the token as it does now).
- **`CookieAuthManager`** — new. Holds the static cookie value and cookie name.
  - `apply_auth` sets `Cookie: <name>=<value>`.
  - `get_csrf_token` fetches `GET /api/v1/security/csrf_token/` authenticated by
    the cookie, and caches the result.
  - `invalidate()` is a no-op — a dead SSO session cannot be renewed
    server-side; nothing to refresh.
  - `invalidate_csrf()` clears the cached CSRF token.

The CSRF-fetch HTTP call is a shared helper reused by both implementations.

### 2. Client changes (`client.py`)

`SupersetClient` depends on `AuthStrategy` instead of the concrete
`AuthManager`. In `_get_headers` and `post_form`, replace the hand-built
`Authorization` header with `await auth.apply_auth(client, headers)`.

The existing 401-retry and CSRF-400-retry logic is unchanged. In cookie mode a
401 means the SSO session expired; the retry will fail again and the error is
surfaced clearly (see §4).

### 3. Config & wiring (`server.py`)

New environment variables:

- `SUPERSET_SESSION_COOKIE` — the cookie value. Its presence selects cookie mode.
- `SUPERSET_SESSION_COOKIE_NAME` — optional; defaults to `session`.

Validation:

1. `SUPERSET_BASE_URL` is required (unchanged).
2. Then require **either** `SUPERSET_SESSION_COOKIE`, **or**
   (`SUPERSET_USERNAME` and `SUPERSET_PASSWORD`).

If the cookie is set, build `CookieAuthManager`; otherwise build
`JwtAuthManager`. Error messages spell out both options.

### 4. Error handling

When cookie auth receives a 401 (on any request or on the CSRF fetch), raise a
`SupersetAPIError` whose message names the SSO-expiry cause, e.g.:

> "Session cookie rejected or expired — refresh SUPERSET_SESSION_COOKIE from
> your browser."

This makes the expired-cookie case obvious rather than a generic auth failure.

### 5. Testing

The project currently has no test framework (only ruff + mypy). Add as dev
dependencies: `pytest`, `pytest-asyncio`, and `respx` (httpx mock), plus a
`tests/` directory. Implementation follows TDD. Coverage:

- Cookie header is sent on requests in cookie mode.
- CSRF token is fetched via the cookie and cached.
- Config auto-selects the correct mode from env vars.
- Missing-config validation requires cookie OR username+password.
- Expired-cookie 401 produces the SSO-specific error message.
- JWT mode behavior is preserved after the rename/refactor.

### 6. Documentation

Update `.env.example`, `README.md`, and `README_RU.md` to document the
session-cookie mode and note its SSO use case.

## Out of scope (YAGNI)

- Per-request / multi-user cookies (hosted, multi-tenant setups).
- Automatic SSO re-login when the session expires.
- Encryption of the cookie at rest.

## Touch points

- `src/mcp_superset/auth.py` — split into strategy interface + two managers.
- `src/mcp_superset/client.py` — depend on the interface; use `apply_auth`.
- `src/mcp_superset/server.py` — new env vars, validation, mode selection.
- `.env.example`, `README.md`, `README_RU.md` — docs.
- `pyproject.toml` — dev test dependencies.
- `tests/` — new.

Tools under `src/mcp_superset/tools/` only import the ready-made
`superset_client` and need no changes.
