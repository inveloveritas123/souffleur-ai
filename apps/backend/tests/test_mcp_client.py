"""Welle 13 — CoachingMcpStdioClient: stdio-JSON-RPC-Client für packages/coaching-mcp.

Der Subprozess-Start wird per `process_factory` durch ein Double ersetzt (`_FakeProcess`) —
kein echter Subprozess/Netzaufruf im Unit-Test, deterministisch und schnell.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from souffleur.adapters.mcp.coaching_mcp_client import CoachingMcpError, CoachingMcpStdioClient


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _FakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout([json.dumps(r).encode("utf-8") + b"\n" for r in responses])
        self.waited = False

    async def wait(self) -> int:
        self.waited = True
        return 0


def _initialize_response(request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05"}}


def _tool_call_response(request_id: int, entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(entries)}],
            "isError": False,
        },
    }


def test_get_coaching_knowledge_starts_process_lazily_and_parses_result() -> None:
    entries = [{"id": "k1", "card_type": "objection", "title": "Reframe"}]
    fake_process = _FakeProcess([_initialize_response(1), _tool_call_response(2, entries)])

    async def process_factory() -> _FakeProcess:
        return fake_process

    client = CoachingMcpStdioClient(process_factory=process_factory)

    async def scenario() -> list[dict[str, Any]]:
        return await client.get_coaching_knowledge("objection", query="Das ist zu teuer", limit=3)

    result = asyncio.run(scenario())

    assert result == entries
    # initialize + tools/call: zwei Anfragen gesendet
    assert len(fake_process.stdin.written) == 2
    initialize_request = json.loads(fake_process.stdin.written[0])
    assert initialize_request["method"] == "initialize"
    tool_call_request = json.loads(fake_process.stdin.written[1])
    assert tool_call_request["method"] == "tools/call"
    assert tool_call_request["params"]["name"] == "get_coaching_knowledge"
    assert tool_call_request["params"]["arguments"] == {
        "card_type": "objection",
        "query": "Das ist zu teuer",
        "limit": 3,
    }


def test_get_coaching_knowledge_reuses_already_started_process() -> None:
    entries_a = [{"id": "k1"}]
    entries_b = [{"id": "k2"}]
    fake_process = _FakeProcess(
        [_initialize_response(1), _tool_call_response(2, entries_a), _tool_call_response(3, entries_b)]
    )

    async def process_factory() -> _FakeProcess:
        return fake_process

    process_starts = {"count": 0}

    async def counting_factory() -> _FakeProcess:
        process_starts["count"] += 1
        return await process_factory()

    client = CoachingMcpStdioClient(process_factory=counting_factory)

    async def scenario() -> tuple[list[Any], list[Any]]:
        first = await client.get_coaching_knowledge("objection")
        second = await client.get_coaching_knowledge("deepening_question")
        return first, second

    first, second = asyncio.run(scenario())

    assert first == entries_a
    assert second == entries_b
    assert process_starts["count"] == 1  # nur einmal gestartet (lazy + wiederverwendet)


def test_get_coaching_knowledge_raises_on_mcp_error_result() -> None:
    error_response = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"content": [{"type": "text", "text": "Unknown card_type"}], "isError": True},
    }
    fake_process = _FakeProcess([_initialize_response(1), error_response])

    async def process_factory() -> _FakeProcess:
        return fake_process

    client = CoachingMcpStdioClient(process_factory=process_factory)

    with pytest.raises(CoachingMcpError):
        asyncio.run(client.get_coaching_knowledge("not_a_type"))


def test_request_raises_on_json_rpc_error_field() -> None:
    error_response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "boom"}}
    fake_process = _FakeProcess([error_response])

    async def process_factory() -> _FakeProcess:
        return fake_process

    client = CoachingMcpStdioClient(process_factory=process_factory)

    with pytest.raises(CoachingMcpError):
        asyncio.run(client.get_coaching_knowledge("objection"))


def test_aclose_is_a_noop_when_never_started() -> None:
    client = CoachingMcpStdioClient(process_factory=lambda: (_ for _ in ()).throw(AssertionError()))

    asyncio.run(client.aclose())  # darf keinen Subprozess starten/kein Fehler


def test_aclose_closes_stdin_and_waits_for_process() -> None:
    fake_process = _FakeProcess([_initialize_response(1), _tool_call_response(2, [])])

    async def process_factory() -> _FakeProcess:
        return fake_process

    client = CoachingMcpStdioClient(process_factory=process_factory)

    async def scenario() -> None:
        await client.get_coaching_knowledge("objection")
        await client.aclose()

    asyncio.run(scenario())

    assert fake_process.stdin.closed is True
    assert fake_process.waited is True
