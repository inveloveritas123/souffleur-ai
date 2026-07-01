"""Tests for the MCP tool functions.

This is the acceptance test for Welle 7: it calls the tool
(``get_coaching_knowledge``) for each Karten-Typ (Einwand, vertiefende Frage,
Strukturhinweis) and asserts a non-empty, typgerechte (matching) answer.
"""

from __future__ import annotations

import pytest
from coaching_mcp.knowledge_store import KnowledgeStore
from coaching_mcp.tools import (
    UnknownCardTypeError,
    get_coaching_knowledge,
    list_card_types,
)

CARD_TYPES = ["objection", "deepening_question", "structure_hint"]


@pytest.fixture(scope="module")
def store() -> KnowledgeStore:
    return KnowledgeStore()


@pytest.mark.parametrize("card_type", CARD_TYPES)
def test_get_coaching_knowledge_returns_nonempty_typed_answer(
    store: KnowledgeStore, card_type: str
) -> None:
    results = get_coaching_knowledge(store, card_type)

    assert results, f"expected a non-empty answer for card_type={card_type!r}"
    for entry in results:
        assert entry["card_type"] == card_type
        # Inhaltlich brauchbar, kein Lorem-Ipsum-Platzhalter:
        assert entry["title"]
        assert entry["guidance"]
        assert entry["example_phrases"]
        assert entry["source"]


def test_get_coaching_knowledge_for_objection_matches_keyword_context() -> None:
    store_instance = KnowledgeStore()
    results = get_coaching_knowledge(
        store_instance,
        "objection",
        query="Ich habe gerade einfach keine Zeit dafür, das ist zu viel.",
    )
    assert results[0]["id"] == "objection-no-time"
    assert results[0]["card_type"] == "objection"


def test_get_coaching_knowledge_respects_limit(store: KnowledgeStore) -> None:
    results = get_coaching_knowledge(store, "deepening_question", limit=1)
    assert len(results) == 1


def test_get_coaching_knowledge_clamps_excessive_limit(store: KnowledgeStore) -> None:
    results = get_coaching_knowledge(store, "structure_hint", limit=999)
    assert len(results) <= 10


def test_get_coaching_knowledge_rejects_unknown_card_type(store: KnowledgeStore) -> None:
    with pytest.raises(UnknownCardTypeError):
        get_coaching_knowledge(store, "not_a_real_card_type")


def test_list_card_types_matches_concept_card_types() -> None:
    assert set(list_card_types()) == set(CARD_TYPES)
