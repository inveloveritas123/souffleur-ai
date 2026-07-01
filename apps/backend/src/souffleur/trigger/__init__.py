"""trigger — TriggerRouter (Welle 13): Regel-Vorfilter + ministral-3b-Klassifikator."""
from __future__ import annotations

from souffleur.trigger.router import (
    CLASSIFIER_SYSTEM_PROMPT,
    DEFAULT_COOLDOWN_MS,
    TriggerDecision,
    TriggerRouter,
    TriggerSource,
)
from souffleur.trigger.rules import (
    CARD_TYPE_DEEPENING_QUESTION,
    CARD_TYPE_OBJECTION,
    CARD_TYPE_STRUCTURE_HINT,
    DEFAULT_SILENCE_THRESHOLD_MS,
    MIN_TRIGGER_CHARS,
    RuleDecision,
    RuleVerdict,
    apply_rules,
)

__all__ = [
    "CARD_TYPE_DEEPENING_QUESTION",
    "CARD_TYPE_OBJECTION",
    "CARD_TYPE_STRUCTURE_HINT",
    "CLASSIFIER_SYSTEM_PROMPT",
    "DEFAULT_COOLDOWN_MS",
    "DEFAULT_SILENCE_THRESHOLD_MS",
    "MIN_TRIGGER_CHARS",
    "RuleDecision",
    "RuleVerdict",
    "TriggerDecision",
    "TriggerRouter",
    "TriggerSource",
    "apply_rules",
]
