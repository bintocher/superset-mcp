"""Tests for tool argument coercion (issue #12) and null-metadata handling (issue #11)."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from mcp_superset.tools.types import IntList, StrList

INT_LIST = TypeAdapter(IntList)
STR_LIST = TypeAdapter(StrList)


def test_json_encoded_int_list_is_accepted():
    """Some MCP clients send [31] as the string "[31]"."""
    assert INT_LIST.validate_python("[31]") == [31]


def test_native_int_list_still_works():
    assert INT_LIST.validate_python([31, 32]) == [31, 32]


def test_single_value_string_becomes_a_list():
    assert INT_LIST.validate_python("31") == [31]


def test_comma_separated_string_is_accepted():
    assert INT_LIST.validate_python("31, 32") == [31, 32]


def test_empty_string_is_an_empty_list():
    assert INT_LIST.validate_python("") == []


def test_str_list_json_encoded():
    assert STR_LIST.validate_python('["a", "b"]') == ["a", "b"]


def test_non_numeric_items_still_rejected():
    with pytest.raises(ValidationError):
        INT_LIST.validate_python('["not-an-int"]')


def test_null_json_metadata_is_treated_as_empty():
    """Superset returns json_metadata: null for freshly created dashboards."""
    result = {"json_metadata": None, "position_json": None}
    assert json.loads(result.get("json_metadata") or "{}") == {}
    assert json.loads(result.get("position_json") or "{}") == {}
