"""Security management tools: users, roles, permissions, RLS."""

import json

from mcp_superset.tools.helpers import find_datasource_permissions
from mcp_superset.tools.types import IntList


def register_security_tools(mcp):
    """Register all security-related MCP tools on the given server instance."""
    from mcp_superset.server import superset_client as client

    # === Current user ===

    @mcp.tool
    async def superset_get_current_user() -> str:
        """Get information about the current authenticated user (mcp_service).

        Returns:
            JSON with username, name, email, roles, and active status.
        """
        result = await client.get("/api/v1/me/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_get_current_user_roles() -> str:
        """Get the list of roles for the current user (mcp_service).

        Returns:
            JSON with IDs and names of all assigned roles.
        """
        result = await client.get("/api/v1/me/roles/")
        return json.dumps(result, ensure_ascii=False)

    # === Users ===

    @mcp.tool
    async def superset_user_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Get the list of Superset users.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for searching. Examples:
                - By username: (filters:!((col:username,opr:ct,value:admin)))
                - Active only: (filters:!((col:active,opr:eq,value:!t)))
                - By role: (filters:!((col:roles,opr:rel_m_m,value:1)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/users/", params=params)
        else:
            result = await client.get_page("/api/v1/security/users/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_get(user_id: int) -> str:
        """Get detailed information about a user by ID.

        IMPORTANT: if the ID is unknown, call superset_user_list first.

        Args:
            user_id: User ID (integer from user_list result).
        """
        result = await client.get(f"/api/v1/security/users/{user_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_create(
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str,
        roles: IntList | None = None,
        active: bool = True,
    ) -> str:
        """Create a new Superset user.

        Args:
            first_name: User's first name.
            last_name: User's last name.
            username: Login name (must be unique).
            email: Email address (must be unique).
            password: Password.
            roles: List of role IDs to assign (from superset_role_list).
                If not specified, the default role (Public) will be assigned.
            active: Whether the account is active (defaults to True).
        """
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "email": email,
            "password": password,
            "active": active,
        }
        if roles is not None:
            payload["roles"] = roles
        result = await client.post("/api/v1/security/users/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_update(
        user_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        roles: IntList | None = None,
        active: bool | None = None,
        confirm_roles_replace: bool = False,
    ) -> str:
        """Update a user. Only pass the fields you want to change.

        IMPORTANT: roles REPLACES the entire role list (does not append).
        To add a single role: get the current roles via user_get,
        add the new ID to the list, then pass the full list.

        Args:
            user_id: ID of the user to update.
            first_name: New first name.
            last_name: New last name.
            email: New email (must be unique).
            roles: New list of role IDs (REPLACES all current roles).
            active: Activate/deactivate the account.
            confirm_roles_replace: Confirmation for role replacement (REQUIRED when passing roles).
        """
        # Guard against accidental role loss
        if roles is not None and not confirm_roles_replace:
            try:
                user_info = await client.get(f"/api/v1/security/users/{user_id}")
                user = user_info.get("result", {})
                current_roles = [{"id": r["id"], "name": r.get("name", "?")} for r in user.get("roles", [])]
            except Exception:
                current_roles = "failed to retrieve"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: roles will REPLACE all current user roles. "
                        f"Current roles: {current_roles}. "
                        f"Requested roles: {roles}. "
                        f"To add a single role, include its ID in the full list. "
                        f"Pass confirm_roles_replace=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        payload = {}
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if email is not None:
            payload["email"] = email
        if roles is not None:
            payload["roles"] = roles
        if active is not None:
            payload["active"] = active
        result = await client.put(f"/api/v1/security/users/{user_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_delete(
        user_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a Superset user. This operation is irreversible.

        CRITICAL: deleting the current service account (mcp_service)
        will lock out the entire MCP server. Deleting dashboard owners
        may change access to those dashboards.

        Args:
            user_id: ID of the user to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            # Retrieve user info for the warning message
            try:
                user_info = await client.get(f"/api/v1/security/users/{user_id}")
                user = user_info.get("result", {})
                username = user.get("username", "?")
                roles = [r.get("name", "?") for r in user.get("roles", [])]
            except Exception:
                username = f"ID={user_id}"
                roles = []
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deleting user '{username}' "
                        f"(roles: {roles}) is irreversible. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        # Guard against deleting the current service account
        try:
            me = await client.get("/api/v1/me/")
            me_result = me.get("result", {})
            if me_result.get("pk") == user_id or me_result.get("id") == user_id:
                return json.dumps(
                    {
                        "error": (
                            "BLOCKED: cannot delete the current service account "
                            f"('{me_result.get('username', 'mcp_service')}'). "
                            "This would lock out the entire MCP server."
                        )
                    },
                    ensure_ascii=False,
                )
        except Exception:
            pass

        result = await client.delete(f"/api/v1/security/users/{user_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Roles ===

    @mcp.tool
    async def superset_role_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Get the list of Superset roles.

        Standard roles: Admin, Alpha, Gamma, sql_lab, Public.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for searching. Examples:
                - By name: (filters:!((col:name,opr:ct,value:admin)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/roles/", params=params)
        else:
            result = await client.get_page("/api/v1/security/roles/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_get(role_id: int) -> str:
        """Get role information by ID.

        IMPORTANT: if the ID is unknown, call superset_role_list first.

        Args:
            role_id: Role ID (integer from role_list result).
        """
        result = await client.get(f"/api/v1/security/roles/{role_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_create(name: str) -> str:
        """Create a new role (without permissions). Permissions are added via role_permission_add.

        Args:
            name: Role name (must be unique).
        """
        result = await client.post("/api/v1/security/roles/", json_data={"name": name})
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_update(role_id: int, name: str) -> str:
        """Rename a role.

        Args:
            role_id: ID of the role to rename.
            name: New role name.
        """
        result = await client.put(f"/api/v1/security/roles/{role_id}", json_data={"name": name})
        return json.dumps(result, ensure_ascii=False)

    # Protected roles that cannot be deleted
    _PROTECTED_ROLE_NAMES = frozenset(
        {
            "Admin",
            "Alpha",
            "Gamma",
            "Public",
            "sql_lab",
            "no_access",
            "la_region_all",
        }
    )
    _PROTECTED_ROLE_PREFIXES = ("la_report_", "la_region_", "la_developer")

    @mcp.tool
    async def superset_role_delete(
        role_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a role. Users with this role will lose the associated permissions.

        BLOCKED for system roles: Admin, Alpha, Gamma, Public,
        sql_lab, no_access, la_report_*, la_region_*, la_developer.

        Args:
            role_id: ID of the role to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        # Retrieve role info
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", "?")
        except Exception:
            role_name = f"ID={role_id}"

        # Block protected roles
        if role_name in _PROTECTED_ROLE_NAMES or any(role_name.startswith(p) for p in _PROTECTED_ROLE_PREFIXES):
            return json.dumps(
                {
                    "error": (
                        f"BLOCKED: role '{role_name}' (ID={role_id}) "
                        f"is a system role or part of the project's RLS architecture. "
                        f"Deleting this role may break user access "
                        f"to dashboards or remove RLS data protection."
                    )
                },
                ensure_ascii=False,
            )

        if not confirm_delete:
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deleting role '{role_name}' (ID={role_id}). "
                        f"All users with this role will lose the associated permissions. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/security/roles/{role_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Permissions ===

    @mcp.tool
    async def superset_permission_list(
        page: int = 0,
        page_size: int = 100,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Get the list of all available permissions (permission_view_menu) in Superset.

        Each permission is a combination of an action (can_read, can_write, can_explore)
        and a resource.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (defaults to 100).
            q: RISON filter for searching.
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/permissions/", params=params)
        else:
            result = await client.get_page("/api/v1/security/permissions/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_permissions_get(role_id: int) -> str:
        """Get the current list of permissions for a role.

        IMPORTANT: call this BEFORE role_permission_add to avoid losing existing permissions.

        Args:
            role_id: Role ID.
        """
        result = await client.get(f"/api/v1/security/roles/{role_id}/permissions/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_permission_add(
        role_id: int,
        permission_view_menu_ids: IntList,
        confirm_full_replace: bool = False,
    ) -> str:
        """Set the permissions list for a role (FULL REPLACEMENT).

        WARNING: this endpoint REPLACES ALL role permissions with the provided list!
        To ADD a single permission:
        1. Call superset_role_permissions_get to get current permission IDs
        2. Add the new ID to the list
        3. Pass the FULL list to this tool with confirm_full_replace=True

        Args:
            role_id: Role ID.
            permission_view_menu_ids: FULL list of permission IDs for the role.
                Permission IDs can be obtained via superset_permission_list.
            confirm_full_replace: Confirmation for full permission replacement (REQUIRED).
        """
        if not confirm_full_replace:
            return json.dumps(
                {
                    "error": (
                        "REJECTED: confirm_full_replace=True not provided. "
                        "POST /api/v1/security/roles/{id}/permissions REPLACES ALL "
                        "role permissions with the provided list. To add a single permission: "
                        "1) Get current ones via role_permissions_get, "
                        "2) Add the new ID to the list, "
                        "3) Pass the FULL list with confirm_full_replace=True."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.post(
            f"/api/v1/security/roles/{role_id}/permissions",
            json_data={"permission_view_menu_ids": permission_view_menu_ids},
        )
        return json.dumps(result, ensure_ascii=False)

    # === Dashboard access management ===

    @mcp.tool
    async def superset_dashboard_grant_role_access(
        dashboard_id: int,
        role_id: int,
        confirm_grant: bool = False,
    ) -> str:
        """Grant a role access to a dashboard by automatically finding all dashboard
        datasets and adding datasource_access to the role's permissions.

        The tool automatically:
        1. Finds all datasets used by the dashboard's charts
        2. Finds permission_view_menu_id for datasource_access of each dataset
        3. Checks which permissions the role already has
        4. Adds missing datasource_access to the role's existing permissions
        5. Checks for RLS rules on the datasets and warns if missing

        Without confirm_grant=True, shows the action plan (dry-run).

        Args:
            dashboard_id: Dashboard ID (from dashboard_list).
            role_id: ID of the role to grant access to (from role_list).
            confirm_grant: True to apply changes. False for dry-run only.
        """
        errors: list[str] = []

        # 1. Verify dashboard
        try:
            dash_info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            dash = dash_info.get("result", {})
            dash_title = dash.get("dashboard_title", f"ID={dashboard_id}")
            dash_slug = dash.get("slug", "")
        except Exception as e:
            return json.dumps({"error": f"Dashboard ID={dashboard_id} not found: {e}"}, ensure_ascii=False)

        # 2. Verify role
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
        except Exception as e:
            return json.dumps({"error": f"Role ID={role_id} not found: {e}"}, ensure_ascii=False)

        # 3. Get dashboard datasets
        try:
            ds_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
            datasets = ds_resp.get("result", [])
        except Exception as e:
            return json.dumps(
                {"error": (f"Failed to get datasets for dashboard '{dash_title}': {e}")}, ensure_ascii=False
            )

        if not datasets:
            return json.dumps(
                {
                    "error": (
                        f"Dashboard '{dash_title}' (ID={dashboard_id}) has no datasets. It may not have any charts."
                    )
                },
                ensure_ascii=False,
            )

        dataset_ids = {ds["id"] for ds in datasets}
        dataset_names = {ds["id"]: f"{ds.get('schema', '?')}.{ds.get('table_name', '?')}" for ds in datasets}

        # 4. Find datasource_access for each dataset
        ds_perms = await find_datasource_permissions(client, dataset_ids)

        missing_ds = dataset_ids - ds_perms.keys()
        if missing_ds:
            missing_names = [f"{dataset_names.get(d, '?')} (id:{d})" for d in missing_ds]
            errors.append(
                f"datasource_access not found for datasets: "
                f"{', '.join(missing_names)}. "
                f"The datasets may have been created recently and Superset "
                f"has not generated permission_view_menu yet. "
                f"Try opening the dataset in the Superset UI."
            )

        # 5. Get current role permissions
        try:
            role_perms_resp = await client.get(f"/api/v1/security/roles/{role_id}/permissions/")
            role_perms = role_perms_resp.get("result", [])
            if isinstance(role_perms, str):
                role_perms = json.loads(role_perms)
            current_perm_ids = {p["id"] for p in role_perms}
        except Exception as e:
            return json.dumps({"error": f"Failed to get permissions for role '{role_name}': {e}"}, ensure_ascii=False)

        # 6. Determine which datasource_access need to be added
        already_have = []
        to_add = []
        for ds_id, perm_id in ds_perms.items():
            ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
            if perm_id in current_perm_ids:
                already_have.append(f"  ✓ {ds_name} (dataset={ds_id}, perm={perm_id})")
            else:
                to_add.append(
                    {
                        "dataset_id": ds_id,
                        "dataset_name": ds_name,
                        "perm_id": perm_id,
                    }
                )

        # 7. Check RLS on datasets
        rls_warnings: list[str] = []
        try:
            rls_resp = await client.get_all("/api/v1/rowlevelsecurity/", params={})
            all_rls = rls_resp.get("result", [])
            if isinstance(all_rls, str):
                all_rls = json.loads(all_rls)

            for ds_id in dataset_ids:
                ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
                has_rls = any(ds_id in [t.get("id", -1) for t in rls.get("tables", [])] for rls in all_rls)
                if not has_rls:
                    rls_warnings.append(
                        f"  ⚠ {ds_name} (id:{ds_id}) — no RLS rules. Users with role '{role_name}' will see ALL data."
                    )
        except Exception:
            rls_warnings.append("  ⚠ Failed to check RLS rules")

        # 8. Build the report
        report_lines = [
            f"Dashboard: {dash_title} (ID={dashboard_id}, slug={dash_slug})",
            f"Role: {role_name} (ID={role_id})",
            f"Dashboard datasets: {len(dataset_ids)}",
            "",
        ]

        if already_have:
            report_lines.append("Already has access:")
            report_lines.extend(already_have)
            report_lines.append("")

        if to_add:
            report_lines.append("Will be added:")
            for item in to_add:
                report_lines.append(
                    f"  + {item['dataset_name']} (dataset={item['dataset_id']}, perm={item['perm_id']})"
                )
            report_lines.append("")
        else:
            report_lines.append("All datasource_access already present in the role — nothing to add.")
            report_lines.append("")

        if rls_warnings:
            report_lines.append("RLS warnings:")
            report_lines.extend(rls_warnings)
            report_lines.append("")

        if errors:
            report_lines.append("Errors:")
            for e in errors:
                report_lines.append(f"  ✗ {e}")
            report_lines.append("")

        # 9. Apply or show dry-run
        if not to_add:
            return json.dumps(
                {
                    "result": "\n".join(report_lines),
                    "status": "nothing_to_do",
                },
                ensure_ascii=False,
            )

        if not confirm_grant:
            report_lines.append("Pass confirm_grant=True to apply the changes.")
            return json.dumps(
                {
                    "result": "\n".join(report_lines),
                    "status": "dry_run",
                },
                ensure_ascii=False,
            )

        # Apply: current permissions + new datasource_access
        new_perm_ids = sorted(current_perm_ids | {item["perm_id"] for item in to_add})
        try:
            await client.post(
                f"/api/v1/security/roles/{role_id}/permissions",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )
        except Exception as e:
            return json.dumps(
                {
                    "error": f"Error updating role permissions: {e}",
                    "report": "\n".join(report_lines),
                },
                ensure_ascii=False,
            )

        added_names = [item["dataset_name"] for item in to_add]
        report_lines.append(
            f"✓ Done! Added {len(to_add)} datasource_access to role '{role_name}': {', '.join(added_names)}"
        )

        return json.dumps(
            {
                "result": "\n".join(report_lines),
                "status": "applied",
                "added_count": len(to_add),
                "total_permissions": len(new_perm_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_dashboard_revoke_role_access(
        dashboard_id: int,
        role_id: int,
        confirm_revoke: bool = False,
    ) -> str:
        """Revoke a role's access to a dashboard by removing datasource_access
        for the dashboard's datasets from the role's permissions.

        IMPORTANT: if a dataset is used by other dashboards that the role also
        has access to, revoking will break access to those dashboards as well.
        The tool will check and warn about this.

        Without confirm_revoke=True, shows the action plan (dry-run).

        Args:
            dashboard_id: Dashboard ID (from dashboard_list).
            role_id: ID of the role to revoke access from (from role_list).
            confirm_revoke: True to apply. False for dry-run only.
        """
        # 1. Verify dashboard
        try:
            dash_info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            dash = dash_info.get("result", {})
            dash_title = dash.get("dashboard_title", f"ID={dashboard_id}")
        except Exception as e:
            return json.dumps({"error": f"Dashboard ID={dashboard_id} not found: {e}"}, ensure_ascii=False)

        # 2. Verify role
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
        except Exception as e:
            return json.dumps({"error": f"Role ID={role_id} not found: {e}"}, ensure_ascii=False)

        # 3. Get dashboard datasets
        try:
            ds_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
            datasets = ds_resp.get("result", [])
        except Exception as e:
            return json.dumps({"error": f"Failed to get dashboard datasets: {e}"}, ensure_ascii=False)

        if not datasets:
            return json.dumps({"error": f"Dashboard '{dash_title}' has no datasets."}, ensure_ascii=False)

        dataset_ids = {ds["id"] for ds in datasets}
        dataset_names = {ds["id"]: f"{ds.get('schema', '?')}.{ds.get('table_name', '?')}" for ds in datasets}

        # 4. Find datasource_access permission_view_menu_id
        ds_perms = await find_datasource_permissions(client, dataset_ids)
        perm_ids_to_remove = set(ds_perms.values())

        if not perm_ids_to_remove:
            return json.dumps({"error": "No datasource_access found for the dashboard's datasets."}, ensure_ascii=False)

        # 5. Get current role permissions
        try:
            role_perms_resp = await client.get(f"/api/v1/security/roles/{role_id}/permissions/")
            role_perms = role_perms_resp.get("result", [])
            if isinstance(role_perms, str):
                role_perms = json.loads(role_perms)
            current_perm_ids = {p["id"] for p in role_perms}
        except Exception as e:
            return json.dumps({"error": f"Failed to get role permissions: {e}"}, ensure_ascii=False)

        # Determine which permissions will actually be removed (intersection)
        actual_remove = perm_ids_to_remove & current_perm_ids
        if not actual_remove:
            return json.dumps(
                {
                    "result": (
                        f"Role '{role_name}' does not have datasource_access "
                        f"to dashboard '{dash_title}' datasets — nothing to revoke."
                    ),
                    "status": "nothing_to_do",
                },
                ensure_ascii=False,
            )

        # 6. Build the report
        report_lines = [
            f"Dashboard: {dash_title} (ID={dashboard_id})",
            f"Role: {role_name} (ID={role_id})",
            "",
            "Will be removed:",
        ]
        for ds_id, perm_id in ds_perms.items():
            if perm_id in actual_remove:
                ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
                report_lines.append(f"  - {ds_name} (dataset={ds_id}, perm={perm_id})")
        report_lines.append("")

        if not confirm_revoke:
            report_lines.append("Pass confirm_revoke=True to apply.")
            return json.dumps(
                {
                    "result": "\n".join(report_lines),
                    "status": "dry_run",
                },
                ensure_ascii=False,
            )

        # 7. Apply
        new_perm_ids = sorted(current_perm_ids - actual_remove)
        try:
            await client.post(
                f"/api/v1/security/roles/{role_id}/permissions",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )
        except Exception as e:
            return json.dumps(
                {
                    "error": f"Error updating role permissions: {e}",
                },
                ensure_ascii=False,
            )

        report_lines.append(f"✓ Done! Removed {len(actual_remove)} datasource_access from role '{role_name}'.")

        return json.dumps(
            {
                "result": "\n".join(report_lines),
                "status": "applied",
                "removed_count": len(actual_remove),
            },
            ensure_ascii=False,
        )

    # === Row Level Security (RLS) ===

    @mcp.tool
    async def superset_rls_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Get the list of Row Level Security rules.

        RLS adds a WHERE clause to queries for specific roles.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for searching.
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/rowlevelsecurity/", params=params)
        else:
            result = await client.get_page("/api/v1/rowlevelsecurity/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_get(rls_id: int) -> str:
        """Get detailed information about an RLS rule by ID.

        Args:
            rls_id: RLS rule ID (from rls_list).
        """
        result = await client.get(f"/api/v1/rowlevelsecurity/{rls_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_create(
        name: str,
        clause: str,
        tables: IntList,
        roles: IntList,
        filter_type: str = "Regular",
        group_key: str | None = None,
        description: str | None = None,
    ) -> str:
        """Create a Row Level Security rule.

        RLS automatically adds a WHERE clause to queries for users
        with the specified roles accessing the specified datasets.

        Args:
            name: Rule name.
            clause: SQL WHERE condition without the WHERE keyword. Examples:
                - "region = 'Moscow'"
                - "user_id = {{ current_user_id() }}"
                - "status IN ('active', 'pending')"
            tables: List of dataset IDs the rule applies to (from dataset_list).
            roles: List of role IDs the rule applies to (from role_list).
            filter_type: Filter type:
                - "Regular" (default) — additional restriction for the specified roles
                - "Base" — base filter applied to all users
            group_key: Rule grouping key (optional).
            description: Rule description (optional).
        """
        # Warning for Base filter_type
        if filter_type == "Base":
            return json.dumps(
                {
                    "error": (
                        "REJECTED: filter_type='Base' applies to ALL users "
                        "and may override existing Regular rules (deny-by-default). "
                        "This project's architecture uses only 'Regular'. "
                        "Change filter_type to 'Regular', or — if a Base rule is "
                        "truly required — create it directly via the Superset UI."
                    )
                },
                ensure_ascii=False,
            )

        payload = {
            "name": name,
            "filter_type": filter_type,
            "clause": clause,
            "tables": tables,
            "roles": roles,
        }
        if group_key is not None:
            payload["group_key"] = group_key
        if description is not None:
            payload["description"] = description
        result = await client.post("/api/v1/rowlevelsecurity/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_update(
        rls_id: int,
        name: str | None = None,
        filter_type: str | None = None,
        clause: str | None = None,
        tables: IntList | None = None,
        roles: IntList | None = None,
        group_key: str | None = None,
        description: str | None = None,
    ) -> str:
        """Update an RLS rule.

        CRITICAL: Superset PUT API REPLACES the roles and tables fields entirely.
        If you pass only roles without tables, Superset will WIPE tables with an
        empty list (and vice versa). Therefore, this tool REQUIRES passing
        roles and tables simultaneously if either one is specified.

        For safe updates:
        1. First get the current rule via rls_list
        2. Pass BOTH roles AND tables (even if you only change one)

        Args:
            rls_id: ID of the RLS rule to update.
            name: New name.
            filter_type: New type: "Regular" or "Base".
            clause: New SQL WHERE condition (without the WHERE keyword).
            tables: List of dataset IDs (REPLACES all current). REQUIRED if roles is specified.
            roles: List of role IDs (REPLACES all current). REQUIRED if tables is specified.
            group_key: New grouping key.
            description: New description.
        """
        # Guard against data loss: roles and tables must be passed together
        if (roles is not None) != (tables is not None):
            missing = "tables" if tables is None else "roles"
            provided = "roles" if tables is None else "tables"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: only {provided} was passed without {missing}. "
                        f"Superset PUT API REPLACES both fields — if {missing} is not passed, "
                        f"it will be wiped with an empty list. "
                        f"First get the current values via rls_list, "
                        f"then pass BOTH roles AND tables simultaneously."
                    )
                },
                ensure_ascii=False,
            )

        payload = {}
        if name is not None:
            payload["name"] = name
        if filter_type is not None:
            payload["filter_type"] = filter_type
        if clause is not None:
            payload["clause"] = clause
        if tables is not None:
            payload["tables"] = tables
        if roles is not None:
            payload["roles"] = roles
        if group_key is not None:
            payload["group_key"] = group_key
        if description is not None:
            payload["description"] = description
        result = await client.put(f"/api/v1/rowlevelsecurity/{rls_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_delete(
        rls_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete an RLS rule. Restrictions for associated roles will be lifted.

        CRITICAL: deleting a deny-by-default rule (clause='1=0') will immediately
        expose ALL data to users with those roles.

        Args:
            rls_id: ID of the RLS rule to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                rls_info = await client.get(f"/api/v1/rowlevelsecurity/{rls_id}")
                rls = rls_info.get("result", {})
                name = rls.get("name", "?")
                clause = rls.get("clause", "?")
                roles = [r.get("name", "?") for r in rls.get("roles", [])]
                tables = [t.get("table_name", "?") for t in rls.get("tables", [])]
            except Exception:
                name, clause, roles, tables = f"ID={rls_id}", "?", [], []
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deleting RLS rule '{name}' "
                        f"(clause: '{clause}', roles: {roles}, datasets: {tables}). "
                        f"Deletion will change data access for the specified roles. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/rowlevelsecurity/{rls_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Bulk operations ===

    @mcp.tool
    async def superset_bulk_user_role_add(
        role_id: int,
        user_ids: IntList | None = None,
        filter_role_id: int | None = None,
        exclude_admin: bool = True,
        confirm: bool = False,
    ) -> str:
        """Add a role to multiple users (without removing existing roles).

        Select users by explicit IDs or by current role filter.

        Args:
            role_id: Role ID to add.
            user_ids: Explicit list of user IDs. If None, uses filter_role_id.
            filter_role_id: Add to all users who have this role. Ignored if user_ids is set.
            exclude_admin: Skip Admin users (default True).
            confirm: True to apply. False for dry-run.
        """
        # Resolve target users
        all_users_resp = await client.get_all("/api/v1/security/users/")
        all_users = all_users_resp.get("result", [])

        targets = []
        for u in all_users:
            role_names = [r["name"] for r in u.get("roles", [])]
            role_ids_set = {r["id"] for r in u.get("roles", [])}
            if exclude_admin and "Admin" in role_names:
                continue
            if role_id in role_ids_set:
                continue  # already has this role
            if user_ids is not None:
                if u["id"] in user_ids:
                    targets.append(u)
            elif filter_role_id is not None:
                if filter_role_id in role_ids_set:
                    targets.append(u)
            else:
                return json.dumps({"error": "Specify user_ids or filter_role_id"})

        if not confirm:
            # Resolve role name
            try:
                role_info = await client.get(f"/api/v1/security/roles/{role_id}")
                role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
            except Exception:
                role_name = f"ID={role_id}"
            return json.dumps(
                {
                    "status": "dry_run",
                    "role": role_name,
                    "users_to_update": len(targets),
                    "sample": [{"id": u["id"], "username": u.get("username", "?")} for u in targets[:10]],
                    "message": f"Will ADD role '{role_name}' to {len(targets)} users. Pass confirm=True to apply.",
                },
                ensure_ascii=False,
            )

        ok, fail = 0, 0
        errors = []
        for u in targets:
            current_role_ids = [r["id"] for r in u.get("roles", [])]
            new_roles = list(set(current_role_ids + [role_id]))
            try:
                await client.put(
                    f"/api/v1/security/users/{u['id']}",
                    json_data={"roles": new_roles},
                )
                ok += 1
            except Exception as e:
                fail += 1
                errors.append({"user_id": u["id"], "error": str(e)})

        return json.dumps(
            {
                "status": "applied",
                "ok": ok,
                "fail": fail,
                "errors": errors[:10],
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_bulk_user_role_remove(
        role_id: int,
        user_ids: IntList | None = None,
        exclude_admin: bool = True,
        confirm: bool = False,
    ) -> str:
        """Remove a role from multiple users.

        Args:
            role_id: Role ID to remove.
            user_ids: Explicit list of user IDs. If None, removes from ALL users who have it.
            exclude_admin: Skip Admin users (default True).
            confirm: True to apply. False for dry-run.
        """
        all_users_resp = await client.get_all("/api/v1/security/users/")
        all_users = all_users_resp.get("result", [])

        targets = []
        for u in all_users:
            role_names = [r["name"] for r in u.get("roles", [])]
            role_ids_set = {r["id"] for r in u.get("roles", [])}
            if exclude_admin and "Admin" in role_names:
                continue
            if role_id not in role_ids_set:
                continue  # doesn't have this role
            if user_ids is not None and u["id"] not in user_ids:
                continue
            targets.append(u)

        if not confirm:
            try:
                role_info = await client.get(f"/api/v1/security/roles/{role_id}")
                role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
            except Exception:
                role_name = f"ID={role_id}"
            return json.dumps(
                {
                    "status": "dry_run",
                    "role": role_name,
                    "users_to_update": len(targets),
                    "sample": [{"id": u["id"], "username": u.get("username", "?")} for u in targets[:10]],
                    "message": f"Will REMOVE role '{role_name}' from {len(targets)} users. Pass confirm=True to apply.",
                },
                ensure_ascii=False,
            )

        ok, fail = 0, 0
        errors = []
        for u in targets:
            current_role_ids = [r["id"] for r in u.get("roles", [])]
            new_roles = [r for r in current_role_ids if r != role_id]
            if not new_roles:
                fail += 1
                errors.append({"user_id": u["id"], "error": "Cannot remove last role"})
                continue
            try:
                await client.put(
                    f"/api/v1/security/users/{u['id']}",
                    json_data={"roles": new_roles},
                )
                ok += 1
            except Exception as e:
                fail += 1
                errors.append({"user_id": u["id"], "error": str(e)})

        return json.dumps(
            {
                "status": "applied",
                "ok": ok,
                "fail": fail,
                "errors": errors[:10],
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_bulk_user_role_replace(
        old_role_id: int,
        new_role_id: int,
        exclude_admin: bool = True,
        confirm: bool = False,
    ) -> str:
        """Replace one role with another for all users who have it.

        Adds new_role_id first, then removes old_role_id (safe two-step).

        Args:
            old_role_id: Role ID to replace.
            new_role_id: Role ID to set instead.
            exclude_admin: Skip Admin users (default True).
            confirm: True to apply. False for dry-run.
        """
        all_users_resp = await client.get_all("/api/v1/security/users/")
        all_users = all_users_resp.get("result", [])

        targets = []
        for u in all_users:
            role_names = [r["name"] for r in u.get("roles", [])]
            role_ids_set = {r["id"] for r in u.get("roles", [])}
            if exclude_admin and "Admin" in role_names:
                continue
            if old_role_id in role_ids_set:
                targets.append(u)

        if not confirm:
            try:
                old_info = await client.get(f"/api/v1/security/roles/{old_role_id}")
                old_name = old_info.get("result", {}).get("name", f"ID={old_role_id}")
            except Exception:
                old_name = f"ID={old_role_id}"
            try:
                new_info = await client.get(f"/api/v1/security/roles/{new_role_id}")
                new_name = new_info.get("result", {}).get("name", f"ID={new_role_id}")
            except Exception:
                new_name = f"ID={new_role_id}"
            return json.dumps(
                {
                    "status": "dry_run",
                    "old_role": old_name,
                    "new_role": new_name,
                    "users_to_update": len(targets),
                    "sample": [{"id": u["id"], "username": u.get("username", "?")} for u in targets[:10]],
                    "message": (
                        f"Will REPLACE role '{old_name}' with '{new_name}' "
                        f"for {len(targets)} users. Pass confirm=True to apply."
                    ),
                },
                ensure_ascii=False,
            )

        ok, fail = 0, 0
        errors = []
        for u in targets:
            current_role_ids = [r["id"] for r in u.get("roles", [])]
            new_roles = list(set([r for r in current_role_ids if r != old_role_id] + [new_role_id]))
            try:
                await client.put(
                    f"/api/v1/security/users/{u['id']}",
                    json_data={"roles": new_roles},
                )
                ok += 1
            except Exception as e:
                fail += 1
                errors.append({"user_id": u["id"], "error": str(e)})

        return json.dumps(
            {
                "status": "applied",
                "ok": ok,
                "fail": fail,
                "errors": errors[:10],
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_role_copy_permissions(
        source_role_id: int,
        target_role_id: int,
        confirm: bool = False,
    ) -> str:
        """Copy all permissions from one role to another (full replacement).

        Args:
            source_role_id: Role to copy permissions FROM.
            target_role_id: Role to copy permissions TO (existing permissions will be REPLACED).
            confirm: True to apply. False for dry-run.
        """
        # Get source permissions
        source_resp = await client.get(f"/api/v1/security/roles/{source_role_id}/permissions/")
        source_perms = source_resp.get("result", [])
        perm_ids = []
        for p in source_perms:
            if isinstance(p, dict) and "id" in p:
                perm_ids.append(p["id"])
            elif isinstance(p, int):
                perm_ids.append(p)

        if not confirm:
            try:
                src_info = await client.get(f"/api/v1/security/roles/{source_role_id}")
                src_name = src_info.get("result", {}).get("name", f"ID={source_role_id}")
            except Exception:
                src_name = f"ID={source_role_id}"
            try:
                tgt_info = await client.get(f"/api/v1/security/roles/{target_role_id}")
                tgt_name = tgt_info.get("result", {}).get("name", f"ID={target_role_id}")
            except Exception:
                tgt_name = f"ID={target_role_id}"
            # Get target current count
            try:
                target_resp = await client.get(f"/api/v1/security/roles/{target_role_id}/permissions/")
                target_count = len(target_resp.get("result", []))
            except Exception:
                target_count = "?"
            return json.dumps(
                {
                    "status": "dry_run",
                    "source": src_name,
                    "target": tgt_name,
                    "permissions_to_copy": len(perm_ids),
                    "target_current_permissions": target_count,
                    "message": (
                        f"Will REPLACE all permissions of '{tgt_name}' ({target_count} perms) "
                        f"with permissions from '{src_name}' ({len(perm_ids)} perms). "
                        f"Pass confirm=True to apply."
                    ),
                },
                ensure_ascii=False,
            )

        result = await client.post(
            f"/api/v1/security/roles/{target_role_id}/permissions",
            json_data={"permission_view_menu_ids": perm_ids},
        )
        return json.dumps(
            {
                "status": "applied",
                "permissions_set": len(perm_ids),
                "result": result,
            },
            ensure_ascii=False,
        )
