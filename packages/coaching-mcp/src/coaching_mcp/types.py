"""Shared types for the Coaching-MCP-Server.

``CardType`` mirrors the three Coaching-Karten-Typen from the concept
(Einwand, vertiefende Frage, Strukturhinweis — see
docs/concept/Konzept_Echtzeit_Coaching_Copilot.md, Abschnitt 2.3) and is the
contract the future TriggerRouter/ReasoningEngine (Welle 13, apps/backend)
will reuse when it calls this server's tool with a card type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CardType(str, Enum):
    """A Coaching-Karten-Typ as defined by the concept document."""

    OBJECTION = "objection"
    DEEPENING_QUESTION = "deepening_question"
    STRUCTURE_HINT = "structure_hint"


@dataclass(frozen=True)
class KnowledgeEntry:
    """One unit of coaching knowledge (a framework, technique or reframe)."""

    id: str
    card_type: CardType
    title: str
    framework: str
    summary: str
    guidance: str
    example_phrases: tuple[str, ...]
    trigger_keywords: tuple[str, ...]
    source: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation (used as MCP tool output)."""
        return {
            "id": self.id,
            "card_type": self.card_type.value,
            "title": self.title,
            "framework": self.framework,
            "summary": self.summary,
            "guidance": self.guidance,
            "example_phrases": list(self.example_phrases),
            "source": self.source,
        }


class UnknownCardTypeError(ValueError):
    """Raised when a card_type string does not map to a known CardType."""


def parse_card_type(value: str) -> CardType:
    """Parse a raw string into a CardType, raising a clear error otherwise."""
    try:
        return CardType(value)
    except ValueError as exc:
        valid = ", ".join(member.value for member in CardType)
        raise UnknownCardTypeError(
            f"Unknown card_type {value!r}. Valid values: {valid}."
        ) from exc
