"""Entry point: ``python -m coaching_mcp`` / the ``coaching-mcp`` console script.

Starts the stdio MCP server (see server.py). Runs entirely locally —
reads/writes only stdin/stdout and the local ``knowledge/`` directory, no
network socket is opened.
"""

from __future__ import annotations

from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.server import serve_stdio


def main() -> None:
    serve_stdio(store=KnowledgeStore())


if __name__ == "__main__":
    main()
