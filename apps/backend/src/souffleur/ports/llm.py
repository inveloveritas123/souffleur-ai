"""LlmPort — austauschbares Reasoning-/Klassifikations-Interface (ARCHITECTURE.md).

Zwei Rollen über Single-Provider Mistral (EU, Paris):
- streamende Reasoning-Methode (`stream_reasoning`, Modell `magistral-medium-2509`):
  erzeugt Coaching-Karten (Phase 2) bzw. die Protokoll-Zusammenfassung (Phase 1, Welle 6).
- schnelle, billige Klassifikationsmethode (`classify`, Modell `ministral-3b-2512`):
  Trigger-Router-Entscheidung "Karte ja/nein?" (Welle 13) bzw. andere leichte Einordnungen.

Wie bei `TranscriptionPort` kennt kein Aufrufer den konkreten Adapter — die
Modell-Wahl steckt in den gepinnten `Settings`-Feldern (`model_reasoning`,
`model_trigger`), nie im Aufrufer-Code (Gate F1).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """Eine einzelne Chat-Nachricht für Reasoning oder Klassifikation."""

    role: ChatRole
    content: str


@dataclass(frozen=True)
class ClassificationResult:
    """Ergebnis der schnellen Klassifikation (z. B. ministral-3b-2512 Trigger-Entscheidung)."""

    label: str
    raw_text: str
    model: str


@runtime_checkable
class LlmPort(Protocol):
    """Vertrag, den jeder LLM-Adapter erfüllen muss."""

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Streamt Text-Deltas vom Reasoning-Modell (magistral-medium-2509)."""
        ...

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        """Schnelle, billige Klassifikation (ministral-3b-2512)."""
        ...
