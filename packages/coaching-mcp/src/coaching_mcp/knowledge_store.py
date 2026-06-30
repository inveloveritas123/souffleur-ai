"""Loads Coaching-Wissen from ``knowledge/*.json`` and answers lookups.

Wissen liegt als Daten vor (kein Fine-Tuning, siehe README). Diese Datei ist
die einzige Stelle, die die JSON-Dateien parst; alles darüber hinaus
(``tools.py``, ``server.py``) arbeitet ausschließlich mit ``KnowledgeEntry``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from coaching_mcp.types import CardType, KnowledgeEntry, parse_card_type

# packages/coaching-mcp/src/coaching_mcp/knowledge_store.py
#   parents[0] = .../coaching_mcp
#   parents[1] = .../src
#   parents[2] = .../coaching-mcp   (package root, sibling of knowledge/)
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_DIR = _PACKAGE_ROOT / "knowledge"

_ENV_KNOWLEDGE_DIR = "SOUFFLEUR_MCP_KNOWLEDGE_DIR"


class KnowledgeLoadError(RuntimeError):
    """Raised when a knowledge JSON file is missing a required field."""


def _entry_from_dict(raw: dict[str, object], source_file: Path) -> KnowledgeEntry:
    required = (
        "id",
        "card_type",
        "title",
        "framework",
        "summary",
        "guidance",
        "example_phrases",
        "trigger_keywords",
        "source",
    )
    missing = [field for field in required if field not in raw]
    if missing:
        raise KnowledgeLoadError(
            f"{source_file}: entry missing required field(s) {missing}: {raw!r}"
        )
    card_type_raw = raw["card_type"]
    example_phrases_raw = raw["example_phrases"]
    trigger_keywords_raw = raw["trigger_keywords"]
    assert isinstance(card_type_raw, str)
    assert isinstance(example_phrases_raw, list)
    assert isinstance(trigger_keywords_raw, list)
    return KnowledgeEntry(
        id=str(raw["id"]),
        card_type=parse_card_type(card_type_raw),
        title=str(raw["title"]),
        framework=str(raw["framework"]),
        summary=str(raw["summary"]),
        guidance=str(raw["guidance"]),
        example_phrases=tuple(str(p) for p in example_phrases_raw),
        trigger_keywords=tuple(str(k) for k in trigger_keywords_raw),
        source=str(raw["source"]),
    )


def _resolve_knowledge_dir(knowledge_dir: Path | None) -> Path:
    if knowledge_dir is not None:
        return knowledge_dir
    env_override = os.environ.get(_ENV_KNOWLEDGE_DIR)
    if env_override:
        return Path(env_override)
    return DEFAULT_KNOWLEDGE_DIR


def load_entries(knowledge_dir: Path | None = None) -> tuple[KnowledgeEntry, ...]:
    """Load every ``*.json`` file in the knowledge directory into entries.

    Pure local file access — no network call, no external service. This is
    the function that fulfils the "kein externer Datenabfluss" requirement.
    """
    directory = _resolve_knowledge_dir(knowledge_dir)
    if not directory.is_dir():
        raise KnowledgeLoadError(f"Knowledge directory not found: {directory}")

    entries: list[KnowledgeEntry] = []
    for json_path in sorted(directory.glob("*.json")):
        with json_path.open("r", encoding="utf-8") as handle:
            raw_entries = json.load(handle)
        if not isinstance(raw_entries, list):
            raise KnowledgeLoadError(f"{json_path}: expected a JSON list at top level")
        for raw_entry in raw_entries:
            entries.append(_entry_from_dict(raw_entry, json_path))
    return tuple(entries)


class KnowledgeStore:
    """In-memory, read-only index over the loaded coaching knowledge."""

    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self._entries: tuple[KnowledgeEntry, ...] = load_entries(knowledge_dir)
        self._by_card_type: dict[CardType, list[KnowledgeEntry]] = {
            card_type: [] for card_type in CardType
        }
        for entry in self._entries:
            self._by_card_type[entry.card_type].append(entry)

    def all_entries(self) -> tuple[KnowledgeEntry, ...]:
        return self._entries

    def entries_for(self, card_type: CardType) -> tuple[KnowledgeEntry, ...]:
        return tuple(self._by_card_type[card_type])

    def search(
        self,
        card_type: CardType,
        query: str | None = None,
        limit: int = 3,
    ) -> tuple[KnowledgeEntry, ...]:
        """Return the best-matching entries for a card type and optional query.

        Always returns entries whose ``card_type`` matches exactly (never a
        different card type), and is never empty as long as the store has at
        least one entry for that card type — a query with no keyword overlap
        falls back to the card type's entries in their default order, so a
        typgerechte, non-empty answer is guaranteed for every known card type.
        """
        candidates = self.entries_for(card_type)
        if not candidates:
            return ()
        if not query:
            return candidates[:limit]

        normalized_query = query.lower()
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in candidates:
            score = 0
            haystacks = (entry.title, entry.summary, *entry.trigger_keywords)
            for keyword in entry.trigger_keywords:
                if keyword.lower() in normalized_query:
                    score += 2
            for haystack in haystacks:
                if haystack.lower() in normalized_query or normalized_query in haystack.lower():
                    score += 1
            scored.append((score, entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        ranked_entries = tuple(entry for _score, entry in scored)
        return ranked_entries[:limit]
