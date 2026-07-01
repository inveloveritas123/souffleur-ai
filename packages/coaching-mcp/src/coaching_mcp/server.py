"""A minimal, dependency-free MCP server for Coaching-Wissen.

Why not the official ``mcp`` Python SDK
----------------------------------------
ARCHITECTURE.md/TASKS.md call for the official MCP Python SDK. Every released
version of the ``mcp`` PyPI package requires Python >=3.10
(verified against PyPI metadata), while this monorepo's pinned tooling
(``pyproject.toml`` at the repo root: ``mypy`` ``python_version = "3.9"``) and
the system Python used by the mandated verification command
(``python3 -m pytest ...`` with ``python3`` resolving to 3.9.6) target
Python 3.9. Installing the SDK is therefore impossible without either
bumping the whole repo's Python baseline (out of scope for this Welle) or
shipping a server that silently can't run under the prescribed verification
command.

This module implements the small, stable subset of the MCP stdio transport
this server needs by hand, using only the standard library: newline-delimited
JSON-RPC 2.0 messages over stdin/stdout, the ``initialize``, ``tools/list``
and ``tools/call`` methods, and the same ``Tool``/``CallToolResult`` JSON
shapes the official SDK uses on the wire. Swapping this module for the
official SDK later (e.g. once the backend container in Welle 13/W10 runs
Python >=3.10) is a contained change: ``tools.py`` and ``knowledge_store.py``
have no dependency on this module and can be reused as-is.

Tests in this Welle call ``dispatch_tool_call``/``handle_request`` directly
(no subprocess, no real stdio) — that already exercises the full server
logic deterministically. ``serve_stdio`` is the thin, manually-verified glue
that reads/writes lines.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.tools import (
    TOOL_NAME_GET_COACHING_KNOWLEDGE,
    TOOL_NAME_LIST_CARD_TYPES,
    UnknownCardTypeError,
    get_coaching_knowledge,
    list_card_types,
)
from coaching_mcp.types import CardType

SERVER_NAME = "souffleur-coaching-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

JSONRPC_VERSION = "2.0"

_PARSE_ERROR = -32700
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602


def tool_definitions() -> list[dict[str, Any]]:
    """MCP ``Tool`` definitions advertised by ``tools/list``."""
    return [
        {
            "name": TOOL_NAME_GET_COACHING_KNOWLEDGE,
            "description": (
                "Liefert zu einem Coaching-Karten-Typ (objection = Einwand, "
                "deepening_question = vertiefende Frage, structure_hint = "
                "Strukturhinweis) passendes Coaching-Wissen (Frameworks, "
                "Fragetechniken, Einwand-Reframes) aus der lokalen "
                "Wissensbasis. Läuft rein lokal, kein externer Datenabfluss."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "card_type": {
                        "type": "string",
                        "enum": [member.value for member in CardType],
                        "description": "Der Karten-Typ, zu dem Wissen gesucht wird.",
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Optionaler Freitext (z. B. die ausloesende "
                            "Aeusserung) zur Rang-Bildung passender Einträge."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Maximale Anzahl Einträge (Default 3).",
                    },
                },
                "required": ["card_type"],
            },
        },
        {
            "name": TOOL_NAME_LIST_CARD_TYPES,
            "description": "Listet die gültigen Karten-Typ-Werte für get_coaching_knowledge auf.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def dispatch_tool_call(
    store: KnowledgeStore, name: str, arguments: dict[str, Any] | None
) -> dict[str, Any]:
    """Run a tool by name and return an MCP ``CallToolResult``-shaped dict."""
    arguments = arguments or {}
    try:
        if name == TOOL_NAME_GET_COACHING_KNOWLEDGE:
            card_type = arguments["card_type"]
            query = arguments.get("query")
            limit = arguments.get("limit", 3)
            entries = get_coaching_knowledge(store, card_type, query=query, limit=limit)
            return _text_result(entries)
        if name == TOOL_NAME_LIST_CARD_TYPES:
            return _text_result(list_card_types())
        return _error_result(f"Unknown tool: {name!r}")
    except KeyError as exc:
        return _error_result(f"Missing required argument: {exc.args[0]!r}")
    except UnknownCardTypeError as exc:
        return _error_result(str(exc))


def _text_result(payload: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": False,
    }


def _error_result(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def handle_request(store: KnowledgeStore, request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one parsed JSON-RPC 2.0 request and return the response dict.

    Returns ``None`` for notifications (no ``id``, no response expected).
    """
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {"tools": {}},
        }
        return _response(request_id, result=result)

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _response(request_id, result={"tools": tool_definitions()})

    if method == "tools/call":
        if request_id is None:
            return None
        name = params.get("name")
        if not isinstance(name, str):
            return _response(
                request_id,
                error={"code": _INVALID_PARAMS, "message": "params.name must be a string"},
            )
        arguments = params.get("arguments")
        result = dispatch_tool_call(store, name, arguments)
        return _response(request_id, result=result)

    if request_id is None:
        return None
    return _response(
        request_id,
        error={"code": _METHOD_NOT_FOUND, "message": f"Unknown method: {method!r}"},
    )


def _response(
    request_id: Any,
    *,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def serve_stdio(
    store: KnowledgeStore | None = None,
    stdin: IO[str] | None = None,
    stdout: IO[str] | None = None,
) -> None:
    """Run the newline-delimited JSON-RPC loop over stdin/stdout.

    Local-only: reads one JSON-RPC request per line, writes one JSON-RPC
    response per line. No socket, no external endpoint is opened.
    """
    active_store = store if store is not None else KnowledgeStore()
    in_stream = stdin if stdin is not None else sys.stdin
    out_stream = stdout if stdout is not None else sys.stdout

    for line in in_stream:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            request = json.loads(stripped)
        except json.JSONDecodeError:
            out_stream.write(
                json.dumps(
                    {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": None,
                        "error": {"code": _PARSE_ERROR, "message": "Invalid JSON"},
                    }
                )
                + "\n"
            )
            out_stream.flush()
            continue

        response = handle_request(active_store, request)
        if response is not None:
            out_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
            out_stream.flush()
