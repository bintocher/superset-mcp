"""Tools for managing user groups in Superset."""

import json

from mcp_superset.tools.types import IntList


def register_group_tools(mcp):
    """Register all group management tools with the MCP server."""
    from mcp_superset.server import superset_client as client

    # === Groups ===

    @mcp.tool
    async def superset_group_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List Superset user groups.

        A group combines users and roles. Users in a group
        inherit all roles assigned to the group.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By name: (filters:!((col:name,opr:ct,value:moscow)))
            get_all: Fetch ALL records with automatic pagination.
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/groups/", params=params)
        else:
            result = await client.get_page("/api/v1/security/groups/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_get(group_id: int) -> str:
        """Get detailed information about a group by ID.

        Returns: name, label, description, list of roles and users.

        Args:
            group_id: Group ID (from group_list).
        """
        result = await client.get(f"/api/v1/security/groups/{group_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_create(
        name: str,
        label: str | None = None,
        description: str | None = None,
        roles: IntList | None = None,
        users: IntList | None = None,
    ) -> str:
        """Create a new user group.

        A group combines users and roles. Users in a group
        automatically inherit all roles of the group.

        Args:
            name: Unique group name (e.g. "la_region_Moscow").
            label: Display label (e.g. "Moscow region").
            description: Group description.
            roles: List of role IDs to assign to the group.
            users: List of user IDs to add to the group.
        """
        payload: dict = {"name": name}
        if label is not None:
            payload["label"] = label
        if description is not None:
            payload["description"] = description

        result = await client.post("/api/v1/security/groups/", json_data=payload)
        group_id = result.get("id")

        # Roles and users are assigned via update (create only accepts name/label/description)
        if group_id and (roles is not None or users is not None):
            update_payload: dict = {}
            if roles is not None:
                update_payload["roles"] = roles
            if users is not None:
                update_payload["users"] = users
            await client.put(
                f"/api/v1/security/groups/{group_id}",
                json_data=update_payload,
            )
            # Fetch full details
            detail = await client.get(f"/api/v1/security/groups/{group_id}")
            return json.dumps(
                {"id": group_id, "result": detail.get("result", {})},
                ensure_ascii=False,
            )

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_update(
        group_id: int,
        name: str | None = None,
        label: str | None = None,
        description: str | None = None,
        roles: IntList | None = None,
        users: IntList | None = None,
        confirm_roles_replace: bool = False,
        confirm_users_replace: bool = False,
    ) -> str:
        """Update a group. Only pass the fields you want to change.

        IMPORTANT: roles REPLACES the entire role list of the group (does not append).
        IMPORTANT: users REPLACES the entire user list of the group (does not append).

        To add a single role/user: fetch current ones via group_get,
        add the ID to the list, pass the complete list.

        Args:
            group_id: ID of the group to update.
            name: New group name.
            label: New label.
            description: New description.
            roles: New COMPLETE list of role IDs (REPLACES all current ones).
            users: New COMPLETE list of user IDs (REPLACES all current ones).
            confirm_roles_replace: Confirmation for role replacement (REQUIRED when roles is set).
            confirm_users_replace: Confirmation for user replacement (REQUIRED when users is set).
        """
        if roles is not None and not confirm_roles_replace:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                current_roles = current.get("roles", [])
                role_names = [f"{r['name']} (id={r['id']})" for r in current_roles]
            except Exception:
                role_names = ["failed to retrieve"]
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: roles REPLACES ALL roles of the group (ID={group_id}). "
                        f"Current roles: {role_names}. "
                        f"Pass confirm_roles_replace=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        if users is not None and not confirm_users_replace:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                current_users = current.get("users", [])
                user_names = [f"{u['username']} (id={u['id']})" for u in current_users]
            except Exception:
                user_names = ["failed to retrieve"]
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: users REPLACES ALL users of the group (ID={group_id}). "
                        f"Current users: {user_names}. "
                        f"Pass confirm_users_replace=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if label is not None:
            payload["label"] = label
        if description is not None:
            payload["description"] = description
        if roles is not None:
            payload["roles"] = roles
        if users is not None:
            payload["users"] = users

        if not payload:
            return json.dumps(
                {"error": "No fields provided for update."},
                ensure_ascii=False,
            )

        result = await client.put(f"/api/v1/security/groups/{group_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_delete(
        group_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a user group.

        Users in the group are NOT deleted, but they lose the roles
        that were assigned through this group.

        Args:
            group_id: ID of the group to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                name = current.get("name", "?")
                roles = [r["name"] for r in current.get("roles", [])]
                users = [u["username"] for u in current.get("users", [])]
            except Exception:
                name = f"ID={group_id}"
                roles = ["failed to retrieve"]
                users = ["failed to retrieve"]
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deleting group '{name}' (ID={group_id}). "
                        f"Roles: {roles}. Users ({len(users)}): "
                        f"{users[:10]}{'...' if len(users) > 10 else ''}. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/security/groups/{group_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_add_users(
        group_id: int,
        user_ids: IntList,
    ) -> str:
        """Add users to a group without removing existing ones.

        Convenience tool: fetches current group users,
        merges in new ones, and updates the group.

        Args:
            group_id: Group ID.
            user_ids: List of user IDs to add.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_user_ids = {u["id"] for u in current.get("users", [])}
        new_user_ids = current_user_ids | set(user_ids)

        await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"users": sorted(new_user_ids)},
        )

        added = set(user_ids) - current_user_ids
        already = set(user_ids) & current_user_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "added": sorted(added),
                "already_in_group": sorted(already),
                "total_users": len(new_user_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_remove_users(
        group_id: int,
        user_ids: IntList,
    ) -> str:
        """Remove users from a group without removing the rest.

        Args:
            group_id: Group ID.
            user_ids: List of user IDs to remove from the group.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_user_ids = {u["id"] for u in current.get("users", [])}
        new_user_ids = current_user_ids - set(user_ids)

        await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"users": sorted(new_user_ids)},
        )

        removed = current_user_ids & set(user_ids)
        not_found = set(user_ids) - current_user_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "removed": sorted(removed),
                "not_in_group": sorted(not_found),
                "total_users": len(new_user_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_add_roles(
        group_id: int,
        role_ids: IntList,
    ) -> str:
        """Add roles to a group without removing existing ones.

        Args:
            group_id: Group ID.
            role_ids: List of role IDs to add.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_role_ids = {r["id"] for r in current.get("roles", [])}
        new_role_ids = current_role_ids | set(role_ids)

        await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"roles": sorted(new_role_ids)},
        )

        added = set(role_ids) - current_role_ids
        already = set(role_ids) & current_role_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "added_roles": sorted(added),
                "already_in_group": sorted(already),
                "total_roles": len(new_role_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_remove_roles(
        group_id: int,
        role_ids: IntList,
    ) -> str:
        """Remove roles from a group without removing the rest.

        Args:
            group_id: Group ID.
            role_ids: List of role IDs to remove.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_role_ids = {r["id"] for r in current.get("roles", [])}
        new_role_ids = current_role_ids - set(role_ids)

        await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"roles": sorted(new_role_ids)},
        )

        removed = current_role_ids & set(role_ids)
        not_found = set(role_ids) - current_role_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "removed_roles": sorted(removed),
                "not_in_group": sorted(not_found),
                "total_roles": len(new_role_ids),
            },
            ensure_ascii=False,
        )
