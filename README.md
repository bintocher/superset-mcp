# mcp-superset

<!-- mcp-name: io.github.bintocher/mcp-superset -->

[![PyPI version](https://img.shields.io/pypi/v/mcp-superset.svg)](https://pypi.org/project/mcp-superset/)
[![PyPI downloads](https://img.shields.io/pypi/dm/mcp-superset.svg)](https://pypi.org/project/mcp-superset/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/bintocher/mcp-superset/actions/workflows/ci.yml/badge.svg)](https://github.com/bintocher/mcp-superset/actions/workflows/ci.yml)
[![CodeQL](https://github.com/bintocher/mcp-superset/actions/workflows/codeql.yml/badge.svg)](https://github.com/bintocher/mcp-superset/actions/workflows/codeql.yml)

[![Superset 6.0.1](https://img.shields.io/badge/Superset-6.0.1-orange.svg)](https://superset.apache.org/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Typed](https://img.shields.io/badge/typed-py.typed-blue.svg)](https://peps.python.org/pep-0561/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Tools: 137](https://img.shields.io/badge/MCP_tools-132%2B-brightgreen.svg)](#available-tools-132)
[![GitHub stars](https://img.shields.io/github/stars/bintocher/mcp-superset.svg?style=social)](https://github.com/bintocher/mcp-superset)

A comprehensive [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for [Apache Superset](https://superset.apache.org/). Gives AI assistants (Claude, GPT, etc.) full control over your Superset instance — dashboards, charts, datasets, SQL Lab, users, roles, RLS, and more — through 137 tools.

## Comparison with Other Superset MCP Servers

| Feature | **mcp-superset** | [superset-mcp](https://github.com/aptro/superset-mcp) | [superset-mcp (Winding2020)](https://github.com/Winding2020/superset-mcp) | [superset-mcp-server](https://github.com/LiusCraft/superset-mcp-server) |
|---------|:-:|:-:|:-:|:-:|
| **Total tools** | **137** | 60 | 31 | 4 |
| Language | Python | Python | TypeScript | TypeScript |
| Dashboard CRUD | 15 tools | 5 | 8 | - |
| Dashboard native filters | **5 tools** | - | - | - |
| Chart CRUD | 11 tools | 5 | 7 | - |
| Database tools | 18 tools | 14 | 1 | 1 |
| Dataset tools | 11 tools | 3 | 7 | - |
| SQL Lab | 5 tools | 7 | 1 | 1 |
| **Security (users/roles)** | **26 tools** | 2 | - | - |
| **Row Level Security** | **5 tools** | - | - | - |
| **Groups** | **9 tools** | - | - | - |
| **Permissions audit** | **yes** | - | - | - |
| **Dashboard access grant/revoke** | **yes** | - | - | - |
| **Auto datasource_access sync** | **yes** | - | - | - |
| Reports & annotations | 10 tools | - | - | - |
| Tags | 7 tools | 7 | - | - |
| Asset export/import | yes | - | - | - |
| **Safety: confirmation flags** | **14 types** | - | - | - |
| **Safety: DDL/DML blocking** | **yes** | - | - | - |
| **Safety: system role protection** | **yes** | - | - | - |
| Transport | HTTP, SSE, stdio | stdio | stdio | stdio |
| Auth method | JWT + auto-refresh + CSRF | Username/password + token file | Username/password or token | LDAP |
| Superset versions | 6.0.1 | 4.1.1 | not specified | not specified |
| CLI with args | `--host --port --transport` | - | - | - |
| PyPI package | `mcp-superset` | `superset-mcp` | `superset-mcp` (npm) | - |
| uvx support | **yes** | - | - | - |
| License | MIT | MIT | - | Apache 2.0 |
| GitHub stars | new | 170 | 21 | 5 |

**Key differentiators:**
- Only MCP server with **full security management** (users, roles, RLS, groups, permissions audit)
- Only one with **built-in safety validations** (confirmation flags, DDL/DML blocking)
- Only one with **dashboard native filter management**
- Only one with **automatic datasource_access synchronization**
- Only one with **multiple transport options** (HTTP, SSE, stdio)
- Only one with **configurable CLI** (`--host`, `--port`, `--transport`, `--env-file`)

## Features

- **137 MCP tools** covering the complete Superset REST API
- **Dashboard management** — CRUD, copy, publish/unpublish, export/import, embedded mode, native filters
- **Chart management** — CRUD, copy, data retrieval, export/import, cache warmup
- **Database management** — CRUD, connection testing, schema/table introspection, SQL validation
- **Dataset management** — CRUD, duplicate, schema refresh, export/import
- **SQL Lab** — query execution, formatting, cost estimation, results & CSV export
- **Security** — users, roles, permissions, Row Level Security (RLS), groups
- **Access control automation** — grant/revoke dashboard access with automatic datasource permission sync
- **Audit** — comprehensive permissions matrix (user x dashboards x datasets x RLS)
- **Tags, reports, annotations, saved queries** — full CRUD
- **Asset export/import** — full instance backup and restore
- **Built-in safety** — confirmation flags for destructive operations, DDL/DML blocking in SQL Lab
- **JWT authentication** with automatic token refresh and CSRF handling
- **Streamable HTTP, SSE, and stdio transports**

## Quick Start

### Installation

```bash
# From PyPI
pip install mcp-superset

# With uv (recommended)
uv pip install mcp-superset

# Run without installing (uvx)
uvx mcp-superset
```

### Configuration

Create a `.env` file in the current directory, or set environment variables:

```env
# Required
SUPERSET_BASE_URL=https://superset.example.com
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=your_password

# Optional
SUPERSET_AUTH_PROVIDER=db          # db (default) or ldap
SUPERSET_MCP_HOST=127.0.0.1       # Server host (default: 127.0.0.1)
SUPERSET_MCP_PORT=8001             # Server port (default: 8001)
SUPERSET_MCP_TRANSPORT=streamable-http  # streamable-http (default), sse, or stdio
```

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

### Running

```bash
# Using CLI (after pip install)
mcp-superset

# Run without installing
uvx mcp-superset

# Using Python module
python -m mcp_superset

# With uv from source
uv run mcp-superset

# With custom settings
mcp-superset --host 0.0.0.0 --port 9000 --transport sse

# With custom .env file
mcp-superset --env-file /path/to/.env

# Using stdio transport (for Claude Desktop, Cursor, etc.)
mcp-superset --transport stdio
```

### CLI Options

| Option | Default | Env Variable | Description |
|--------|---------|-------------|-------------|
| `--host` | `127.0.0.1` | `SUPERSET_MCP_HOST` | Server bind address |
| `--port` | `8001` | `SUPERSET_MCP_PORT` | Server bind port |
| `--transport` | `streamable-http` | `SUPERSET_MCP_TRANSPORT` | Transport: `streamable-http`, `sse`, `stdio` |
| `--env-file` | auto-detect | — | Path to `.env` file |
| `--version` | — | — | Show version and exit |

### Connecting to MCP Clients

#### Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "superset": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

Then start the server: `mcp-superset` or `uvx mcp-superset`.

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "superset": {
      "command": "uvx",
      "args": ["mcp-superset", "--transport", "stdio"],
      "env": {
        "SUPERSET_BASE_URL": "https://superset.example.com",
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": "your_password"
      }
    }
  }
}
```

#### Cursor / Windsurf

```json
{
  "mcpServers": {
    "superset": {
      "command": "uvx",
      "args": ["mcp-superset", "--transport", "stdio"],
      "env": {
        "SUPERSET_BASE_URL": "https://superset.example.com",
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": "your_password"
      }
    }
  }
}
```

#### Other MCP Clients

Any MCP-compatible client can connect via:
- **Streamable HTTP**: `http://<host>:<port>/mcp`
- **SSE**: `http://<host>:<port>/sse`
- **stdio**: pipe to `mcp-superset --transport stdio`

## Available Tools (137)

### Dashboards (15 tools)

| Tool | Description |
|------|-------------|
| `superset_dashboard_list` | List dashboards with filtering and pagination |
| `superset_dashboard_get` | Get dashboard details by ID |
| `superset_dashboard_create` | Create a new dashboard |
| `superset_dashboard_update` | Update dashboard properties |
| `superset_dashboard_delete` | Delete a dashboard (requires confirmation) |
| `superset_dashboard_copy` | Duplicate a dashboard |
| `superset_dashboard_publish` | Publish a draft dashboard |
| `superset_dashboard_unpublish` | Unpublish a dashboard |
| `superset_dashboard_charts` | List charts in a dashboard |
| `superset_dashboard_datasets` | List datasets used by a dashboard |
| `superset_dashboard_export` | Export dashboard as ZIP (base64) |
| `superset_dashboard_import` | Import dashboard from ZIP file |
| `superset_dashboard_embedded_get` | Get embedded configuration |
| `superset_dashboard_embedded_set` | Enable embedded mode with allowed domains |
| `superset_dashboard_embedded_delete` | Disable embedded mode |

### Dashboard Filters (5 tools)

| Tool | Description |
|------|-------------|
| `superset_dashboard_filter_list` | List native filters on a dashboard |
| `superset_dashboard_filter_add` | Add a native filter (auto-generates correct ID format) |
| `superset_dashboard_filter_update` | Update an existing native filter |
| `superset_dashboard_filter_delete` | Remove a native filter (requires confirmation) |
| `superset_dashboard_filter_reset` | Remove all filters (requires confirmation) |

### Charts (11 tools)

| Tool | Description |
|------|-------------|
| `superset_chart_list` | List charts with filtering and pagination |
| `superset_chart_get` | Get chart details by ID |
| `superset_chart_create` | Create a new chart |
| `superset_chart_update` | Update chart properties |
| `superset_chart_delete` | Delete a chart (requires confirmation) |
| `superset_chart_copy` | Duplicate a chart |
| `superset_chart_data` | Execute chart query and get data |
| `superset_chart_get_data` | Get data from a saved chart |
| `superset_chart_export` | Export chart as ZIP (base64) |
| `superset_chart_import` | Import chart from ZIP file |
| `superset_chart_cache_warmup` | Warm up chart cache |

### Databases (18 tools)

| Tool | Description |
|------|-------------|
| `superset_database_list` | List database connections |
| `superset_database_get` | Get database details |
| `superset_database_create` | Register a new database connection |
| `superset_database_update` | Update database settings |
| `superset_database_delete` | Remove a database (requires confirmation) |
| `superset_database_test_connection` | Test database connectivity |
| `superset_database_schemas` | List schemas in a database |
| `superset_database_tables` | List tables in a schema |
| `superset_database_catalogs` | List catalogs (for multi-catalog databases) |
| `superset_database_connection_info` | Get connection string info |
| `superset_database_function_names` | List available SQL functions |
| `superset_database_related_objects` | Find charts/datasets using this database |
| `superset_database_validate_sql` | Validate SQL syntax |
| `superset_database_validate_parameters` | Validate connection parameters |
| `superset_database_select_star` | Generate SELECT * query for a table |
| `superset_database_table_metadata` | Get table column and index metadata |
| `superset_database_export` | Export database config as ZIP |
| `superset_database_available_engines` | List supported database engines |

### Datasets (11 tools)

| Tool | Description |
|------|-------------|
| `superset_dataset_list` | List datasets with filtering |
| `superset_dataset_get` | Get dataset details including columns and metrics |
| `superset_dataset_create` | Create a dataset from a table or SQL query |
| `superset_dataset_update` | Update dataset properties |
| `superset_dataset_delete` | Delete a dataset (requires confirmation) |
| `superset_dataset_duplicate` | Duplicate a dataset |
| `superset_dataset_refresh_schema` | Refresh columns from source |
| `superset_dataset_related_objects` | Find charts using this dataset |
| `superset_dataset_export` | Export dataset as ZIP |
| `superset_dataset_import` | Import dataset from ZIP |
| `superset_dataset_get_or_create` | Get existing or create new dataset |

### SQL Lab & Queries (13 tools)

| Tool | Description |
|------|-------------|
| `superset_sqllab_execute` | Execute a SQL query (SELECT only) |
| `superset_sqllab_format_sql` | Format/beautify SQL |
| `superset_sqllab_results` | Fetch results of a completed query |
| `superset_sqllab_estimate_cost` | Estimate query execution cost |
| `superset_sqllab_export_csv` | Export query results as CSV |
| `superset_query_list` | List executed queries |
| `superset_query_get` | Get query details and results |
| `superset_query_stop` | Stop a running query |
| `superset_saved_query_list` | List saved queries |
| `superset_saved_query_create` | Save a new query |
| `superset_saved_query_get` | Get saved query details |
| `superset_saved_query_update` | Update a saved query |
| `superset_saved_query_delete` | Delete a saved query (requires confirmation) |

### Security & Access Control (26 tools)

| Tool | Description |
|------|-------------|
| `superset_get_current_user` | Get current authenticated user info |
| `superset_get_current_user_roles` | Get roles of current user |
| `superset_user_list` | List users with filtering |
| `superset_user_get` | Get user details |
| `superset_user_create` | Create a new user |
| `superset_user_update` | Update user properties |
| `superset_user_delete` | Delete a user (requires confirmation) |
| `superset_role_list` | List roles |
| `superset_role_get` | Get role details |
| `superset_role_create` | Create a new role |
| `superset_role_update` | Update role name/description |
| `superset_role_delete` | Delete a role (requires confirmation, blocks system roles) |
| `superset_permission_list` | List all available permissions |
| `superset_role_permissions_get` | Get permissions assigned to a role |
| `superset_role_permission_add` | Set role permissions (full replacement, requires confirmation) |
| `superset_role_copy_permissions` | Copy all permissions from one role to another |
| `superset_dashboard_grant_role_access` | Grant a role access to dashboard and its datasets |
| `superset_dashboard_revoke_role_access` | Revoke a role's access to dashboard datasets |
| `superset_bulk_user_role_add` | Add a role to multiple users (by IDs or by current role) |
| `superset_bulk_user_role_remove` | Remove a role from multiple users |
| `superset_bulk_user_role_replace` | Replace one role with another for all matching users |
| `superset_rls_list` | List Row Level Security rules |
| `superset_rls_get` | Get RLS rule details |
| `superset_rls_create` | Create an RLS rule |
| `superset_rls_update` | Update an RLS rule (requires both roles and tables) |
| `superset_rls_delete` | Delete an RLS rule (requires confirmation) |

### Groups (9 tools)

| Tool | Description |
|------|-------------|
| `superset_group_list` | List groups |
| `superset_group_get` | Get group details with members and roles |
| `superset_group_create` | Create a new group |
| `superset_group_update` | Update group name |
| `superset_group_delete` | Delete a group |
| `superset_group_add_users` | Add users to a group |
| `superset_group_remove_users` | Remove users from a group |
| `superset_group_add_roles` | Add roles to a group |
| `superset_group_remove_roles` | Remove roles from a group |

### Tags (7 tools)

| Tool | Description |
|------|-------------|
| `superset_tag_list` | List tags |
| `superset_tag_get` | Get tag details |
| `superset_tag_create` | Create a tag (optionally bind to objects) |
| `superset_tag_update` | Update a tag |
| `superset_tag_delete` | Delete a tag (requires confirmation) |
| `superset_tag_get_objects` | List objects associated with a tag |
| `superset_tag_bulk_create` | Create multiple tags at once |

### System & Reports (21 tools)

| Tool | Description |
|------|-------------|
| `superset_report_list` | List scheduled reports |
| `superset_report_get` | Get report details |
| `superset_report_create` | Create a scheduled report |
| `superset_report_update` | Update a report |
| `superset_report_delete` | Delete a report (requires confirmation) |
| `superset_annotation_layer_list` | List annotation layers |
| `superset_annotation_layer_get` | Get annotation layer details |
| `superset_annotation_layer_create` | Create an annotation layer |
| `superset_annotation_layer_update` | Update an annotation layer |
| `superset_annotation_layer_delete` | Delete an annotation layer (requires confirmation) |
| `superset_annotation_list` | List annotations in a layer |
| `superset_annotation_get` | Get annotation details |
| `superset_annotation_create` | Create an annotation |
| `superset_annotation_update` | Update an annotation |
| `superset_annotation_delete` | Delete an annotation (requires confirmation) |
| `superset_recent_activity` | Get recent user activity |
| `superset_log_list` | Get audit logs |
| `superset_get_menu` | Get Superset menu structure |
| `superset_get_base_url` | Get configured Superset base URL |
| `superset_assets_export` | Export all Superset assets as ZIP |
| `superset_assets_import` | Import assets from ZIP file |

### Audit (1 tool)

| Tool | Description |
|------|-------------|
| `superset_permissions_audit` | Generate comprehensive permissions matrix |

## Safety Features

The server includes extensive built-in protections to prevent accidental data loss or misconfiguration.

### Confirmation Flags

Destructive operations require explicit confirmation parameters:

| Operation | Required Flag | What It Shows |
|-----------|--------------|---------------|
| Delete dashboard | `confirm_delete=True` | Dashboard name, slug, chart count |
| Delete chart | `confirm_delete=True` | Linked dashboards |
| Delete dataset | `confirm_delete=True` | Affected charts and dashboards |
| Delete database | `confirm_delete=True` | Affected datasets, charts |
| Delete RLS rule | `confirm_delete=True` | Clause, roles, datasets |
| Delete role | `confirm_delete=True` | Blocks system roles |
| Delete user | `confirm_delete=True` | Blocks service account deletion |
| Update chart params | `confirm_params_replace=True` | — |
| Update dataset columns | `confirm_columns_replace=True` | — |
| Update database URI | `confirm_uri_change=True` | Affected charts/dashboards |
| Update user roles | `confirm_roles_replace=True` | Current roles |
| Set role permissions | `confirm_full_replace=True` | — |
| Grant dashboard access | `confirm_grant=True` | Dry-run results |
| Revoke dashboard access | `confirm_revoke=True` | Dry-run results |
| Bulk add role to users | `confirm=True` | User count, sample list |
| Bulk remove role from users | `confirm=True` | User count, prevents last role removal |
| Bulk replace role | `confirm=True` | Old/new role names, user count |
| Copy role permissions | `confirm=True` | Source/target permission counts |

### Automatic Protections

- **DDL/DML blocking** — SQL Lab rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE` (SQL comments are stripped before checking)
- **System role protection** — cannot delete Admin, Alpha, Gamma, Public roles
- **Service account protection** — cannot delete the MCP service user
- **RLS safety** — `rls_update` requires both `roles` and `tables` to prevent silent data wipe
- **Native filter IDs** — automatically generated in `NATIVE_FILTER-<uuid>` format
- **Chart validation** — rejects charts without `granularity_sqla` (required for dashboard time filters)
- **Auto-sync** — datasource_access permissions are automatically synchronized when dashboard roles change

## Architecture

```
superset-mcp/
├── pyproject.toml              # Package configuration
├── .env.example                # Environment variable template
├── LICENSE                     # MIT License
├── README.md                   # This file
├── README_RU.md                # Russian documentation
├── CHANGELOG.md                # Version history
└── src/mcp_superset/
    ├── __init__.py             # Package init with __version__
    ├── __main__.py             # CLI entry point with argparse
    ├── server.py               # FastMCP server setup and configuration
    ├── auth.py                 # JWT authentication (login, refresh, CSRF)
    ├── client.py               # HTTP client (auto-auth, retry, RISON pagination)
    ├── models.py               # Pydantic models
    └── tools/
        ├── __init__.py         # register_all_tools()
        ├── helpers.py          # Auto-sync datasource_access logic
        ├── dashboards.py       # Dashboard + filter tools (20)
        ├── charts.py           # Chart tools (11)
        ├── databases.py        # Database tools (18)
        ├── datasets.py         # Dataset tools (11)
        ├── queries.py          # SQL Lab + saved query tools (13)
        ├── security.py         # User, role, permission, RLS, bulk operations (26)
        ├── groups.py           # Group management tools (9)
        ├── audit.py            # Permissions audit tool (1)
        ├── tags.py             # Tag tools (7)
        └── system.py           # Reports, annotations, logs, assets (21)
```

## Superset Compatibility

- **Tested with**: Apache Superset 6.0.1
- **Authentication**: JWT (recommended) — API Key (`sst_*`) is not implemented in Superset
- **Required Superset user**: Admin role (for full API access)

### Recommended Superset Configuration

Add to your `superset_config.py`:

```python
from datetime import timedelta

# Increase JWT token lifetime (default is 15 min)
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# Max API page size
FAB_API_MAX_PAGE_SIZE = 100
```

## Development

### Setup

```bash
git clone https://github.com/bintocher/mcp-superset.git
cd superset-mcp

# Create virtual environment and install in editable mode
uv venv
uv pip install -e ".[dev]"

# Copy and configure .env
cp .env.example .env
# Edit .env with your Superset credentials
```

### Running Locally

```bash
# Run from source
uv run python -m mcp_superset

# Or with CLI
uv run mcp-superset --port 8001
```

### Running Tests

```bash
uv run python test_all_tools.py
```

## Known Superset API Quirks

These are handled automatically by the MCP server, but useful to know when debugging:

| Quirk | Details |
|-------|---------|
| RISON pagination | Superset ignores `page`/`page_size` as query params; must use RISON in `q` parameter |
| CSRF required | All POST/PUT/DELETE need `X-CSRFToken` header + session cookie |
| Referer required | SQL Lab returns 403 without `Referer` header |
| Tag API returns `{}` | Tag creation doesn't return the ID; must query list |
| Tag update needs `name` | Field is mandatory even if unchanged |
| Role permissions replace | `POST /security/roles/{id}/permissions` replaces ALL permissions |
| RLS update replaces | `PUT /rowlevelsecurity/{id}` replaces ALL provided fields |
| Dataset update columns | `PUT /dataset/{id}` with `columns` replaces ALL columns |
| Dashboard copy | Requires `json_metadata` (can be `"{}"`) |
| Native filter IDs | Must be `NATIVE_FILTER-<uuid>` format |
| `filter_time` needs `granularity_sqla` | Charts without it silently ignore time filters |
| Number formatting | `SMART_NUMBER` abbreviates; use `,d` or `,.2f` for exact |

## License

[MIT](LICENSE) — Stanislav Chernov ([@bintocher](https://github.com/bintocher))
