"""Tools for managing Superset charts."""

import base64
import json
import re

from mcp_superset.tools.helpers import auto_sync_chart_dashboards, parse_json_arg
from mcp_superset.tools.types import IntList

# Moment.js date format patterns that do NOT work in Superset 6.x.
# Superset uses D3 strftime (%Y-%m-%d); moment.js (YYYY-MM-DD) renders as literal text.
_MOMENTJS_DATE_PATTERNS = re.compile(
    r"(?<![%\w])"  # not preceded by % or a word char (exclude D3 formats and words)
    r"(?:"
    r"YYYY[-/.]MM[-/.]DD"  # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    r"|DD[-/.]MM[-/.]YYYY"  # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
    r"|MM[-/.]DD[-/.]YYYY"  # MM-DD-YYYY
    r"|YYYY[-/.]MM"  # YYYY-MM
    r"|MMM[\s]YYYY"  # MMM YYYY
    r"|DD[\s]MMM[\s]YYYY"  # DD MMM YYYY
    r"|HH:mm(?::ss)?"  # HH:mm, HH:mm:ss
    r")"
)

# Params keys that contain date formats
_DATE_FORMAT_KEYS = {
    "table_timestamp_format",
    "x_axis_time_format",
    "tooltipTimeFormat",
    "y_axis_format",
    "header_timestamp_format",
}

# Legacy viz_type values removed from the Superset 5.0/6.x frontend.
# The frontend returns an error: "Item with key 'X' is not registered"
_DEPRECATED_VIZ_TYPES = {
    # Removed in Superset 5.0 (auto-migration via superset viz-migrations upgrade)
    "area": "echarts_area",
    "bar": "echarts_timeseries_bar",
    "line": "echarts_timeseries_line (or echarts_timeseries_smooth for cardinal, echarts_timeseries_step for step)",
    "heatmap": "heatmap_v2",
    "histogram": "histogram_v2",
    "sankey": "sankey_v2",
    "sankey_loop": "no replacement (removed without a substitute)",
    "event_flow": "no replacement (removed without a substitute)",
    # Removed in Superset 3.0/4.0
    "dist_bar": "echarts_timeseries_bar (with orientation: horizontal for horizontal layout)",
    "dual_line": "mixed_timeseries (2 metrics with 2 Y-axes)",
    "treemap": "treemap_v2",
    "sunburst": "sunburst_v2",
    "pivot_table": "pivot_table_v2",
    "line_multi": "mixed_timeseries",
    "filter_box": "Native Dashboard Filters (dashboard_filter_add)",
    # Removed earlier
    "markup": "Dashboard Markdown component",
    "separator": "Dashboard Markdown component",
    "iframe": "Dashboard Markdown component",
}

# Valid viz_type values in Superset 6.x (registered in MainPreset.ts).
# Used for validation: if a viz_type is neither valid nor deprecated,
# a warning is issued (possible typo).
_VALID_VIZ_TYPES = {
    # ECharts
    "big_number",
    "big_number_total",
    "pop_kpi",
    "box_plot",
    "bubble_v2",
    "echarts_area",
    "echarts_timeseries",
    "echarts_timeseries_bar",
    "echarts_timeseries_line",
    "echarts_timeseries_scatter",
    "echarts_timeseries_smooth",
    "echarts_timeseries_step",
    "funnel",
    "gantt_chart",
    "gauge_chart",
    "graph_chart",
    "heatmap_v2",
    "histogram_v2",
    "mixed_timeseries",
    "pie",
    "radar",
    "sankey_v2",
    "sunburst_v2",
    "tree_chart",
    "treemap_v2",
    "waterfall",
    # Tables
    "table",
    "pivot_table_v2",
    "ag-grid-table",
    # Templates and text
    "handlebars",
    # Maps
    "country_map",
    "world_map",
    "mapbox",
    # deck.gl
    "deck_arc",
    "deck_contour",
    "deck_geojson",
    "deck_grid",
    "deck_heatmap",
    "deck_hex",
    "deck_multi",
    "deck_path",
    "deck_polygon",
    "deck_scatter",
    "deck_screengrid",
    # Legacy (still registered but may be removed in the future)
    "bubble",
    "bullet",
    "cal_heatmap",
    "chord",
    "compare",
    "horizon",
    "paired_ttest",
    "para",
    "partition",
    "rose",
    "time_pivot",
    "time_table",
    "word_cloud",
}


# viz_types that have NO temporal axis — dashboard time filters cannot apply
# to them via granularity_sqla, so requiring it would block legitimate charts.
# Everything else (timeseries, tables, big_number/KPI) still requires it so
# dashboard time/native filters keep working.
_NON_TEMPORAL_VIZ_TYPES = {
    # Maps
    "country_map",
    "world_map",
    "mapbox",
    "deck_arc",
    "deck_contour",
    "deck_geojson",
    "deck_grid",
    "deck_heatmap",
    "deck_hex",
    "deck_multi",
    "deck_path",
    "deck_polygon",
    "deck_scatter",
    "deck_screengrid",
    # Text / templates
    "word_cloud",
    "handlebars",
    # Categorical / hierarchical (no inherent time axis)
    "pie",
    "funnel",
    "radar",
    "gauge_chart",
    "treemap_v2",
    "sunburst_v2",
    "sankey_v2",
    "chord",
    "partition",
    "graph_chart",
    "tree_chart",
    "rose",
    "paired_ttest",
    "para",
}


def _validate_chart_params(params_str: str | None, viz_type: str | None = None) -> str | None:
    """Validate params and viz_type for common errors.

    Args:
        params_str: JSON string of chart params to validate.
        viz_type: Chart visualization type to check against known types.

    Returns:
        Error message string if validation fails, None otherwise.
    """
    errors = []

    # Check for deprecated viz_type
    vt = viz_type
    if vt is None and params_str:
        try:
            vt = json.loads(params_str).get("viz_type")
        except (json.JSONDecodeError, AttributeError):
            pass
    if vt and vt in _DEPRECATED_VIZ_TYPES:
        replacement = _DEPRECATED_VIZ_TYPES[vt]
        errors.append(
            f"viz_type '{vt}' has been removed from Superset 6.x (error: 'Item with key \"{vt}\" "
            f"is not registered'). Use instead: {replacement}"
        )
    elif vt and vt not in _VALID_VIZ_TYPES:
        errors.append(
            f"viz_type '{vt}' not found in the list of valid Superset 6.x types. "
            f"Possible typo. Available types: " + ", ".join(sorted(_VALID_VIZ_TYPES))
        )

    # Parse params for all checks below
    if params_str:
        try:
            params_dict = json.loads(params_str)
        except json.JSONDecodeError:
            params_dict = {}
    else:
        params_dict = {}

    # Check granularity_sqla — REQUIRED for dashboard time filters to work,
    # but ONLY for viz types that actually have a temporal axis. Non-temporal
    # viz (maps, pie, word_cloud, hierarchical) cannot use it and must not be
    # blocked. When viz_type is unknown, default to requiring it (conservative).
    needs_granularity = not (vt and vt in _NON_TEMPORAL_VIZ_TYPES)
    if params_str and needs_granularity and not params_dict.get("granularity_sqla"):
        errors.append(
            "params does not contain 'granularity_sqla' — WITHOUT this parameter "
            "dashboard filters (time range, native filters) will NOT work "
            "for this chart. SQL will be generated without a WHERE clause on date. "
            "Add granularity_sqla with the name of the dataset's temporal column "
            '(e.g. "granularity_sqla": "call_date"). '
            "To find the column: dataset_get -> main_dttm_col or columns[].is_dttm=true"
        )

    # Check for moment.js formats in params
    if params_str:
        for key in _DATE_FORMAT_KEYS:
            value = params_dict.get(key)
            if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                errors.append(
                    f"Parameter '{key}' contains moment.js format '{value}' — "
                    f"Superset 6.x will render it as LITERAL TEXT! "
                    f"Use D3 strftime instead: "
                    f'"%Y-%m-%d" (date), "%Y-%m-%d %H:%M" (datetime), '
                    f'"%d.%m.%Y" (European), "%Y-%m" (year-month), "%Y" (year)'
                )

        # Check for moment.js format in query_context form_data
        form_data = params_dict.get("form_data", {})
        if isinstance(form_data, str):
            try:
                form_data = json.loads(form_data)
            except json.JSONDecodeError:
                form_data = {}
        if isinstance(form_data, dict):
            for key in _DATE_FORMAT_KEYS:
                value = form_data.get(key)
                if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                    errors.append(
                        f"form_data.'{key}' contains moment.js format '{value}' — "
                        f'replace with D3 strftime (e.g. "%Y-%m-%d")'
                    )

    if errors:
        return "REJECTED:\n" + "\n".join(f"• {e}" for e in errors)
    return None


def _validate_query_context(query_context_str: str | None) -> str | None:
    """Validate query_context for moment.js date formats.

    Args:
        query_context_str: JSON string of query context to validate.

    Returns:
        Error message string if validation fails, None otherwise.
    """
    if not query_context_str:
        return None
    try:
        qc = json.loads(query_context_str)
    except json.JSONDecodeError:
        return None

    errors = []
    # Check form_data inside query_context
    form_data = qc.get("form_data", {})
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except json.JSONDecodeError:
            form_data = {}
    if isinstance(form_data, dict):
        for key in _DATE_FORMAT_KEYS:
            value = form_data.get(key)
            if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                errors.append(
                    f"query_context.form_data.'{key}' contains moment.js format "
                    f"'{value}' — replace with D3 strftime (e.g. \"%Y-%m-%d\")"
                )

    if errors:
        return "REJECTED:\n" + "\n".join(f"• {e}" for e in errors)
    return None


def register_chart_tools(mcp):
    """Register all chart-related MCP tools on the given server.

    Args:
        mcp: The MCP server instance to register tools on.
    """
    from mcp_superset.server import superset_client as client

    @mcp.tool
    async def superset_chart_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List Superset charts with pagination.

        IMPORTANT: always call this tool before chart_get/chart_delete
        to look up actual chart IDs.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for searching. Examples:
                - By name: (filters:!((col:slice_name,opr:ct,value:search_term)))
                - By type: (filters:!((col:viz_type,opr:eq,value:table)))
                - By dataset: (filters:!((col:datasource_id,opr:eq,value:1)))
            get_all: Retrieve ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/chart/", params=params)
        else:
            result = await client.get_page("/api/v1/chart/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_get(chart_id: int) -> str:
        """Get detailed information about a chart by ID.

        Returns all settings: viz_type, params, query_context, dashboard bindings.
        IMPORTANT: if the ID is unknown, call superset_chart_list first.

        Args:
            chart_id: Chart ID (integer from chart_list result).
        """
        result = await client.get(f"/api/v1/chart/{chart_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_create(
        slice_name: str,
        viz_type: str,
        datasource_id: int,
        datasource_type: str = "table",
        params: str | None = None,
        query_context: str | None = None,
        dashboards: IntList | None = None,
    ) -> str:
        """Create a new chart.

        Args:
            slice_name: Chart name (displayed in the UI).
            viz_type: Visualization type (Superset 6.x). Main types:
                ECharts (recommended):
                - echarts_timeseries_bar — bar/horizontal bar chart
                - echarts_timeseries_line — line chart
                - echarts_timeseries_smooth — smoothed line
                - echarts_timeseries_step — step line
                - echarts_timeseries_scatter — scatter plot
                - echarts_area — area chart
                - mixed_timeseries — multiple series with 2 Y-axes
                - pie — pie chart
                - funnel — funnel chart
                - gauge_chart — gauge/speedometer
                - radar — radar chart
                - graph_chart — graph/network
                - tree_chart — tree diagram
                - treemap_v2 — treemap
                - sunburst_v2 — sunburst chart
                - sankey_v2 — Sankey diagram
                - heatmap_v2 — heatmap
                - histogram_v2 — histogram
                - box_plot — box plot
                - bubble_v2 — bubble chart
                - waterfall — waterfall chart
                - gantt_chart — Gantt chart
                KPI:
                - big_number_total — big number (KPI)
                - big_number — KPI with trend
                Tables:
                - table — table
                - pivot_table_v2 — pivot table
                Maps:
                - country_map — country map (ISO 3166-2 codes)
                - world_map — world map
                Other:
                - word_cloud — word cloud
                - handlebars — custom template
                DEPRECATED (DO NOT USE — "not registered" error):
                  dist_bar -> echarts_timeseries_bar, bar -> echarts_timeseries_bar,
                  area -> echarts_area, line -> echarts_timeseries_line,
                  heatmap -> heatmap_v2, histogram -> histogram_v2,
                  treemap -> treemap_v2, sunburst -> sunburst_v2,
                  sankey -> sankey_v2, pivot_table -> pivot_table_v2,
                  dual_line -> mixed_timeseries, line_multi -> mixed_timeseries
            datasource_id: Dataset ID (from superset_dataset_list).
            datasource_type: Data source type (default "table" — dataset).
            params: JSON string with visualization parameters (depend on viz_type).
                Define metrics, groupings, filters, colors, labels, etc.

                IMPORTANT — numeric and time formats:
                  Do NOT use SMART_NUMBER or SMART_DATE — they abbreviate numbers
                  (1.61k instead of 1610) and show literal text instead of dates.
                  Use explicit formats:
                  - y_axis_format: "d" (integers without separators), ",d" (with commas),
                    ",.2f" (decimals)
                  - number_format: ",d" (for pie chart)
                  - x_axis_time_format: "%b %Y" (X-axis dates), "%Y-%m-%d" (ISO)
                  - tooltipTimeFormat: "%Y-%m-%d" or "%Y-%m" (tooltip dates)
                  - show_value: true (show numbers on bar chart columns)

                CRITICAL — date/time format in Superset 6.x:
                  Superset 6.x uses ONLY D3 time format (strftime syntax).
                  Do NOT use moment.js format (YYYY-MM-DD) — it will be rendered
                  as literal text "YYYY-MM-DD" instead of an actual date!
                  Correct formats (D3/strftime):
                  - "%Y-%m-%d"       -> 2026-03-05 (ISO date)
                  - "%Y-%m-%d %H:%M" -> 2026-03-05 14:30 (date + time)
                  - "%d.%m.%Y"       -> 05.03.2026 (European format)
                  - "%b %Y"          -> Mar 2026 (month + year)
                  - "%Y"             -> 2026 (year only)
                  - "%Y-%m"          -> 2026-03 (year-month)
                  INCORRECT formats (moment.js — DO NOT WORK):
                  - "YYYY-MM-DD" — renders literal "YYYY-MM-DD"
                  - "DD.MM.YYYY" — renders literal "DD.MM.YYYY"
                  - "MMM YYYY"   — renders literal "MMM YYYY"
                  Parameters that accept date formats:
                  - table_timestamp_format (tables)
                  - x_axis_time_format (X-axis)
                  - tooltipTimeFormat (tooltip)
                  - y_axis_format (for big_number_total with date in metric)

                big_number_total (KPI cards) — REFERENCE parameters:
                  - header_font_size: 0.27 (number size, ~53px in a 60px container)
                  - subheader_font_size: 0.15 (subtitle/label size)
                  - y_axis_format: "d" (integers without comma separators)
                  IMPORTANT — scroll in KPI: the big_number_total container has a fixed
                  height (usually 60px at 2 grid cells). Too large a font causes scrolling.
                  Culprits: font-size + line-height (1.1x) + margin-bottom (8px default).
                  If using dashboard CSS for custom font size, add
                  `margin-bottom: 0 !important` to .header-line.
                  Formula: font_size * 1.1 + margin <= container_height (60px).
                  Recommended CSS: font-size 3.3rem (58px with line-height), margin-bottom: 0.

                country_map — required parameters:
                  - select_country: "russia"
                  - entity: "<column with ISO 3166-2 codes>"
                  - metric: {...}
                  Map tooltip (class .hover-popup) is clipped by the container
                  .dashboard-chart (overflow:hidden). Fix via dashboard CSS:
                  .dashboard-chart-id-{N} .dashboard-chart { overflow: visible !important; }
                  .hover-popup { z-index: 99999 !important; }

            query_context: JSON string with query context.
                Required for chart_get_data to work. Usually generated by the UI.
            dashboards: List of dashboard IDs to bind the chart to.
        """
        # Validation: deprecated viz_type and moment.js formats
        validation_error = _validate_chart_params(params, viz_type)
        if validation_error:
            return json.dumps({"error": validation_error}, ensure_ascii=False)
        qc_error = _validate_query_context(query_context)
        if qc_error:
            return json.dumps({"error": qc_error}, ensure_ascii=False)

        payload = {
            "slice_name": slice_name,
            "viz_type": viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
        }
        if params is not None:
            payload["params"] = params
        if query_context is not None:
            payload["query_context"] = query_context
        if dashboards is not None:
            payload["dashboards"] = dashboards
        result = await client.post("/api/v1/chart/", json_data=payload)

        # Auto-sync: add datasource_access to dashboard roles
        new_id = result.get("id")
        if new_id:
            sync = await auto_sync_chart_dashboards(client, chart_id=new_id, datasource_id=datasource_id)
            synced = [s for s in sync if s.get("synced_roles")]
            if synced:
                result["_auto_access_synced"] = synced

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_update(
        chart_id: int,
        slice_name: str | None = None,
        viz_type: str | None = None,
        params: str | None = None,
        query_context: str | None = None,
        dashboards: IntList | None = None,
        confirm_params_replace: bool = False,
    ) -> str:
        """Update an existing chart. Pass only the fields to change.

        Args:
            chart_id: ID of the chart to update.
            slice_name: New name.
            viz_type: New visualization type (see chart_create for the list of types).
            params: New JSON visualization parameters (replaces entirely).
                See chart_create for reference on numeric/time formats.
                IMPORTANT: params replaces ALL parameters — first get current ones
                via chart_get, modify the needed fields, and pass the full JSON.
                CRITICAL: for dates use D3 strftime format ("%Y-%m-%d"),
                NOT moment.js ("YYYY-MM-DD") — otherwise a literal will be shown!
            query_context: New JSON query context (replaces entirely).
                IMPORTANT: when changing params you should also update query_context,
                otherwise the chart will use the old query context.
            dashboards: New list of dashboard IDs (REPLACES all bindings).
            confirm_params_replace: Confirmation for replacing params (REQUIRED when passing params).
        """
        # Guard against partial params replacement
        if params is not None and not confirm_params_replace:
            return json.dumps(
                {
                    "error": (
                        "REJECTED: params replaces ALL chart parameters. "
                        'If you pass only the changed parameter (e.g. {"y_axis_format": "d"}), '
                        "all other settings (metrics, groupby, filters, colors) will be DESTROYED. "
                        "First get the current params via chart_get, modify the needed fields, "
                        "then pass the FULL JSON with confirm_params_replace=True."
                    )
                },
                ensure_ascii=False,
            )

        # Validation: deprecated viz_type and moment.js formats
        validation_error = _validate_chart_params(params, viz_type)
        if validation_error:
            return json.dumps({"error": validation_error}, ensure_ascii=False)
        qc_error = _validate_query_context(query_context)
        if qc_error:
            return json.dumps({"error": qc_error}, ensure_ascii=False)

        payload = {}
        if slice_name is not None:
            payload["slice_name"] = slice_name
        if viz_type is not None:
            payload["viz_type"] = viz_type
        if params is not None:
            payload["params"] = params
        if query_context is not None:
            payload["query_context"] = query_context
        if dashboards is not None:
            payload["dashboards"] = dashboards
        result = await client.put(f"/api/v1/chart/{chart_id}", json_data=payload)

        # Auto-sync: when dashboards or datasource change
        if dashboards is not None:
            sync = await auto_sync_chart_dashboards(client, chart_id=chart_id)
            synced = [s for s in sync if s.get("synced_roles")]
            if synced:
                result["_auto_access_synced"] = synced

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_delete(
        chart_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a chart by ID. The chart will be removed from all dashboards.

        Args:
            chart_id: ID of the chart to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                chart_info = await client.get(f"/api/v1/chart/{chart_id}")
                chart = chart_info.get("result", {})
                chart_name = chart.get("slice_name", "?")
                dashboards = chart.get("dashboards", [])
                dash_names = [d.get("dashboard_title", f"ID={d.get('id')}") for d in dashboards]
            except Exception:
                chart_name = f"ID={chart_id}"
                dash_names = []
            msg = f"REJECTED: deletion of chart '{chart_name}' (ID={chart_id})"
            if dash_names:
                msg += f", bound to dashboards: {dash_names}"
            msg += ". Pass confirm_delete=True to confirm."
            return json.dumps({"error": msg}, ensure_ascii=False)

        result = await client.delete(f"/api/v1/chart/{chart_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_data(
        query_context: str,
    ) -> str:
        """Execute an arbitrary query against a dataset and retrieve data.

        Allows fetching data directly from a dataset without creating a chart.
        To get data from an existing chart, use chart_get_data instead.

        Args:
            query_context: JSON string with the query context. Format:
                {
                    "datasource": {"id": <dataset_id>, "type": "table"},
                    "queries": [{
                        "columns": ["col1", "col2"],
                        "metrics": [{"label": "count", "expressionType": "SIMPLE",
                                     "aggregate": "COUNT", "column": {"column_name": "id"}}],
                        "filters": [{"col": "status", "op": "==", "val": "active"}],
                        "orderby": [["col1", true]],
                        "row_limit": 100,
                        "time_range": "Last 7 days"
                    }],
                    "result_format": "json",
                    "result_type": "full"
                }
                IMPORTANT: time_range is specified at the QUERY level, NOT inside extras.
                Allowed time_range values: "Last day", "Last week", "Last month",
                "Last year", "No filter", or "2024-01-01 : 2024-12-31".
        """
        payload, err = parse_json_arg(query_context, "query_context")
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        result = await client.post("/api/v1/chart/data", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_get_data(chart_id: int) -> str:
        """Get data from a specific saved chart by its ID.

        IMPORTANT: works only if the chart was saved with query_context
        (usually after opening and saving via the Superset UI). If query_context
        is missing, use superset_chart_data with a manually constructed query.

        Args:
            chart_id: Chart ID.
        """
        result = await client.get(f"/api/v1/chart/{chart_id}/data/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_export(
        chart_ids: str,
    ) -> str:
        """Export charts with all dependencies (datasets, databases) as a ZIP file.

        The result is a base64-encoded ZIP file. It can be imported back
        via superset_chart_import.

        Args:
            chart_ids: Chart IDs separated by commas (e.g. "1,2,3").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        params = {"q": f"[{chart_ids}]"}
        raw = await client.get_raw("/api/v1/chart/export/", params=params)
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
    async def superset_chart_import(
        file_path: str,
        overwrite: bool = False,
    ) -> str:
        """Import charts from a ZIP file (created via export).

        The ZIP must contain YAML files with chart configurations and dependencies.

        Args:
            file_path: Absolute path to the ZIP file on disk.
            overwrite: Overwrite existing objects with the same UUID (default False).
        """
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/chart/import/",
                files=files,
                data=data,
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_copy(
        chart_id: int,
        slice_name: str,
        dashboards: IntList | None = None,
    ) -> str:
        """Create a copy of an existing chart with a new name.

        Copies all visualization parameters, type, dataset, and query_context.
        Dashboard bindings are NOT copied — specify new ones via the dashboards parameter.

        Args:
            chart_id: ID of the source chart to copy.
            slice_name: Name for the new copy.
            dashboards: List of dashboard IDs to bind the copy to (optional).
        """
        source = await client.get(f"/api/v1/chart/{chart_id}")
        chart = source.get("result", {})

        payload = {
            "slice_name": slice_name,
            "viz_type": chart.get("viz_type", "table"),
            "datasource_id": chart.get("datasource_id"),
            "datasource_type": chart.get("datasource_type", "table"),
        }
        if chart.get("params"):
            payload["params"] = chart["params"]
        if chart.get("query_context"):
            payload["query_context"] = chart["query_context"]
        if dashboards is not None:
            payload["dashboards"] = dashboards

        result = await client.post("/api/v1/chart/", json_data=payload)
        new_id = result.get("id")
        return json.dumps(
            {"status": "ok", "source_id": chart_id, "new_id": new_id, "slice_name": slice_name},
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_chart_cache_warmup(
        chart_id: int,
        dashboard_id: int | None = None,
    ) -> str:
        """Warm up the cache for a chart.

        Useful for speeding up loading of frequently used charts.

        Args:
            chart_id: ID of the chart to warm up.
            dashboard_id: Dashboard ID for filter context (optional).
        """
        payload = {"chart_id": chart_id}
        if dashboard_id is not None:
            payload["dashboard_id"] = dashboard_id
        result = await client.put(
            "/api/v1/chart/warm_up_cache",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)
