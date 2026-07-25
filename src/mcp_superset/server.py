"""MCP server entry point for Apache Superset."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_superset import __version__
from mcp_superset.auth import build_auth_strategy
from mcp_superset.client import SupersetClient
from mcp_superset.tools import register_all_tools

# Load .env — custom path via env var, or auto-detect from package directory
_custom_env = os.environ.get("SUPERSET_MCP_ENV_FILE")
if _custom_env:
    load_dotenv(Path(_custom_env))
else:
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(_env_path)

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

superset_client = SupersetClient(auth_manager=auth_manager, base_url=SUPERSET_BASE_URL)

# Create MCP server
mcp = FastMCP(
    name="superset",
    instructions=(
        "MCP server for managing Apache Superset. "
        "Provides tools for dashboards, charts, databases, datasets, "
        "SQL queries, users, roles, permissions, and other Superset resources."
    ),
)

# Register all tools
register_all_tools(mcp)


# Health check endpoint (no auth, no Superset API calls)
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "version": __version__,
            "superset_url": SUPERSET_BASE_URL,
        }
    )


if __name__ == "__main__":
    host = os.getenv("SUPERSET_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("SUPERSET_MCP_PORT", "8001"))
    mcp.run(transport="streamable-http", host=host, port=port, stateless_http=True)
