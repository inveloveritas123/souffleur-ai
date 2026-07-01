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
        self.killed = False

    async def wait(self) -> int:
        self.waited = True
        return 0

    def kill(self) -> None:
        self.killed = True


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


class _HangingStdout:
    """`readline()` hängt für immer — simuliert einen Coaching-MCP-Prozess, der nicht mehr
    antwortet (Finding 11: Deadlock-Schutz für `stdout.readline()` unter gehaltenem Lock)."""

    async def readline(self) -> bytes:
        await asyncio.Event().wait()  # niemals gesetzt -> hängt, bis von außen abgebrochen
        raise AssertionError("unreachable")  # pragma: no cover


class _HangingProcess:
    """`wait()` hängt für immer, bis `kill()` aufgerufen wird — simuliert einen Coaching-MCP-
    Subprozess, der auf ein normales `stdin.close()` nicht reagiert (Finding 16).

    `asyncio.Event()` bindet sich unter Python 3.9 sofort an die zum Konstruktionszeitpunkt
    aktuelle Event-Loop (dasselbe Problem wie `CoachingMcpStdioClient._lock`, siehe dessen
    Docstring) — die Konstruktion hier passiert VOR `asyncio.run(...)`, daher lazy statt in
    `__init__`.
    """

    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _HangingStdout()
        self.killed = False
        self._exit_event: asyncio.Event | None = None

    def _event(self) -> asyncio.Event:
        if self._exit_event is None:
            self._exit_event = asyncio.Event()
        return self._exit_event

    def kill(self) -> None:
        self.killed = True
        self._event().set()

    async def wait(self) -> int:
        await self._event().wait()
        return -9


def test_request_raises_clear_error_on_readline_timeout_instead_of_hanging() -> None:
    """Finding 11 (MCP-Deadlock): `await stdout.readline()` OHNE Timeout unter gehaltenem Lock
    hängt die gesamte Session für immer, wenn der MCP-Server nie antwortet. Der Fix muss einen
    Timeout erzwingen und `CoachingMcpError` werfen statt zu hängen."""
    process = _HangingProcess()

    async def process_factory() -> _HangingProcess:
        return process

    client = CoachingMcpStdioClient(process_factory=process_factory, request_timeout_s=0.05)

    async def scenario() -> None:
        # `_ensure_started` ruft intern `_request("initialize", ...)` — genau dort hängt es.
        await asyncio.wait_for(client.get_coaching_knowledge("objection"), timeout=2.0)

    with pytest.raises(CoachingMcpError):
        asyncio.run(scenario())


def test_aclose_kills_process_when_wait_times_out() -> None:
    """Finding 16 (MCP aclose ohne kill): `await process.wait()` OHNE Timeout in `aclose()`
    hängt für immer, wenn der Prozess nach `stdin.close()` nicht selbst beendet. Der Fix muss
    nach einem Timeout `process.kill()` aufrufen."""
    process = _HangingProcess()
    # `wait()` hängt normalerweise ewig — nur `kill()` setzt das Exit-Event (siehe oben).

    async def process_factory() -> _HangingProcess:
        return process

    client = CoachingMcpStdioClient(process_factory=process_factory, close_timeout_s=0.05)
    client._process = process  # Prozess "künstlich" als gestartet markieren, kein Handshake nötig

    asyncio.run(asyncio.wait_for(client.aclose(), timeout=2.0))

    assert process.killed is True


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
