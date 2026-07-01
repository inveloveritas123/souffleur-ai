"""Regel-Vorfilter des TriggerRouters (Welle 13, deterministisch, schnell).

ARCHITECTURE.md "Trigger-Router-Logik": feuert bei erkanntem Einwand-Marker, Fragezeichen,
längerer Pause (Stille über Schwellwert) oder konfigurierten Schlüsselbegriffen.
Negativ-Filter unterdrückt Backchannel ("mhm", "ja genau") und zu kurze Segmente. Rein
regelbasiert, kein Modellaufruf — deterministischer Unit-Test-Pfad (SPEC.md Akzeptanz).

`card_type`-Werte spiegeln `packages/coaching-mcp` (`CardType`): `objection`
(Einwand), `deepening_question` (vertiefende Frage), `structure_hint` (Strukturhinweis).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CARD_TYPE_OBJECTION = "objection"
CARD_TYPE_DEEPENING_QUESTION = "deepening_question"
CARD_TYPE_STRUCTURE_HINT = "structure_hint"

# Backchannel/Bestätigungslaute — unterdrückt, selbst wenn sie ein Fragezeichen tragen ("ja?").
_BACKCHANNEL_PHRASES = frozenset(
    {"mhm", "mh", "hm", "aha", "ja", "genau", "ja genau", "okay", "ok", "gut", "richtig"}
)

# Zu kurze Segmente sind fast immer Backchannel/Füllwörter, kein inhaltlicher Trigger.
MIN_TRIGGER_CHARS = 8

# Einwand-Marker (Schlüsselbegriffe) — konfigurierbar, hier als Startwortliste.
_OBJECTION_MARKERS = (
    "aber",
    "jedoch",
    "allerdings",
    "leider",
    "problem",
    "bedenken",
    "zu teuer",
    "zu hoch",
    "zu viel",
    "schwierig",
    "zweifel",
    "eigentlich nicht",
    "das funktioniert nicht",
)

DEFAULT_SILENCE_THRESHOLD_MS = 2500


class RuleDecision(str, Enum):
    """Ergebnis des deterministischen Vorfilters."""

    NO_CARD = "no_card"
    CARD = "card"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class RuleVerdict:
    """Vorfilter-Entscheidung plus (falls `CARD`) eine erste Karten-Typ-Einschätzung."""

    decision: RuleDecision
    card_type: str | None = None


def apply_rules(
    text: str,
    *,
    silence_ms: int = 0,
    silence_threshold_ms: int = DEFAULT_SILENCE_THRESHOLD_MS,
) -> RuleVerdict:
    """Deterministischer Vorfilter — kein Modellaufruf, keine Zufälligkeit.

    Reihenfolge (ARCHITECTURE.md): Negativ-Filter (Backchannel/zu kurz) zuerst, dann
    Fragezeichen (vertiefende Frage), dann Einwand-Marker, dann lange Stille
    (Strukturhinweis). Trifft keine Regel, ist der Vorfilter unsicher — das ist der
    Übergabepunkt an den LLM-Klassifikator (ministral-3b-2512).
    """
    stripped = text.strip()
    normalized = stripped.lower().strip("?!. ")

    if not stripped or len(stripped) < MIN_TRIGGER_CHARS:
        return RuleVerdict(RuleDecision.NO_CARD)
    if normalized in _BACKCHANNEL_PHRASES:
        return RuleVerdict(RuleDecision.NO_CARD)
    if "?" in stripped:
        return RuleVerdict(RuleDecision.CARD, card_type=CARD_TYPE_DEEPENING_QUESTION)
    if any(marker in normalized for marker in _OBJECTION_MARKERS):
        return RuleVerdict(RuleDecision.CARD, card_type=CARD_TYPE_OBJECTION)
    if silence_ms >= silence_threshold_ms:
        return RuleVerdict(RuleDecision.CARD, card_type=CARD_TYPE_STRUCTURE_HINT)
    return RuleVerdict(RuleDecision.UNCERTAIN)
