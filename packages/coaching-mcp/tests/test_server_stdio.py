"""End-to-end test of the newline-delimited JSON-RPC stdio loop itself.

Uses in-memory ``io.StringIO`` instead of a real subprocess/pipe — exercises
the exact read/parse/dispatch/write code path in ``serve_stdio`` without any
process spawning, while staying fast and deterministic.
"""

from __future__ import annotations

import io
import json

from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.server import serve_stdio


def test_serve_stdio_handles_initialize_and_tool_call() -> None:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_coaching_knowledge",
                "arguments": {"card_type": "structure_hint"},
            },
        },
    ]
    stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout = io.StringIO()

    serve_stdio(store=KnowledgeStore(), stdin=stdin, stdout=stdout)

    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2

    initialize_response = json.loads(lines[0])
    assert initialize_response["id"] == 1
    assert "protocolVersion" in initialize_response["result"]

    tool_call_response = json.loads(lines[1])
    assert tool_call_response["id"] == 2
    result = tool_call_response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload
    assert all(entry["card_type"] == "structure_hint" for entry in payload)


def test_serve_stdio_reports_invalid_json_without_crashing() -> None:
    stdin = io.StringIO("not valid json\n")
    stdout = io.StringIO()

    serve_stdio(store=KnowledgeStore(), stdin=stdin, stdout=stdout)

    response = json.loads(stdout.getvalue().strip())
    assert response["error"]["code"] == -32700
