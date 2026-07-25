"""Tools for managing Superset dashboards."""

import base64
import json
import uuid

from mcp_superset.tools.helpers import parse_json_arg
from mcp_superset.tools.types import IntList, StrList

KPI_VIZ_TYPES = {"big_number_total", "big_number"}
MIN_KPI_HEIGHT = 16  # 2 grid cells (1 cell = 8 units)

# Filter types that require granularity_sqla on charts
_TIME_FILTER_TYPES = {"filter_time", "filter_timecolumn", "filter_timegrain"}


async def _ensure_datasets_filter_ready(client, dashboard_id: int) -> list[dict]:
    """Set always_filter_main_dttm=True on all datasets of a dashboard.

    Called automatically when creating/copying a dashboard or adding filters.

    Returns:
        List of {id, name, action} for updated datasets.
    """
    updated = []
    try:
        datasets_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
        datasets = datasets_resp.get("result", [])
    except Exception:
        return updated

    for ds in datasets:
        ds_id = ds.get("id")
        if not ds_id:
            continue
        try:
            ds_detail = await client.get(f"/api/v1/dataset/{ds_id}")
            ds_data = ds_detail.get("result", {})
            if not ds_data.get("always_filter_main_dttm"):
                await client.put(
                    f"/api/v1/dataset/{ds_id}",
                    json_data={"always_filter_main_dttm": True},
                )
                updated.append(
                    {
                        "id": ds_id,
                        "name": ds_data.get("table_name", "?"),
                        "action": "always_filter_main_dttm = True",
                    }
                )
        except Exception:
            pass
    return updated


async def _auto_fix_charts_for_filter(
    client,
    dashboard_id: int,
    filter_column: str,
    filter_type: str,
) -> dict:
    """Automatically configure ALL charts of a dashboard to work with a filter.

    For ANY filter type:
    1. Sets granularity_sqla on charts that lack it (required for time range).
       - For time filters: uses the filter column.
       - For other types (select, range): uses main_dttm_col from the chart's dataset.
    2. Checks that the filter column exists in each chart's dataset.
       If not, adds a warning (the filter won't affect that chart).

    Returns:
        dict with keys: charts_updated, charts_already_ok, column_warnings, warnings.
    """
    result = {
        "charts_updated": [],
        "charts_already_ok": [],
        "column_warnings": [],
        "warnings": [],
    }

    is_time_filter = filter_type in _TIME_FILTER_TYPES

    try:
        charts_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/charts")
        charts = charts_resp.get("result", [])
    except Exception:
        return result

    # Dataset cache: ds_id -> {main_dttm_col, column_names}
    ds_cache: dict[int, dict] = {}

    async def _get_dataset_info(ds_id: int) -> dict:
        if ds_id in ds_cache:
            return ds_cache[ds_id]
        try:
            ds_resp = await client.get(f"/api/v1/dataset/{ds_id}")
            ds_data = ds_resp.get("result", {})
            columns = ds_data.get("columns", [])
            col_names = {c.get("column_name") for c in columns if c.get("column_name")}
            info = {
                "main_dttm_col": ds_data.get("main_dttm_col"),
                "column_names": col_names,
                "table_name": ds_data.get("table_name", "?"),
            }
        except Exception:
            info = {"main_dttm_col": None, "column_names": set(), "table_name": "?"}
        ds_cache[ds_id] = info
        return info

    for chart_info in charts:
        chart_id = chart_info.get("id")
        if not chart_id:
            continue
        try:
            chart_resp = await client.get(f"/api/v1/chart/{chart_id}")
            chart = chart_resp.get("result", {})
        except Exception:
            result["warnings"].append(f"chart {chart_id}: failed to fetch")
            continue

        chart_name = chart.get("slice_name", "?")
        ds_id = chart.get("datasource_id")

        # --- Check if filter column exists in the chart's dataset ---
        if ds_id and not is_time_filter:
            ds_info = await _get_dataset_info(ds_id)
            if filter_column not in ds_info["column_names"]:
                result["column_warnings"].append(
                    {
                        "chart_id": chart_id,
                        "chart_name": chart_name,
                        "dataset_id": ds_id,
                        "dataset_name": ds_info["table_name"],
                        "missing_column": filter_column,
                        "message": (
                            f"Filter on '{filter_column}' will NOT affect chart "
                            f"'{chart_name}' (ID={chart_id}): column is missing "
                            f"from dataset '{ds_info['table_name']}' (ID={ds_id})"
                        ),
                    }
                )

        # --- granularity_sqla ---
        params_str = chart.get("params", "{}")
        try:
            params = json.loads(params_str) if isinstance(params_str, str) else (params_str or {})
        except json.JSONDecodeError:
            params = {}

        current = params.get("granularity_sqla")
        if current:
            result["charts_already_ok"].append(
                {
                    "id": chart_id,
                    "name": chart_name,
                    "granularity_sqla": current,
                }
            )
            continue

        # Determine the column for granularity_sqla
        if is_time_filter:
            sqla_col = filter_column
        else:
            # For non-time filters: use main_dttm_col from the dataset
            ds_info = await _get_dataset_info(ds_id) if ds_id else {}
            sqla_col = ds_info.get("main_dttm_col")
            if not sqla_col:
                result["warnings"].append(
                    f"chart {chart_id} ({chart_name}): no granularity_sqla "
                    f"and main_dttm_col is not set on the dataset — time range "
                    f"filter will not work for this chart"
                )
                continue

        params["granularity_sqla"] = sqla_col
        try:
            await client.put(
                f"/api/v1/chart/{chart_id}",
                json_data={
                    "params": json.dumps(params, ensure_ascii=False),
                },
            )
            result["charts_updated"].append(
                {
                    "id": chart_id,
                    "name": chart_name,
                    "set": f"granularity_sqla = '{sqla_col}'",
                }
            )
        except Exception as e:
            result["warnings"].append(f"chart {chart_id} ({chart_name}): error updating granularity_sqla: {e}")

    return result


def register_dashboard_tools(mcp):
    """Register all dashboard-related MCP tools."""

    from mcp_superset.server import superset_client as client
    from mcp_superset.tools.helpers import auto_sync_dashboard_access

    async def _validate_kpi_height(position: dict) -> str | None:
        """Validate that KPI charts (big_number_total/big_number) have height >= 2 grid cells.

        Returns:
            Error message string, or None if validation passes.
        """
        small_charts = {}  # chartId -> height
        for v in position.values():
            if not isinstance(v, dict) or v.get("type") != "CHART":
                continue
            meta = v.get("meta", {})
            chart_id = meta.get("chartId")
            height = meta.get("height", 0)
            if chart_id and height < MIN_KPI_HEIGHT:
                small_charts[chart_id] = height

        if not small_charts:
            return None

        kpi_violations = []
        for cid, height in small_charts.items():
            try:
                chart = await client.get(f"/api/v1/chart/{cid}")
                vt = chart.get("result", {}).get("viz_type", "")
                if vt in KPI_VIZ_TYPES:
                    kpi_violations.append((cid, height, vt))
            except Exception:
                pass

        if kpi_violations:
            details = ", ".join(
                f"chart_id={cid} (viz_type={vt}, height={h}, minimum={MIN_KPI_HEIGHT})" for cid, h, vt in kpi_violations
            )
            return (
                f"REJECTED: KPI charts (big_number_total/big_number) require at least "
                f"2 grid cells of height (height >= {MIN_KPI_HEIGHT}) in position_json. "
                f"Violations: {details}. "
                f"Fix height to {MIN_KPI_HEIGHT} or greater."
            )
        return None

    @mcp.tool
    async def superset_dashboard_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List Superset dashboards with pagination.

        IMPORTANT: always call this tool before dashboard_get
        to find out the current dashboard IDs.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By title: (filters:!((col:dashboard_title,opr:ct,value:search)))
                - By owner: (filters:!((col:owners,opr:rel_m_m,value:1)))
                - Published only: (filters:!((col:published,opr:eq,value:!t)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/dashboard/", params=params)
        else:
            result = await client.get_page("/api/v1/dashboard/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_get(dashboard_id: int) -> str:
        """Get detailed information about a dashboard by ID.

        IMPORTANT: if the ID is unknown, first call superset_dashboard_list
        to find the desired dashboard. A non-existent ID will return 404.

        Args:
            dashboard_id: Dashboard ID (integer from dashboard_list result).
        """
        result = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_create(
        dashboard_title: str,
        slug: str | None = None,
        published: bool = False,
        json_metadata: str | None = None,
        css: str | None = None,
        position_json: str | None = None,
        roles: IntList | None = None,
    ) -> str:
        """Create a new dashboard.

        IMPORTANT: when roles are specified, datasource_access is automatically
        synced for the given roles — each role will get access to all dashboard datasets.

        Args:
            dashboard_title: Dashboard title (displayed in the UI).
            slug: URL slug for a pretty link (e.g. "my-dashboard"). Must be unique.
            published: Publish immediately (default False — draft).
            json_metadata: JSON string with dashboard metadata. Contains filter settings,
                color palette, refresh interval. Use "{}" for empty metadata.
            css: Custom CSS for dashboard styling.
            position_json: JSON string with widget positioning on the dashboard.
                Defines the layout of charts, headers, dividers in the grid.
            roles: List of role IDs that can access the dashboard. Users without
                one of these roles will NOT see the dashboard. Empty list = accessible to all.
        """
        # Validate KPI chart height in position_json
        if position_json is not None:
            if isinstance(position_json, str):
                pos, err = parse_json_arg(position_json, "position_json")
                if err:
                    return json.dumps({"error": err}, ensure_ascii=False)
            else:
                pos = position_json
            kpi_error = await _validate_kpi_height(pos)
            if kpi_error:
                return json.dumps({"error": kpi_error}, ensure_ascii=False)

        payload = {"dashboard_title": dashboard_title}
        if slug is not None:
            payload["slug"] = slug
        if published:
            payload["published"] = published
        if json_metadata is not None:
            payload["json_metadata"] = json_metadata
        if css is not None:
            payload["css"] = css
        if position_json is not None:
            payload["position_json"] = position_json
        if roles is not None:
            payload["roles"] = roles
        result = await client.post("/api/v1/dashboard/", json_data=payload)

        # Auto: if dashboard was created with charts — enable
        # always_filter_main_dttm on all datasets
        new_id = result.get("id")
        datasets_auto = []
        if new_id and position_json:
            datasets_auto = await _ensure_datasets_filter_ready(client, new_id)

        if datasets_auto:
            result["_auto_datasets_updated"] = datasets_auto

        # Auto: sync datasource_access for dashboard roles
        if new_id:
            sync = await auto_sync_dashboard_access(client, new_id)
            if sync.get("synced_roles"):
                result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_update(
        dashboard_id: int,
        dashboard_title: str | None = None,
        slug: str | None = None,
        published: bool | None = None,
        json_metadata: str | dict | None = None,
        css: str | None = None,
        position_json: str | dict | None = None,
        owners: IntList | None = None,
        roles: IntList | None = None,
    ) -> str:
        """Update an existing dashboard. Pass only the fields to change.

        IMPORTANT: after the update, datasource_access is automatically synced —
        each role from dashboard.roles will get access to all dashboard datasets.

        Args:
            dashboard_id: ID of the dashboard to update.
            dashboard_title: New title.
            slug: New URL slug (must be unique).
            published: Change publication status (true — published, false — draft).
            json_metadata: Dashboard JSON metadata (string or object, fully replaced).
            css: New custom CSS for the dashboard.
                Injected as a <style> tag on the dashboard page.
                Does NOT affect Explore view (chart editor) — only the dashboard.

                Common CSS fixes:

                  1) KPI big_number_total — digit size and scroll:
                  KPI container has a fixed height (~60px at 2 cells).
                  Default font is small. To enlarge via CSS:
                    div[class*="big_number"] .header-line {
                      font-size: 3.3rem !important;  /* digits */
                      font-weight: 700 !important;
                      line-height: 1.1 !important;
                      margin-bottom: 0 !important;  /* REQUIRED! otherwise scroll */
                    }
                    div[class*="big_number"] .subheader-line {
                      font-size: 1rem !important;  /* label */
                      font-weight: 400 !important;
                      opacity: 0.7;
                    }
                  IMPORTANT: margin-bottom on .header-line defaults to 8px — together with
                  line-height causes overflow and scroll. Verification formula:
                  font_size_px * 1.1 + margin_bottom <= 60px.
                  3.3rem = 52.8px -> 52.8 * 1.1 = 58px + 0 = 58px < 60px OK

                  2) Country Map tooltip clipped by container — culprit is
                  DIV.dashboard-chart (styled-component with overflow:hidden).
                  Tooltip = DIV.hover-popup (NOT .datamaps-hoverover!). Fix:
                    .dashboard-chart-id-{N} .dashboard-chart {
                      overflow: visible !important;
                    }
                    .hover-popup { z-index: 99999 !important; }

                  To analyze CSS issues: open the dashboard in Playwright,
                  find the chart element, walk up parentElement,
                  check getComputedStyle(el).overflow at each level.

            position_json: Widget positioning on the dashboard (string or object).
                Defines the layout of charts, headers, dividers in the grid.
                IMPORTANT: fully replaced — first get current layout via
                dashboard_get, modify needed elements and pass the entire JSON.
            owners: List of owner user IDs (REPLACES all current owners).
            roles: List of role IDs for dashboard access (REPLACES current ones).
                On change, datasource_access is automatically synced.
        """
        # Validate KPI chart height in position_json
        if position_json is not None:
            if isinstance(position_json, str):
                pos, err = parse_json_arg(position_json, "position_json")
                if err:
                    return json.dumps({"error": err}, ensure_ascii=False)
            else:
                pos = position_json
            kpi_error = await _validate_kpi_height(pos)
            if kpi_error:
                return json.dumps({"error": kpi_error}, ensure_ascii=False)

        payload = {}
        if dashboard_title is not None:
            payload["dashboard_title"] = dashboard_title
        if slug is not None:
            payload["slug"] = slug
        if published is not None:
            payload["published"] = published
        if json_metadata is not None:
            payload["json_metadata"] = (
                json.dumps(json_metadata, ensure_ascii=False) if isinstance(json_metadata, dict) else json_metadata
            )
        if css is not None:
            payload["css"] = css
        if position_json is not None:
            payload["position_json"] = (
                json.dumps(position_json, ensure_ascii=False) if isinstance(position_json, dict) else position_json
            )
        if owners is not None:
            payload["owners"] = owners
        if roles is not None:
            payload["roles"] = roles
        result = await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data=payload)

        # Auto: sync datasource_access for dashboard roles
        sync = await auto_sync_dashboard_access(client, dashboard_id)
        if sync.get("synced_roles"):
            result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_publish(dashboard_id: int) -> str:
        """Publish a dashboard (make it visible to users with appropriate permissions).

        Args:
            dashboard_id: Dashboard ID.
        """
        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={"published": True})
        return json.dumps({"status": "ok", "dashboard_id": dashboard_id, "published": True}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_unpublish(dashboard_id: int) -> str:
        """Unpublish a dashboard (convert to draft).

        The dashboard will remain accessible to owners and admins but will be hidden from the general list.

        Args:
            dashboard_id: Dashboard ID.
        """
        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={"published": False})
        return json.dumps({"status": "ok", "dashboard_id": dashboard_id, "published": False}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_delete(
        dashboard_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a dashboard by ID. Charts and datasets are NOT deleted — only the dashboard itself.

        CRITICAL: the dashboard will be permanently deleted.

        Args:
            dashboard_id: ID of the dashboard to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
                r = info.get("result", {})
                title = r.get("dashboard_title", "?")
                slug = r.get("slug", "")
                published = r.get("published", False)
                charts = await client.get(f"/api/v1/dashboard/{dashboard_id}/charts")
                charts_count = len(charts.get("result", []))
            except Exception:
                title = f"ID={dashboard_id}"
                slug = ""
                published = "?"
                charts_count = "?"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deletion of dashboard '{title}'"
                        f"{f' (slug={slug})' if slug else ''} "
                        f"(ID={dashboard_id}, published={published}, "
                        f"charts={charts_count}). "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/dashboard/{dashboard_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_copy(
        dashboard_id: int,
        dashboard_title: str,
        json_metadata: str | None = None,
    ) -> str:
        """Create a copy of an existing dashboard with all its charts.

        Args:
            dashboard_id: ID of the source dashboard to copy.
            dashboard_title: Title for the new copy.
            json_metadata: JSON metadata for the copy.
                IMPORTANT: Superset requires this field. If not provided, "{}" will be used.
        """
        payload = {
            "dashboard_title": dashboard_title,
            "json_metadata": json_metadata or "{}",
        }
        result = await client.post(
            f"/api/v1/dashboard/{dashboard_id}/copy/",
            json_data=payload,
        )

        # Auto: enable always_filter_main_dttm on all datasets of the copy
        new_id = result.get("id")
        datasets_auto = []
        if new_id:
            datasets_auto = await _ensure_datasets_filter_ready(client, new_id)
        if datasets_auto:
            result["_auto_datasets_updated"] = datasets_auto

        # Auto: sync datasource_access for roles of the copy
        if new_id:
            sync = await auto_sync_dashboard_access(client, new_id)
            if sync.get("synced_roles"):
                result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_charts(dashboard_id: int) -> str:
        """Get the list of all charts placed on a dashboard.

        Returns chart IDs and names. Useful for analyzing dashboard contents.

        Args:
            dashboard_id: Dashboard ID.
        """
        result = await client.get(f"/api/v1/dashboard/{dashboard_id}/charts")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_datasets(dashboard_id: int) -> str:
        """Get the list of all datasets used by a dashboard's charts.

        Useful for understanding the dashboard's dependencies on data sources.

        Args:
            dashboard_id: Dashboard ID.
        """
        result = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_export(
        dashboard_ids: str,
    ) -> str:
        """Export dashboards with all dependencies (charts, datasets, databases) as a ZIP.

        The result is a base64-encoded ZIP file. It can be imported back
        via superset_dashboard_import.

        Args:
            dashboard_ids: Comma-separated dashboard IDs (e.g. "1,2,3").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        params = {"q": f"[{dashboard_ids}]"}
        raw = await client.get_raw("/api/v1/dashboard/export/", params=params)
        return json.dumps(
            {
                "format": "zip",
                "encoding": "base64",
                "data": base64.b64encode(raw).decode(),
                "size_bytes": len(raw),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_dashboard_import(
        file_path: str,
        overwrite: bool = False,
    ) -> str:
        """Import dashboards from a ZIP file (created via export).

        The ZIP should contain YAML files with dashboard and dependency configurations.

        Args:
            file_path: Absolute path to the ZIP file on disk.
            overwrite: Overwrite existing objects with the same UUID (default False).
        """
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/dashboard/import/",
                files=files,
                data=data,
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_get(dashboard_id: int) -> str:
        """Get the embedding (embedded) settings of a dashboard.

        IMPORTANT: will return 404 if embedded mode has not been configured via embedded_set.

        Args:
            dashboard_id: Dashboard ID.
        """
        result = await client.get(f"/api/v1/dashboard/{dashboard_id}/embedded")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_set(
        dashboard_id: int,
        allowed_domains: StrList | None = None,
    ) -> str:
        """Enable dashboard embedding (embedded mode) and configure allowed domains.

        Once enabled, the dashboard can be embedded via iframe on the specified domains.

        Args:
            dashboard_id: Dashboard ID.
            allowed_domains: List of domains where embedding is allowed
                (e.g. ["example.com", "app.example.com"]). Empty list = all domains.
        """
        payload = {}
        if allowed_domains is not None:
            payload["allowed_domains"] = allowed_domains
        result = await client.post(
            f"/api/v1/dashboard/{dashboard_id}/embedded",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_delete(dashboard_id: int) -> str:
        """Disable dashboard embedding (embedded mode).

        After disabling, the dashboard can no longer be embedded via iframe.

        Args:
            dashboard_id: Dashboard ID.
        """
        result = await client.delete(f"/api/v1/dashboard/{dashboard_id}/embedded")
        return json.dumps(result, ensure_ascii=False)

    # --- Dashboard native filter tools ---

    def _extract_chart_ids(position: dict) -> list[int]:
        """Extract chart IDs from a dashboard's position_json."""
        return [v["meta"]["chartId"] for v in position.values() if isinstance(v, dict) and v.get("type") == "CHART"]

    @mcp.tool
    async def superset_dashboard_filter_list(dashboard_id: int) -> str:
        """Get a list of native filters on a dashboard in a readable format.

        Parses json_metadata and returns configuration of each filter:
        ID, name, type, column, dataset, chartsInScope, controlValues.

        Args:
            dashboard_id: Dashboard ID.
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata") or "{}")
        filters = metadata.get("native_filter_configuration", [])
        summary = []
        for f in filters:
            targets = f.get("targets", [])
            column = None
            dataset_id = None
            if targets:
                column = targets[0].get("column", {}).get("name")
                dataset_id = targets[0].get("datasetId")
            summary.append(
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "filterType": f.get("filterType"),
                    "column": column,
                    "datasetId": dataset_id,
                    "chartsInScope": f.get("chartsInScope", []),
                    "cascadeParentIds": f.get("cascadeParentIds", []),
                    "controlValues": f.get("controlValues", {}),
                }
            )
        return json.dumps(summary, ensure_ascii=False, indent=2)

    @mcp.tool
    async def superset_dashboard_filter_add(
        dashboard_id: int,
        name: str,
        column: str,
        dataset_id: int,
        filter_type: str = "filter_select",
        multi_select: bool = True,
        search_all_options: bool = False,
        enable_empty_filter: bool = False,
        cascade_parent_id: str | None = None,
    ) -> str:
        """Add a native filter to a dashboard with correct defaults.

        Automatically populates chartsInScope with all dashboard charts,
        builds correct scope, defaultDataMask, and cascadeParentIds.
        Filter ID is generated in NATIVE_FILTER-<uuid> format — this is REQUIRED
        for Superset 6.0.1 (custom IDs are silently ignored by the frontend).

        Args:
            dashboard_id: Dashboard ID.
            name: Display name of the filter (e.g. "Full Name").
            column: Dataset column name for filtering (e.g. "full_name").
            dataset_id: ID of the dataset providing filter values.
            filter_type: Filter type: "filter_select", "filter_time", "filter_range".
            multi_select: Allow multiple selection (default True).
            search_all_options: Search all values, not just loaded ones (for large lists).
            enable_empty_filter: Empty filter means filtering by NULL.
            cascade_parent_id: ID of the parent filter for cascading.
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata") or "{}")
        position = json.loads(result.get("position_json") or "{}")

        chart_ids = _extract_chart_ids(position)
        filter_id = f"NATIVE_FILTER-{uuid.uuid4()}"

        new_filter = {
            "id": filter_id,
            "name": name,
            "filterType": filter_type,
            "type": "NATIVE_FILTER",
            "targets": [{"datasetId": dataset_id, "column": {"name": column}}],
            "controlValues": {
                "enableEmptyFilter": enable_empty_filter,
                "multiSelect": multi_select,
                "searchAllOptions": search_all_options,
                "inverseSelection": False,
                "defaultToFirstItem": False,
            },
            "defaultDataMask": {
                "extraFormData": {},
                "filterState": {},
                "ownState": {},
            },
            "cascadeParentIds": [cascade_parent_id] if cascade_parent_id else [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
        }

        filters = metadata.get("native_filter_configuration", [])
        filters.append(new_filter)
        metadata["native_filter_configuration"] = filters
        metadata["show_native_filters"] = True

        await client.put(
            f"/api/v1/dashboard/{dashboard_id}",
            json_data={
                "json_metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )

        # === Auto: configure datasets and charts for filter operation ===
        response = {
            "status": "ok",
            "filter_id": filter_id,
            "chartsInScope": chart_ids,
        }

        # 1. always_filter_main_dttm on all datasets
        datasets_auto = await _ensure_datasets_filter_ready(client, dashboard_id)
        if datasets_auto:
            response["_auto_datasets_updated"] = datasets_auto

        # 2. granularity_sqla on charts + column compatibility check
        charts_auto = await _auto_fix_charts_for_filter(client, dashboard_id, column, filter_type)
        if charts_auto["charts_updated"]:
            response["_auto_charts_updated"] = charts_auto["charts_updated"]
        if charts_auto["column_warnings"]:
            response["_auto_column_warnings"] = charts_auto["column_warnings"]
        if charts_auto["warnings"]:
            response["_auto_warnings"] = charts_auto["warnings"]

        return json.dumps(response, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_filter_update(
        dashboard_id: int,
        filter_id: str,
        name: str | None = None,
        column: str | None = None,
        multi_select: bool | None = None,
        search_all_options: bool | None = None,
        enable_empty_filter: bool | None = None,
        cascade_parent_id: str | None = None,
    ) -> str:
        """Update a native filter on a dashboard by ID. Pass only the fields to change.

        Args:
            dashboard_id: Dashboard ID.
            filter_id: Filter ID (format "NATIVE_FILTER-<uuid>").
            name: New filter name.
            column: New column for filtering.
            multi_select: Multiple selection.
            search_all_options: Search all values.
            enable_empty_filter: Empty filter = NULL.
            cascade_parent_id: Parent filter ID (None — remove cascading).
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata") or "{}")
        filters = metadata.get("native_filter_configuration", [])

        target = None
        for f in filters:
            if f.get("id") == filter_id:
                target = f
                break

        if not target:
            return json.dumps(
                {"status": "error", "message": f"Filter {filter_id} not found"},
                ensure_ascii=False,
            )

        if name is not None:
            target["name"] = name
        if column is not None and target.get("targets"):
            target["targets"][0]["column"]["name"] = column
        cv = target.get("controlValues", {})
        if multi_select is not None:
            cv["multiSelect"] = multi_select
        if search_all_options is not None:
            cv["searchAllOptions"] = search_all_options
        if enable_empty_filter is not None:
            cv["enableEmptyFilter"] = enable_empty_filter
        target["controlValues"] = cv
        if cascade_parent_id is not None:
            target["cascadeParentIds"] = [cascade_parent_id] if cascade_parent_id else []

        metadata["native_filter_configuration"] = filters
        await client.put(
            f"/api/v1/dashboard/{dashboard_id}",
            json_data={
                "json_metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )
        return json.dumps({"status": "ok", "filter_id": filter_id}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_filter_delete(
        dashboard_id: int,
        filter_id: str,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a native filter from a dashboard by ID.

        Args:
            dashboard_id: Dashboard ID.
            filter_id: ID of the filter to delete (format "NATIVE_FILTER-<uuid>").
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata") or "{}")
        filters = metadata.get("native_filter_configuration", [])

        target = None
        for f in filters:
            if f.get("id") == filter_id:
                target = f
                break

        if not target:
            return json.dumps(
                {"status": "error", "message": f"Filter {filter_id} not found"},
                ensure_ascii=False,
            )

        if not confirm_delete:
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deletion of filter '{target.get('name', '?')}' "
                        f"(ID={filter_id}) from dashboard {dashboard_id}. "
                        f"Total filters on dashboard: {len(filters)}. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        new_filters = [f for f in filters if f.get("id") != filter_id]
        metadata["native_filter_configuration"] = new_filters
        await client.put(
            f"/api/v1/dashboard/{dashboard_id}",
            json_data={
                "json_metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )
        return json.dumps(
            {"status": "ok", "deleted": filter_id, "remaining": len(new_filters)},
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_dashboard_filter_reset(
        dashboard_id: int,
        dataset_id: int,
        filters_json: str,
        confirm_reset: bool = False,
    ) -> str:
        """Recreate ALL native filters on a dashboard with correct defaults.

        Deletes all current filters and creates new ones from the provided list.
        Automatically populates chartsInScope, scope, defaultDataMask, cascadeParentIds.

        CRITICAL: all current filters will be DELETED and replaced with new ones.

        Args:
            dashboard_id: Dashboard ID.
            dataset_id: Dataset ID for all filters.
            filters_json: JSON array of filter definitions. Each element:
            confirm_reset: Filter reset confirmation (REQUIRED).
                {
                    "name": "Full Name",
                    "column": "full_name",
                    "type": "filter_select",       // filter_select | filter_time | filter_range
                    "multi_select": true,           // optional, default true
                    "search_all_options": false,     // optional, default false
                    "enable_empty_filter": false,    // optional, default false
                    "cascade_parent_id": null        // optional, parent filter ID
                }
        """
        if not confirm_reset:
            # Show current filters for an informed decision
            dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            result = dashboard.get("result", {})
            metadata = json.loads(result.get("json_metadata") or "{}")
            current_filters = metadata.get("native_filter_configuration", [])
            current_names = [f.get("name", "?") for f in current_filters]
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: filter_reset will delete {len(current_filters)} "
                        f"current filters: {current_names} and replace with new ones. "
                        f"Pass confirm_reset=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata") or "{}")
        position = json.loads(result.get("position_json") or "{}")

        chart_ids = _extract_chart_ids(position)
        filter_defs, err = parse_json_arg(filters_json, "filters_json")
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)

        new_filters = []
        for fd in filter_defs:
            filter_id = f"NATIVE_FILTER-{uuid.uuid4()}"
            filter_type = fd.get("type", "filter_select")

            f = {
                "id": filter_id,
                "name": fd["name"],
                "filterType": filter_type,
                "type": "NATIVE_FILTER",
                "targets": [{"datasetId": dataset_id, "column": {"name": fd["column"]}}],
                "controlValues": {
                    "enableEmptyFilter": fd.get("enable_empty_filter", False),
                    "multiSelect": fd.get("multi_select", True),
                    "searchAllOptions": fd.get("search_all_options", False),
                    "inverseSelection": False,
                    "defaultToFirstItem": False,
                },
                "defaultDataMask": {
                    "extraFormData": {},
                    "filterState": {},
                    "ownState": {},
                },
                "cascadeParentIds": ([fd["cascade_parent_id"]] if fd.get("cascade_parent_id") else []),
                "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
                "chartsInScope": chart_ids,
                "tabsInScope": [],
            }
            new_filters.append(f)

        metadata["native_filter_configuration"] = new_filters
        metadata["show_native_filters"] = True
        metadata["filter_bar_orientation"] = "VERTICAL"
        metadata["cross_filters_enabled"] = True
        metadata["filter_scopes"] = {}

        await client.put(
            f"/api/v1/dashboard/{dashboard_id}",
            json_data={
                "json_metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )

        response = {
            "status": "ok",
            "filters_created": len(new_filters),
            "chartsInScope": chart_ids,
            "filter_ids": [f["id"] for f in new_filters],
        }

        # === Auto: configure datasets and charts for filter operation ===
        # 1. always_filter_main_dttm on all datasets
        datasets_auto = await _ensure_datasets_filter_ready(client, dashboard_id)
        if datasets_auto:
            response["_auto_datasets_updated"] = datasets_auto

        # 2. granularity_sqla + column check for ALL filters
        # Use the first filter for auto_fix (granularity_sqla from time or main_dttm_col)
        first_fd = filter_defs[0] if filter_defs else {}
        first_type = first_fd.get("type", "filter_select")
        first_col = first_fd.get("column", "")
        if first_col:
            charts_auto = await _auto_fix_charts_for_filter(client, dashboard_id, first_col, first_type)
            if charts_auto["charts_updated"]:
                response["_auto_charts_updated"] = charts_auto["charts_updated"]
            if charts_auto["column_warnings"]:
                response["_auto_column_warnings"] = charts_auto["column_warnings"]
            if charts_auto["warnings"]:
                response["_auto_warnings"] = charts_auto["warnings"]

        return json.dumps(response, ensure_ascii=False, indent=2)
