"""Argument types for tools, tolerant of how MCP clients encode lists.

Several MCP clients serialise array arguments as a JSON string before the call
reaches pydantic, so `dashboards=[31]` arrives as the string `"[31]"` and a
plain `list[int]` annotation rejects it with a validation error. These aliases
accept both the native list and its JSON-encoded form.
"""

import json
from typing import Annotated, Any

from pydantic import BeforeValidator


def coerce_list(value: Any) -> Any:
    """Turn a JSON-encoded (or comma-separated) list into a real list.

    Args:
        value: Raw argument value as received from the MCP client.

    Returns:
        A list when the input was a string encoding one, otherwise the value
        unchanged - pydantic then validates the item types as usual.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Tolerate "31,32" as well - some clients flatten arrays that way.
        return [part.strip() for part in text.split(",") if part.strip()]
    return parsed if isinstance(parsed, list) else [parsed]


IntList = Annotated[list[int], BeforeValidator(coerce_list)]
StrList = Annotated[list[str], BeforeValidator(coerce_list)]
