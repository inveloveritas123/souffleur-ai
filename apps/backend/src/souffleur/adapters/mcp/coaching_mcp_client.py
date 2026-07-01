"""adapters/mcp — stdio-Client für `packages/coaching-mcp` (Welle 13).

Bindet den Coaching-MCP-Server per stdio an (newline-delimited JSON-RPC 2.0, siehe
`packages/coaching-mcp/src/coaching_mcp/server.py::serve_stdio`) — kein HTTP, kein externer
Datenabfluss (lokaler Subprozess, `python -m coaching_mcp`). Ruft ausschließlich das Tool
`get_coaching_knowledge(card_type, query, limit)` (siehe `coaching_mcp/tools.py`).

Der Subprozess wird lazy gestartet (erster `get_coaching_knowledge`-Aufruf), damit die
Konstruktion dieses Clients (z. B. beim App-Start, `core/app.py`) keinen Prozess spawnt, wenn
Live-Coaching in der jeweiligen Session nie ausgelöst wird. `process_factory` erlaubt Tests,
den Subprozess-Start durch ein Double zu ersetzen — keine echte Prozess-/Netzabhängigkeit im
Unit-Test (Gate E1/E2: lokaler Subprozess ist ohnehin kein Netzaufruf, wird hier trotzdem
gemockt, um Tests deterministisch und schnell zu halten).
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

DEFAULT_MCP_COMMAND: tuple[str, ...] = (sys.executable, "-m", "coaching_mcp")
TOOL_NAME_GET_COACHING_KNOWLEDGE = "get_coaching_knowledge"


class CoachingMcpError(RuntimeError):
    """Der Coaching-MCP-Server hat einen Fehler zurückgemeldet oder ist nicht erreichbar."""


class _StdinLike(Protocol):
    def write(self, data: bytes) -> Any: ...
    async def drain(self) -> None: ...
    def close(self) -> None: ...


class _StdoutLike(Protocol):
    async def readline(self) -> bytes: ...


class _ProcessLike(Protocol):
    stdin: _StdinLike | None
    stdout: _StdoutLike | None

    async def wait(self) -> int: ...


ProcessFactory = Callable[[], Awaitable[_ProcessLike]]


class CoachingMcpStdioClient:
    """Startet `packages/coaching-mcp` lazy als Subprozess und spricht JSON-RPC über stdio."""

    def __init__(
        self,
        command: Sequence[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        process_factory: ProcessFactory | None = None,
    ) -> None:
        self._command = tuple(command) if command else DEFAULT_MCP_COMMAND
        self._cwd = cwd
        self._env = env
        self._process_factory: ProcessFactory = process_factory or self._spawn_subprocess
        self._process: _ProcessLike | None = None
        self._next_id = 1
        # Lazy statt in __init__: `asyncio.Lock()` bindet sich unter Python 3.9 sofort an die
        # zum Konstruktionszeitpunkt "aktuelle" Event-Loop — die kann zur Konstruktionszeit
        # (z. B. App-Start außerhalb eines laufenden Loops) noch gar nicht existieren.
        self._lock: asyncio.Lock | None = None

    async def _spawn_subprocess(self) -> _ProcessLike:
        process = await asyncio.create_subprocess_exec(
            *self._command,
            cwd=self._cwd,
            env=self._env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        return process  # type: ignore[return-value]

    async def _ensure_started(self) -> None:
        if self._process is not None:
            return
        self._process = await self._process_factory()
        await self._request("initialize", {})

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise CoachingMcpError("Coaching-MCP-stdio-Prozess ist nicht gestartet")
        stdin, stdout = self._process.stdin, self._process.stdout
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            request_id = self._next_id
            self._next_id += 1
            line = json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            stdin.write((line + "\n").encode("utf-8"))
            await stdin.drain()
            raw = await stdout.readline()

        if not raw:
            raise CoachingMcpError("Coaching-MCP-Server hat die Verbindung ohne Antwort beendet")
        response = json.loads(raw.decode("utf-8"))
        error = response.get("error")
        if error:
            raise CoachingMcpError(str(error.get("message", error)))
        result: dict[str, Any] = response.get("result") or {}
        return result

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Ruft `get_coaching_knowledge(card_type, query, limit)` über MCP `tools/call` auf."""
        await self._ensure_started()
        result = await self._request(
            "tools/call",
            {
                "name": TOOL_NAME_GET_COACHING_KNOWLEDGE,
                "arguments": {"card_type": card_type, "query": query, "limit": limit},
            },
        )
        content = result.get("content") or []
        text = content[0].get("text", "[]") if content else "[]"
        if result.get("isError"):
            raise CoachingMcpError(text)
        parsed: list[dict[str, Any]] = json.loads(text)
        return parsed

    async def aclose(self) -> None:
        """Beendet den Subprozess (falls gestartet). Kein-Op, wenn nie gestartet."""
        if self._process is None:
            return
        if self._process.stdin is not None:
            self._process.stdin.close()
        await self._process.wait()
        self._process = None
