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


class JwtAuthManager:
    """Manages JWT authentication with Superset REST API.

    Uses JWT authentication flow:
    - Login: POST /api/v1/security/login with refresh=true
    - CSRF: GET /api/v1/security/csrf_token/ (required for POST/PUT/DELETE)
    - Refresh: POST /api/v1/security/refresh when access_token expires
    """

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        provider: str = "db",
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.provider = provider

        # JWT state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._csrf_token: str | None = None
        self._token_expires_at: float = 0

    @property
    def auth_failure_hint(self) -> str | None:
        """No special hint — a JWT can be re-obtained via login/refresh."""
        return None

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid access_token, refreshing or re-logging in as needed.

        Args:
            client: httpx async client used for HTTP requests.

        Returns:
            A valid JWT access token string.
        """
        # Check if token is still valid (with 30 sec safety margin)
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token

        # Try refresh if we have a refresh token
        if self._refresh_token:
            refreshed = await self._refresh(client)
            if refreshed:
                return self._access_token

        # Full login
        await self._login(client)
        return self._access_token

    async def apply_auth(self, client: httpx.AsyncClient, headers: dict[str, str]) -> None:
        """Set the Authorization header with a valid Bearer token.

        Args:
            client: httpx async client used for HTTP requests.
            headers: Mutable header dict to inject the token into.
        """
        token = await self.get_token(client)
        headers["Authorization"] = f"Bearer {token}"

    async def get_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid CSRF token, fetching one if necessary.

        Args:
            client: httpx async client used for HTTP requests.

        Returns:
            A CSRF token string.
        """
        if self._csrf_token:
            return self._csrf_token
        await self._fetch_csrf(client)
        return self._csrf_token

    async def _login(self, client: httpx.AsyncClient) -> None:
        """Perform JWT login via POST /api/v1/security/login.

        Args:
            client: httpx async client used for HTTP requests.
        """
        url = f"{self.base_url}/api/v1/security/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "provider": self.provider,
            "refresh": True,
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        # Default JWT_ACCESS_TOKEN_EXPIRES = 15 minutes (900 sec)
        self._token_expires_at = time.time() + 900
        # Reset CSRF — it is bound to the session/token
        self._csrf_token = None

    async def _refresh(self, client: httpx.AsyncClient) -> bool:
        """Attempt to refresh the JWT using the refresh token.

        Args:
            client: httpx async client used for HTTP requests.

        Returns:
            True if refresh succeeded, False otherwise.
        """
        url = f"{self.base_url}/api/v1/security/refresh"
        headers = {"Authorization": f"Bearer {self._refresh_token}"}
        try:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + 900
            # Reset CSRF — a new one is needed for the new token
            self._csrf_token = None
            return True
        except (httpx.HTTPStatusError, KeyError):
            # Refresh failed — full login required
            self._refresh_token = None
            return False

    async def _fetch_csrf(self, client: httpx.AsyncClient) -> None:
        """Fetch CSRF token via GET /api/v1/security/csrf_token/.

        Args:
            client: httpx async client used for HTTP requests.
        """
        token = await self.get_token(client)
        url = f"{self.base_url}/api/v1/security/csrf_token/"
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self._csrf_token = data["result"]

    def invalidate(self) -> None:
        """Reset all cached tokens, forcing re-authentication on next request."""
        self._access_token = None
        self._refresh_token = None
        self._csrf_token = None
        self._token_expires_at = 0

    def invalidate_csrf(self) -> None:
        """Reset only the cached CSRF token.

        The JWT may still be valid while the CSRF token has expired
        (FAB CSRF tokens have their own, shorter lifetime). This forces
        a fresh CSRF fetch on the next mutating request without a full
        re-login.
        """
        self._csrf_token = None


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
