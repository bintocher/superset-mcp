"""HTTP client for Superset REST API with automatic authentication."""

from typing import Any

import httpx

from mcp_superset.auth import AuthStrategy


class SupersetClient:
    """Unified async HTTP client for interacting with Superset REST API.

    Automatically injects JWT + CSRF into headers, handles API errors,
    and provides convenient CRUD methods.
    """

    def __init__(self, auth_manager: AuthStrategy, base_url: str):
        self.auth = auth_manager
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )

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
        try:
            await self.auth.apply_auth(self._client, headers)
            if need_csrf:
                csrf = await self.auth.get_csrf_token(self._client)
                headers["X-CSRFToken"] = csrf
        except httpx.HTTPStatusError as exc:
            # Login/refresh/CSRF fetch failed - surface it as a SupersetAPIError
            # (with the auth hint) instead of leaking a raw httpx exception.
            raise SupersetAPIError(
                status_code=exc.response.status_code,
                detail=(
                    f"Superset API authentication {exc.request.method} {exc.request.url.path}: "
                    f"{exc.response.status_code} - {self._error_detail(exc.response)}"
                ),
            ) from exc
        return headers

    def _error_detail(self, resp: httpx.Response) -> str:
        """Extract a human-readable error detail, appending the auth hint on 401.

        Args:
            resp: The failed httpx response.

        Returns:
            Error detail string; the auth hint is appended for 401 responses.
        """
        try:
            error_body = resp.json()
            detail = error_body.get("message", "") or self._format_errors(error_body.get("errors")) or str(error_body)
        except Exception:
            detail = resp.text[:500]
        detail = str(detail)
        if resp.status_code == 401 and self.auth.auth_failure_hint:
            detail = " - ".join(p for p in (detail, self.auth.auth_failure_hint) if p)
        return detail

    @staticmethod
    def _format_errors(errors: Any) -> str:
        """Flatten Superset's errors payload into a readable line.

        Superset returns 500s as {"errors": [{"message": "Fatal error",
        "error_type": ..., "extra": {"issue_codes": [{"code": N, ...}]}}]},
        which is far more useful than the bare "Fatal error" once unpacked.

        Args:
            errors: The "errors" value from a Superset error response.

        Returns:
            A single-line summary, or "" when there is nothing to unpack.
        """
        if not errors:
            return ""
        if not isinstance(errors, list):
            return str(errors)
        parts = []
        for item in errors:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            text = str(item.get("message", "")).strip()
            error_type = item.get("error_type")
            if error_type:
                text = f"{text} [{error_type}]" if text else f"[{error_type}]"
            extra = item.get("extra") or {}
            codes = extra.get("issue_codes") if isinstance(extra, dict) else None
            if isinstance(codes, list):
                messages = [str(c.get("message", "")).strip() for c in codes if isinstance(c, dict)]
                messages = [m for m in messages if m]
                if messages:
                    text = f"{text} ({'; '.join(messages)})"
            parts.append(text or str(item))
        return " | ".join(p for p in parts if p)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request to Superset API with error handling.

        Automatically retries on 401 (expired token). Does NOT retry on 400
        (Bad Request) as that indicates a data validation error.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (e.g. "/api/v1/chart/").
            params: Optional query parameters.
            json_data: Optional JSON body payload.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            SupersetAPIError: If the API returns a 4xx/5xx status code.
        """
        url = f"{self.base_url}{endpoint}"
        need_csrf = method.upper() in ("POST", "PUT", "DELETE")
        headers = await self._get_headers(need_csrf=need_csrf)

        resp = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
        )

        if resp.status_code == 401:
            # Token expired — invalidate and retry once
            self.auth.invalidate()
            headers = await self._get_headers(need_csrf=need_csrf)
            resp = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

        # CSRF token may expire independently of the JWT (FAB CSRF has its own,
        # shorter lifetime). Retry ONCE on a 400 that is clearly a CSRF failure —
        # narrowly, so genuine validation errors (other 400s) are NOT masked.
        if resp.status_code == 400 and need_csrf and self._is_csrf_error(resp):
            self.auth.invalidate_csrf()
            headers = await self._get_headers(need_csrf=need_csrf)
            resp = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

        if resp.status_code >= 400:
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API {method} {endpoint}: {resp.status_code} - {self._error_detail(resp)}",
            )

        if resp.status_code == 204:
            return {"status": "ok"}

        return resp.json()

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a GET request to the given API endpoint.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response.
        """
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request to the given API endpoint.

        Args:
            endpoint: API endpoint path.
            json_data: Optional JSON body payload.

        Returns:
            Parsed JSON response.
        """
        return await self._request("POST", endpoint, json_data=json_data)

    async def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a PUT request to the given API endpoint.

        Args:
            endpoint: API endpoint path.
            json_data: Optional JSON body payload.

        Returns:
            Parsed JSON response.
        """
        return await self._request("PUT", endpoint, json_data=json_data)

    async def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a DELETE request to the given API endpoint.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response.
        """
        return await self._request("DELETE", endpoint, params=params)

    async def get_raw(self, endpoint: str, params: dict[str, Any] | None = None) -> bytes:
        """Send a GET request and return raw bytes (for export endpoints).

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            Raw response content as bytes.

        Raises:
            SupersetAPIError: If the API returns a 4xx/5xx status code.
        """
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_headers(need_csrf=False)
        headers.pop("Content-Type", None)
        headers["Accept"] = "*/*"
        resp = await self._client.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
        )
        if resp.status_code == 401:
            self.auth.invalidate()
            headers = await self._get_headers(need_csrf=False)
            headers.pop("Content-Type", None)
            headers["Accept"] = "*/*"
            resp = await self._client.request(
                method="GET",
                url=url,
                headers=headers,
                params=params,
            )
        if resp.status_code >= 400:
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API GET {endpoint}: {resp.status_code} - {self._error_detail(resp)}",
            )
        return resp.content

    async def post_form(
        self,
        endpoint: str,
        files: dict,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Send a POST multipart/form-data request (for import endpoints).

        Args:
            endpoint: API endpoint path.
            files: Dictionary of files to upload (as expected by httpx).
            data: Optional form data fields.

        Returns:
            Parsed JSON response.

        Raises:
            SupersetAPIError: If the API returns a 4xx/5xx status code.
        """
        url = f"{self.base_url}{endpoint}"
        # httpx sets its own multipart Content-Type (with the boundary)
        headers = await self._get_headers(need_csrf=True)
        headers.pop("Content-Type", None)
        resp = await self._client.post(
            url=url,
            headers=headers,
            files=files,
            data=data or {},
        )
        if resp.status_code == 401:
            self.auth.invalidate()
            headers = await self._get_headers(need_csrf=True)
            headers.pop("Content-Type", None)
            resp = await self._client.post(
                url=url,
                headers=headers,
                files=files,
                data=data or {},
            )
        if resp.status_code >= 400:
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API POST {endpoint}: {resp.status_code} - {self._error_detail(resp)}",
            )
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()

    @staticmethod
    def _is_csrf_error(resp: httpx.Response) -> bool:
        """Detect whether a 400 response was caused by an expired/missing CSRF token.

        Args:
            resp: The httpx response with status 400.

        Returns:
            True if the response body mentions a CSRF problem.
        """
        try:
            body = resp.json()
            message = str(body.get("message", "") or body.get("msg", "") or body)
        except Exception:
            message = resp.text[:500]
        return "csrf" in message.lower()

    @staticmethod
    def _build_rison_q(page: int, page_size: int, existing_q: str | None = None) -> str:
        """Build a RISON query string with pagination, merging with an existing q filter.

        Superset ignores page/page_size as query parameters — they MUST be
        inside the RISON q parameter.

        Args:
            page: Page number (0-based).
            page_size: Number of results per page.
            existing_q: Existing RISON filter string (e.g. "(filters:!(...))").

        Returns:
            RISON string with pagination, e.g. "(page:0,page_size:100,...)".
        """
        pagination = f"page:{page},page_size:{page_size}"
        if not existing_q:
            return f"({pagination})"
        # Merge: insert pagination inside existing RISON parentheses
        q = existing_q.strip()
        if q.startswith("(") and q.endswith(")"):
            inner = q[1:-1].strip()
            if inner:
                return f"({pagination},{inner})"
            return f"({pagination})"
        # Non-standard format — wrap everything
        return f"({pagination},{q})"

    async def get_page(
        self,
        endpoint: str,
        page: int = 0,
        page_size: int = 100,
        q: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single page using RISON pagination.

        Superset ignores page/page_size as plain query parameters — they MUST
        be passed inside the RISON q parameter. This builds the correct q
        (merging any existing RISON filter) and issues the GET.

        Args:
            endpoint: API endpoint path.
            page: Page number (0-based).
            page_size: Number of results per page.
            q: Existing RISON filter to merge with pagination (optional).
            extra_params: Additional non-RISON query parameters (e.g. tags).

        Returns:
            Parsed JSON response for the requested page.
        """
        params: dict[str, Any] = dict(extra_params or {})
        params["q"] = self._build_rison_q(page, page_size, q)
        return await self.get(endpoint, params=params)

    async def get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> dict[str, Any]:
        """Send a GET request with automatic pagination — returns ALL records.

        Sequentially fetches pages of page_size records until all results are
        retrieved (based on the count field in the response).

        Superset requires pagination via RISON in the q parameter,
        NOT via separate page/page_size query parameters.

        Args:
            endpoint: API endpoint (e.g. "/api/v1/security/roles/").
            params: Additional query parameters (q, filters, etc.).
            page_size: Page size (max 100 for Superset API).
            max_pages: Maximum number of pages to fetch (safeguard against
                infinite loops, default=100 -> 10000 records).

        Returns:
            Combined result: {"result": [...all records...], "count": N}.
        """
        all_results: list[Any] = []
        page = 0
        total_count = None
        existing_q = (params or {}).get("q")

        while page < max_pages:
            page_params = {k: v for k, v in (params or {}).items() if k != "q"}
            page_params["q"] = self._build_rison_q(page, page_size, existing_q)

            data = await self.get(endpoint, params=page_params)

            results = data.get("result", [])
            all_results.extend(results)

            if total_count is None:
                total_count = data.get("count", len(results))

            if len(all_results) >= total_count or len(results) < page_size:
                break

            page += 1

        return {"result": all_results, "count": total_count or len(all_results)}

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()


class SupersetAPIError(Exception):
    """Error returned by Superset REST API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
