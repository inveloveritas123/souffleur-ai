"""The MCP tool(s) exposed by the Coaching-MCP-Server.

``get_coaching_knowledge`` is the tool required by Welle 7: given a
Karten-Typ (Einwand/vertiefende Frage/Strukturhinweis) it returns matching
Coaching-Wissen from ``knowledge/`` as plain, JSON-serializable dicts — ready
to be embedded into the MCP tool-call result content and, later (Welle 13),
into the ReasoningEngine's prompt to magistral-medium-2509.
"""

from __future__ import annotations

from typing import Any

from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.types import CardType, UnknownCardTypeError, parse_card_type

TOOL_NAME_GET_COACHING_KNOWLEDGE = "get_coaching_knowledge"
TOOL_NAME_LIST_CARD_TYPES = "list_card_types"

DEFAULT_LIMIT = 3
MAX_LIMIT = 10


def get_coaching_knowledge(
    store: KnowledgeStore,
    card_type: str,
    query: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Return coaching knowledge entries matching ``card_type`` (and ``query``).

    Args:
        store: the loaded knowledge base to read from (no I/O happens here).
        card_type: one of "objection", "deepening_question", "structure_hint".
        query: optional free-text snippet (e.g. the triggering utterance) used
            to rank entries; without it the card type's default entries are
            returned.
        limit: maximum number of entries to return (clamped to MAX_LIMIT).

    Returns:
        A non-empty list of JSON-serializable entry dicts, all sharing the
        requested ``card_type`` (typgerechte Antwort).

    Raises:
        UnknownCardTypeError: if ``card_type`` is not a known Karten-Typ.
    """
    parsed_card_type: CardType = parse_card_type(card_type)
    clamped_limit = max(1, min(limit, MAX_LIMIT))
    entries = store.search(parsed_card_type, query=query, limit=clamped_limit)
    return [entry.to_dict() for entry in entries]


def list_card_types() -> list[str]:
    """Return the valid Karten-Typ values this server understands.

    Convenience tool for MCP clients (e.g. the ReasoningEngine, Welle 13) to
    discover the accepted ``card_type`` values without hardcoding them.
    """
    return [card_type.value for card_type in CardType]


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "TOOL_NAME_GET_COACHING_KNOWLEDGE",
    "TOOL_NAME_LIST_CARD_TYPES",
    "UnknownCardTypeError",
    "get_coaching_knowledge",
    "list_card_types",
]
