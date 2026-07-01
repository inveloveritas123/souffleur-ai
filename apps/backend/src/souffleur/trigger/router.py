"""TriggerRouter — zweistufige Karten-Entscheidung (Welle 13).

ARCHITECTURE.md "Trigger-Router-Logik": Regel-Vorfilter (`trigger/rules.py`, deterministisch)
zuerst; nur bei `UNCERTAIN` ruft der Router den billigen LLM-Klassifikator
(`ministral-3b-2512`, über `LlmPort.classify`) auf. Ein Cooldown je Session verhindert
Karten-Spam — auch ein Regel- oder LLM-Treffer feuert nicht, solange die letzte Karte noch
im Cooldown-Fenster liegt.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from souffleur.audit.audit_log import AuditLog
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, LlmPort
from souffleur.trigger.rules import (
    CARD_TYPE_DEEPENING_QUESTION,
    CARD_TYPE_OBJECTION,
    CARD_TYPE_STRUCTURE_HINT,
    RuleDecision,
    apply_rules,
)

DEFAULT_COOLDOWN_MS = 8000

_VALID_CARD_TYPES = (CARD_TYPE_OBJECTION, CARD_TYPE_DEEPENING_QUESTION, CARD_TYPE_STRUCTURE_HINT)

TriggerSource = Literal["rules", "llm"]

CLASSIFIER_SYSTEM_PROMPT = (
    "Du klassifizierst eine einzelne Äußerung aus einem Coaching-Gespräch. Antworte NUR mit "
    "genau einem Wort: 'no_card', 'objection', 'deepening_question' oder 'structure_hint'."
)


@dataclass(frozen=True)
class TriggerDecision:
    """Ergebnis von `TriggerRouter.decide` — `fire=False` deckt No-Card UND Cooldown ab."""

    fire: bool
    card_type: str | None
    source: TriggerSource


def _default_clock() -> int:
    return int(time.monotonic() * 1000)


def _normalize_card_type(label: str) -> str | None:
    for card_type in _VALID_CARD_TYPES:
        if card_type in label:
            return card_type
    return None


class TriggerRouter:
    """Entscheidet, ob und mit welchem Karten-Typ die ReasoningEngine ausgelöst wird."""

    def __init__(
        self,
        llm_port: LlmPort,
        settings: Settings,
        *,
        audit_log: AuditLog | None = None,
        cooldown_ms: int = DEFAULT_COOLDOWN_MS,
        clock: Callable[[], int] = _default_clock,
    ) -> None:
        self._llm = llm_port
        self._settings = settings
        self._audit_log = audit_log
        self._cooldown_ms = cooldown_ms
        self._clock = clock
        self._last_fired_at_ms: dict[str, int] = {}

    async def decide(
        self,
        *,
        session_id: str,
        tenant_id: str,
        text: str,
        silence_ms: int = 0,
        correlation_id: str | None = None,
    ) -> TriggerDecision:
        verdict = apply_rules(text, silence_ms=silence_ms)

        if verdict.decision == RuleDecision.NO_CARD:
            return TriggerDecision(fire=False, card_type=None, source="rules")

        if verdict.decision == RuleDecision.CARD:
            return self._apply_cooldown(session_id, verdict.card_type, source="rules")

        # RuleDecision.UNCERTAIN -> billiger LLM-Klassifikator (ministral-3b-2512).
        # Finding 12 (Trigger-Kosten vor Cooldown): der Cooldown-Check MUSS vor dem bezahlten
        # classify-Aufruf greifen — sonst zahlt jede Session während des Cooldown-Fensters für
        # Klassifikationen, deren Ergebnis ohnehin nie feuern darf.
        if self._in_cooldown(session_id):
            return TriggerDecision(fire=False, card_type=None, source="rules")

        classification = await self._llm.classify(
            [
                ChatMessage(role="system", content=CLASSIFIER_SYSTEM_PROMPT),
                ChatMessage(role="user", content=text),
            ]
        )
        if self._audit_log is not None:
            self._audit_log.record(
                actor="trigger_router",
                action="model_call",
                resource=f"{self._settings.model_trigger}:classify",
                tenant_id=tenant_id,
                result="success",
                model=self._settings.model_trigger,
                correlation_id=correlation_id,
            )

        card_type = _normalize_card_type(classification.label.strip().lower())
        if card_type is None:
            return TriggerDecision(fire=False, card_type=None, source="llm")
        return self._apply_cooldown(session_id, card_type, source="llm")

    def forget_session(self, session_id: str) -> None:
        """Entfernt den Cooldown-Zustand einer beendeten Session (Finding 15, Leak-Fix) —
        ohne das würde `_last_fired_at_ms` über die Prozesslaufzeit unbegrenzt wachsen, weil
        nie eine Session-ID entfernt wird. No-Op, wenn die Session nie gefeuert hat."""
        self._last_fired_at_ms.pop(session_id, None)

    def _in_cooldown(self, session_id: str, *, now: int | None = None) -> bool:
        """Prüft NUR (mutiert nichts) — Vorbedingung, bevor überhaupt klassifiziert wird."""
        now = self._clock() if now is None else now
        last_fired_at = self._last_fired_at_ms.get(session_id)
        return last_fired_at is not None and (now - last_fired_at) < self._cooldown_ms

    def _apply_cooldown(
        self, session_id: str, card_type: str | None, *, source: TriggerSource
    ) -> TriggerDecision:
        now = self._clock()
        if self._in_cooldown(session_id, now=now):
            return TriggerDecision(fire=False, card_type=None, source=source)
        self._last_fired_at_ms[session_id] = now
        return TriggerDecision(fire=True, card_type=card_type, source=source)
