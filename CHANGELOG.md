# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.8] - 2026-07-13

### Fixed

- **`superset_dataset_update` silently reset `always_filter_main_dttm` to false.** Superset's `PUT /dataset/{id}` drops the flag whenever it is omitted from the payload, so updating a dataset's `columns` (e.g. to set Russian `verbose_name` labels) turned off the main datetime filter and broke time filtering on every dependent dashboard. The tool now preserves the current value automatically when `columns` are replaced, and exposes a new optional `always_filter_main_dttm` parameter to set it explicitly.

## [0.2.7] - 2026-06-15

### Fixed

- **`--version` reported a stale, hard-coded version.** The CLI banner was pinned to `0.2.4` in `__main__.py`, so `mcp-superset --version` printed the wrong version regardless of the installed package. It now derives the version from `mcp_superset.__version__`, keeping the CLI in sync with the package version automatically.

## [0.2.6] - 2026-06-09

### Fixed

- **Bulk role operations were broken** — `superset_bulk_user_role_add`, `superset_bulk_user_role_remove`, `superset_bulk_user_role_replace` and `superset_role_copy_permissions` passed `json=` instead of `json_data=` to the client, raising `TypeError` at apply time (dry-run was unaffected, so it went unnoticed).
- **DDL/DML guard in `superset_sqllab_execute` could be bypassed** — the check only inspected the first keyword, so `WITH ... DELETE`, chained `SELECT 1; DROP ...`, parenthesised `(DELETE ...)`, `EXPLAIN ... DELETE`, `COPY` and `DO $$ BEGIN EXECUTE '...' END $$` (DDL hidden in a string literal) slipped through. It now matches dangerous keywords (including `DO`/`EXECUTE`) as whole words anywhere in the query, after stripping comments and string literals, and names the most specific operation in the rejection message.
- **List pagination ignored `page`/`page_size`** — most `*_list` tools (including `superset_group_list`) sent them as plain query params, which Superset ignores (always returning the first page). They now use RISON pagination via the new `client.get_page()` helper. Custom endpoints (`recent_activity`, `tag/get_objects`) keep query params, as they genuinely read them.
- **CSRF token was never refreshed on expiry** — a stale CSRF (which has its own, shorter lifetime than the JWT) caused a 400 with no retry. The client now detects CSRF-related 400s and retries once with a fresh token, without masking genuine validation errors.
- **`granularity_sqla` guard was too strict** — it blocked legitimate non-temporal charts (maps, pie, word cloud, hierarchical). It is now required only for viz types that actually have a temporal axis.
- **Unhandled `JSONDecodeError` on malformed JSON arguments** — tools accepting JSON strings (`columns`, `metrics`, `recipients`, `query_context`, `objects_to_tag`, `tags`, `position_json`, `filters_json`) now return a structured `{"error": ...}` instead of crashing.
- **Auto-sync of `datasource_access`** used `PUT .../permissions/` (trailing slash) instead of the working `POST .../permissions`, so access grants on dashboard/chart create/update silently failed.

### Changed

- Removed reference to a non-existent `superset_rls_create_unsafe` tool in the Base RLS rejection message.
- Consolidated three near-duplicate `datasource_access` permission lookups into a single `find_datasource_permissions` helper.
- Standardised the dataset `related_objects` endpoint to a trailing slash, matching the database endpoint.

## [0.2.5] - 2026-04-05

### Added

- **Bulk role operations** (4 new tools):
  - `superset_bulk_user_role_add` — add a role to multiple users (by user IDs or by current role filter)
  - `superset_bulk_user_role_remove` — remove a role from multiple users (prevents removing last role)
  - `superset_bulk_user_role_replace` — replace one role with another for all users who have it
  - `superset_role_copy_permissions` — copy all permissions from one role to another
  - All bulk operations support dry-run mode and exclude Admin users by default
- **Improved permissions audit** (`superset_permissions_audit`):
  - Now checks both dashboard visibility (via `dashboard.roles`) AND `datasource_access`
  - Three access states: `1` (full access), `0` (no access), `"visible_no_data"` (can open dashboard but charts fail)
  - Previously only checked `datasource_access`, missing role-based dashboard visibility

### Changed

- Total tools count: 119 (was 115)

## [0.2.4] - 2026-03-11

### Added

- Extended README badges: PyPI downloads, CodeQL, Superset version, MCP compatible, py.typed, Ruff, uv, tools count, GitHub stars
- Official MCP Registry support (`server.json`, `mcp-name` verification tag)
- Glama.ai listing: https://glama.ai/mcp/servers/bintocher/mcp-superset
- Smithery configuration (`smithery.yaml`)

## [0.2.2] - 2025-03-11

### Changed

- Updated GitHub Actions to latest versions via Dependabot:
  - `actions/upload-artifact` v6 → v7
  - `actions/download-artifact` v6 → v8
  - `github/codeql-action` v3 → v4

## [0.2.1] - 2025-03-11

### Added

- Health check endpoint: `GET /health` returns server status, version, and Superset URL (no auth required)
- PEP 561 `py.typed` marker for typed package support
- CONTRIBUTING.md with development setup and contribution guidelines
- SECURITY.md with responsible disclosure policy
- GitHub issue templates (bug report, feature request) and PR template
- Dependabot configuration for automated dependency updates (pip + GitHub Actions)
- Pre-commit hooks configuration (ruff, trailing whitespace, YAML check)
- CodeQL security scanning workflow

### Changed

- All comments, docstrings, and error messages translated to English
- Google-style docstrings added to all public functions and methods

## [0.2.0] - 2025-03-11

### Changed

- Renamed Python package from `superset_mcp` to `mcp_superset` for consistency with PyPI name `mcp-superset`
- Import is now `import mcp_superset` (was `import superset_mcp`)
- CLI entry point: `python -m mcp_superset` (was `python -m superset_mcp`)

## [0.1.0] - 2025-03-10

### Added

- Initial release
- 128+ MCP tools covering complete Apache Superset 6.0.1 REST API
- Dashboard management: CRUD, copy, publish/unpublish, export/import, embedded mode
- Chart management: CRUD, copy, data retrieval, export/import, cache warmup
- Database management: CRUD, connection testing, schema/table introspection
- Dataset management: CRUD, duplicate, schema refresh, export/import
- SQL Lab: query execution, formatting, results retrieval, cost estimation
- Saved queries: full CRUD
- Security: user/role management, permissions, RLS (Row Level Security)
- Group management with role/user assignment
- Dashboard native filters: add, update, delete, reset
- Tag management with object binding
- Report scheduling and annotation layers
- Asset export/import (full instance backup/restore)
- Audit tool: comprehensive permissions matrix
- JWT authentication with automatic token refresh
- CSRF token handling for state-changing operations
- Built-in safety validations and confirmation flags for destructive operations
- Automatic datasource_access synchronization
- DDL/DML blocking in SQL Lab
- Streamable HTTP transport (stateless mode)
- CLI with configurable host/port
- Environment variable and `.env` file configuration
