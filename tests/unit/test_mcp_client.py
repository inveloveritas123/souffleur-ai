"""Unit-Tests adapters/mcp/coaching_mcp_client.py — stdio-JSON-RPC-Client, Subprozess gemockt."""
from __future__ import annotations

import json
import unittest
from typing import TypeVar

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.adapters.mcp.coaching_mcp_client import (  # noqa: E402
    CoachingMcpError,
    CoachingMcpStdioClient,
)


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
    def __init__(self, responses: list[bytes]) -> None:
        self._responses = list(responses)

    async def readline(self) -> bytes:
        if not self._responses:
            return b""
        return self._responses.pop(0)


class _FakeProcess:
    def __init__(self, responses: list[bytes]) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(responses)
        self.waited = False

    async def wait(self) -> int:
        self.waited = True
        return 0


def _ok_response(request_id: int, result: dict) -> bytes:
    return (json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n").encode()


def _error_response(request_id: int, message: str) -> bytes:
    return (
        json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"message": message}}) + "\n"
    ).encode()


class CoachingMcpStdioClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_coaching_knowledge_starts_process_lazily_and_parses_result(self) -> None:
        knowledge = [{"card_type": "objection", "title": "x", "guidance": "y"}]
        process = _FakeProcess(
            [
                _ok_response(1, {}),  # initialize
                _ok_response(2, {"content": [{"type": "text", "text": json.dumps(knowledge)}]}),
            ]
        )

        spawn_calls = 0

        async def process_factory() -> _FakeProcess:
            nonlocal spawn_calls
            spawn_calls += 1
            return process

        client = CoachingMcpStdioClient(process_factory=process_factory)
        self.assertIsNone(client._process)  # Lazy: kein Prozess bei Konstruktion

        result = await client.get_coaching_knowledge("objection", query="zu teuer", limit=3)

        self.assertEqual(result, knowledge)
        self.assertEqual(spawn_calls, 1)
        self.assertEqual(len(process.stdin.written), 2)  # initialize + tools/call

    async def test_second_call_reuses_the_same_process(self) -> None:
        process = _FakeProcess(
            [
                _ok_response(1, {}),
                _ok_response(2, {"content": [{"text": "[]"}]}),
                _ok_response(3, {"content": [{"text": "[]"}]}),
            ]
        )
        spawn_calls = 0

        async def process_factory() -> _FakeProcess:
            nonlocal spawn_calls
            spawn_calls += 1
            return process

        client = CoachingMcpStdioClient(process_factory=process_factory)
        await client.get_coaching_knowledge("objection")
        await client.get_coaching_knowledge("deepening_question")

        self.assertEqual(spawn_calls, 1)

    async def test_error_result_raises_coaching_mcp_error(self) -> None:
        process = _FakeProcess(
            [
                _ok_response(1, {}),
                _ok_response(2, {"content": [{"text": "boom"}], "isError": True}),
            ]
        )

        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(process))

        with self.assertRaises(CoachingMcpError):
            await client.get_coaching_knowledge("objection")

    async def test_jsonrpc_error_response_raises_coaching_mcp_error(self) -> None:
        process = _FakeProcess([_error_response(1, "init kaputt")])

        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(process))

        with self.assertRaises(CoachingMcpError):
            await client.get_coaching_knowledge("objection")

    async def test_empty_readline_raises_coaching_mcp_error(self) -> None:
        process = _FakeProcess([b""])  # EOF sofort bei initialize

        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(process))

        with self.assertRaises(CoachingMcpError):
            await client.get_coaching_knowledge("objection")

    async def test_request_without_started_process_raises(self) -> None:
        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(_FakeProcess([])))
        with self.assertRaises(CoachingMcpError):
            await client._request("tools/call", {})

    async def test_aclose_is_noop_when_never_started(self) -> None:
        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(_FakeProcess([])))
        await client.aclose()  # darf nicht werfen

    async def test_aclose_closes_stdin_and_awaits_process(self) -> None:
        process = _FakeProcess([_ok_response(1, {})])
        client = CoachingMcpStdioClient(process_factory=lambda: _async_return(process))
        await client._ensure_started()

        await client.aclose()

        self.assertTrue(process.stdin.closed)
        self.assertTrue(process.waited)
        self.assertIsNone(client._process)

    async def test_default_command_uses_python_module_invocation(self) -> None:
        client = CoachingMcpStdioClient()
        self.assertEqual(client._command[1:], ("-m", "coaching_mcp"))


_T = TypeVar("_T")


async def _async_return(value: _T) -> _T:  # kleine Hilfsfunktion: synchroner Wert als Awaitable
    return value


if __name__ == "__main__":
    unittest.main()
