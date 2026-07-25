"""End-to-end tool tests over the MCP layer, covering the reported bugs.

Issue #11: dashboards whose json_metadata is null crashed every native-filter
tool with a TypeError before any API call was made.
Issue #12: list arguments arrive JSON-encoded from some clients ("[31]"), which
pydantic rejected, making the dashboards parameter unusable.
"""

import json

import httpx
import pytest
import respx
from fastmcp import Client, FastMCP

import mcp_superset.server as server_module
from mcp_superset.auth import CookieAuthManager
from mcp_superset.client import SupersetClient
from mcp_superset.tools import register_all_tools

BASE = "https://superset.example.com"


@pytest.fixture
def mcp_server(monkeypatch):
    """An MCP server whose tools talk to a SupersetClient we can mock with respx."""
    client = SupersetClient(auth_manager=CookieAuthManager(base_url=BASE, cookie_value="c"), base_url=BASE)
    monkeypatch.setattr(server_module, "superset_client", client)
    mcp = FastMCP(name="test")
    register_all_tools(mcp)
    yield mcp


def _text(result):
    """Extract the tool's text payload across fastmcp result shapes."""
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        return content[0].text
    return str(content)


@respx.mock
async def test_filter_list_on_dashboard_with_null_metadata(mcp_server):
    respx.get(f"{BASE}/api/v1/dashboard/31").mock(
        return_value=httpx.Response(200, json={"result": {"id": 31, "json_metadata": None, "position_json": None}})
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool("superset_dashboard_filter_list", {"dashboard_id": 31})

    assert json.loads(_text(result)) == []


@respx.mock
async def test_filter_add_on_dashboard_with_null_metadata(mcp_server):
    respx.get(f"{BASE}/api/v1/dashboard/31").mock(
        return_value=httpx.Response(200, json={"result": {"id": 31, "json_metadata": None, "position_json": None}})
    )
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(return_value=httpx.Response(200, json={"result": "csrf"}))
    put = respx.put(f"{BASE}/api/v1/dashboard/31").mock(return_value=httpx.Response(200, json={"result": {}}))
    respx.get(f"{BASE}/api/v1/dashboard/31/datasets").mock(return_value=httpx.Response(200, json={"result": []}))
    respx.get(f"{BASE}/api/v1/dashboard/31/charts").mock(return_value=httpx.Response(200, json={"result": []}))

    async with Client(mcp_server) as c:
        result = await c.call_tool(
            "superset_dashboard_filter_add",
            {"dashboard_id": 31, "name": "Region", "column": "region", "dataset_id": 7},
        )

    payload = json.loads(_text(result))
    assert payload["status"] == "ok"
    assert payload["filter_id"].startswith("NATIVE_FILTER-")
    sent = json.loads(json.loads(put.calls.last.request.content)["json_metadata"])
    assert len(sent["native_filter_configuration"]) == 1


@respx.mock
async def test_chart_update_accepts_json_encoded_dashboards(mcp_server):
    respx.get(f"{BASE}/api/v1/security/csrf_token/").mock(return_value=httpx.Response(200, json={"result": "csrf"}))
    put = respx.put(f"{BASE}/api/v1/chart/65").mock(return_value=httpx.Response(200, json={"result": {"id": 65}}))
    respx.get(f"{BASE}/api/v1/chart/65").mock(
        return_value=httpx.Response(200, json={"result": {"id": 65, "dashboards": [], "datasource_id": 7}})
    )

    async with Client(mcp_server) as c:
        await c.call_tool("superset_chart_update", {"chart_id": 65, "dashboards": "[31]"})

    assert json.loads(put.calls.last.request.content)["dashboards"] == [31]
