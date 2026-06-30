"""Tests for the MCP JSON-RPC request handling (server.py).

Calls ``handle_request``/``dispatch_tool_call`` directly — exercising the
exact server logic without spawning a subprocess or touching a real stdio
transport, which keeps the test deterministic and fast while still
verifying the MCP-shaped request/response contract.
"""

from __future__ import annotations

import json

import pytest
from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.server import (
    PROTOCOL_VERSION,
    dispatch_tool_call,
    handle_request,
    tool_definitions,
)
from coaching_mcp.tools import TOOL_NAME_GET_COACHING_KNOWLEDGE, TOOL_NAME_LIST_CARD_TYPES


@pytest.fixture(scope="module")
def store() -> KnowledgeStore:
    return KnowledgeStore()


def test_initialize_advertises_tools_capability(store: KnowledgeStore) -> None:
    response = handle_request(store, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert response is not None
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in response["result"]["capabilities"]


def test_notifications_initialized_returns_no_response(store: KnowledgeStore) -> None:
    response = handle_request(store, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert response is None


def test_tools_list_advertises_get_coaching_knowledge(store: KnowledgeStore) -> None:
    response = handle_request(store, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert response is not None
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert TOOL_NAME_GET_COACHING_KNOWLEDGE in names
    assert TOOL_NAME_LIST_CARD_TYPES in names


def test_tool_definitions_input_schema_enumerates_card_types() -> None:
    definitions = tool_definitions()
    get_knowledge_def = next(
        d for d in definitions if d["name"] == TOOL_NAME_GET_COACHING_KNOWLEDGE
    )
    schema_enum = get_knowledge_def["inputSchema"]["properties"]["card_type"]["enum"]
    assert set(schema_enum) == {"objection", "deepening_question", "structure_hint"}


@pytest.mark.parametrize("card_type", ["objection", "deepening_question", "structure_hint"])
def test_tools_call_get_coaching_knowledge_returns_nonempty_typed_content(
    store: KnowledgeStore, card_type: str
) -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": TOOL_NAME_GET_COACHING_KNOWLEDGE,
            "arguments": {"card_type": card_type},
        },
    }
    response = handle_request(store, request)
    assert response is not None
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload, "tool call must return a non-empty answer"
    assert all(entry["card_type"] == card_type for entry in payload)


def test_tools_call_unknown_card_type_is_reported_as_tool_error(store: KnowledgeStore) -> None:
    result = dispatch_tool_call(
        store, TOOL_NAME_GET_COACHING_KNOWLEDGE, {"card_type": "not_a_real_type"}
    )
    assert result["isError"] is True
    assert "not_a_real_type" in result["content"][0]["text"]


def test_tools_call_missing_required_argument_is_reported_as_tool_error(
    store: KnowledgeStore,
) -> None:
    result = dispatch_tool_call(store, TOOL_NAME_GET_COACHING_KNOWLEDGE, {})
    assert result["isError"] is True


def test_tools_call_list_card_types(store: KnowledgeStore) -> None:
    result = dispatch_tool_call(store, TOOL_NAME_LIST_CARD_TYPES, {})
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert set(payload) == {"objection", "deepening_question", "structure_hint"}


def test_unknown_method_returns_jsonrpc_error(store: KnowledgeStore) -> None:
    response = handle_request(store, {"jsonrpc": "2.0", "id": 4, "method": "not/a/method"})
    assert response is not None
    assert response["error"]["code"] == -32601
