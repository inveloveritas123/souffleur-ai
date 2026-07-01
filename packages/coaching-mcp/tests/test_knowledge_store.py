"""Tests for the local knowledge loader/lookup (no network, no I/O beyond disk)."""

from __future__ import annotations

from pathlib import Path

import pytest
from coaching_mcp.knowledge_store import KnowledgeLoadError, KnowledgeStore, load_entries
from coaching_mcp.types import CardType


def test_load_entries_reads_all_three_knowledge_files() -> None:
    entries = load_entries()
    card_types_present = {entry.card_type for entry in entries}
    assert card_types_present == set(CardType)


@pytest.mark.parametrize("card_type", list(CardType))
def test_each_card_type_has_several_real_entries(card_type: CardType) -> None:
    store = KnowledgeStore()
    entries = store.entries_for(card_type)
    # "ein paar fundierte Einträge" pro Karten-Typ (Aufgabenstellung) — mind. 3.
    assert len(entries) >= 3
    for entry in entries:
        assert entry.card_type is card_type
        assert entry.title
        assert entry.guidance
        assert entry.example_phrases
        assert entry.source


@pytest.mark.parametrize("card_type", list(CardType))
def test_search_without_query_returns_nonempty_typed_default(card_type: CardType) -> None:
    store = KnowledgeStore()
    results = store.search(card_type)
    assert results, "search() must never be empty for a known card type"
    assert all(entry.card_type is card_type for entry in results)


def test_search_respects_limit() -> None:
    store = KnowledgeStore()
    results = store.search(CardType.DEEPENING_QUESTION, limit=2)
    assert len(results) == 2


def test_search_ranks_matching_trigger_keyword_first() -> None:
    store = KnowledgeStore()
    # "objection-no-time" trägt das Trigger-Keyword "keine zeit".
    results = store.search(CardType.OBJECTION, query="Ich habe gerade einfach keine Zeit dafür")
    assert results[0].id == "objection-no-time"


def test_search_falls_back_to_default_order_when_no_keyword_matches() -> None:
    store = KnowledgeStore()
    results = store.search(CardType.STRUCTURE_HINT, query="völlig unzusammenhängender Text xyz")
    assert results, "must still return a typgerechte, non-empty answer"
    assert all(entry.card_type is CardType.STRUCTURE_HINT for entry in results)


def test_load_entries_raises_clear_error_for_missing_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"
    with pytest.raises(KnowledgeLoadError):
        load_entries(missing_dir)
