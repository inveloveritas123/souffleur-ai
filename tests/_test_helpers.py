"""Geteilte Test-Fixtures für `tests/unit` und `tests/e2e` (Welle 17, Gate C2).

Liegt bewusst flach direkt unter `tests/` (dem `top_level_dir` von
`unittest discover -s tests`, siehe `tests/_pathfix.py`) — dadurch per
`import _test_helpers` sowohl aus `tests/unit/*.py` als auch aus
`tests/e2e/*.py` importierbar, ohne dass die beiden Pakete voneinander
abhängen müssen (relative Imports über Paketgrenzen sind in Python nicht
möglich).

Baut NIE echte Netzwerk-Clients auf und spawnt NIE echte Subprozesse — reine
Werte-Fixtures und einfache Test-Doubles (Fakes), gemäß Aufgabenstellung
"keine echten Netz-/Modell-/Download-Calls".
"""
from __future__ import annotations

import dataclasses
import os
from collections.abc import AsyncIterator
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.audit.audit_log import AuditEntry  # noqa: E402
from souffleur.core.settings import Settings  # noqa: E402
from souffleur.ports.llm import ChatMessage, ClassificationResult  # noqa: E402


def default_settings(**overrides: Any) -> Settings:
    """Eine vollständige, gültige `Settings`-Instanz — Felder überschreibbar.

    Spiegelt `apps/backend/tests/test_protocol_api.py::_settings()` (dieselben
    Pflichtfeldwerte), damit unsere Fakes exakt zu den bereits verifizierten
    Modell-Pins/EU-Endpunkten passen.
    """
    base = Settings(
        mistral_api_key="test-key",
        mistral_base_url="https://api.mistral.ai",
        stt_provider="voxtral_api",
        model_stt_live="voxtral-mini-transcribe-realtime-2602",
        model_stt_batch="voxtral-mini-2602",
        model_reasoning="magistral-medium-2509",
        model_trigger="ministral-3b-2512",
        gladia_api_key=None,
        gladia_base_url="https://api.gladia.io",
        voxtral_local_url="http://voxtral-worker:9000",
        mcp_url="http://coaching-mcp:8080",
        backend_port=8000,
        web_port=5173,
        mcp_port=8080,
        tenant_id="zukunftsbund",
        audit_log_path="./data/audit-log.jsonl",
        retention_days=30,
        require_consent=True,
    )
    return dataclasses.replace(base, **overrides) if overrides else base


def remove_if_exists(path: str) -> None:
    """`addCleanup`-Helfer für temporäre Test-Audiodateien — mypy-sauber (kein `and`-Trick)."""
    if os.path.exists(path):
        os.remove(path)


class SpyAuditLog:
    """`AuditLog`-Double: sammelt Aufrufe von `record(...)` statt eine Datei zu schreiben.

    Erfüllt denselben Aufrufvertrag (`record(**kwargs) -> AuditEntry`) wie die echte
    `souffleur.audit.audit_log.AuditLog` — Tests prüfen `entries`, ohne Dateisystem-I/O.
    """

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        tenant_id: str,
        result: str,
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp="1970-01-01T00:00:00+00:00",
            actor=actor,
            action=action,  # type: ignore[arg-type]
            resource=resource,
            tenant_id=tenant_id,
            result=result,  # type: ignore[arg-type]
            model=model,
            correlation_id=correlation_id,
        )
        self.entries.append(entry)
        return entry


class FakeLlmPort:
    """`LlmPort`-Double: liefert vorgegebene Reasoning-Deltas und einen Klassifikations-Label.

    `stream_reasoning_calls`/`classify_calls` sammeln die genauen Aufrufe (Nachrichtenlisten),
    damit Tests prüfen können, WAS ans Reasoning-/Klassifikationsmodell ginge.
    """

    def __init__(
        self,
        reasoning_deltas: list[str] | None = None,
        classification_label: str = "no_card",
    ) -> None:
        self.reasoning_deltas = reasoning_deltas if reasoning_deltas is not None else ["Karte."]
        self.classification_label = classification_label
        self.stream_reasoning_calls: list[list[ChatMessage]] = []
        self.classify_calls: list[list[ChatMessage]] = []

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_reasoning_calls.append(messages)
        for delta in self.reasoning_deltas:
            yield delta

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        self.classify_calls.append(messages)
        return ClassificationResult(
            label=self.classification_label, raw_text=self.classification_label, model="fake-model"
        )


class FakeCoachingKnowledgeClient:
    """`CoachingKnowledgeClient`-Double — liefert vorgegebenes Coaching-Wissen ohne MCP-Subprozess."""

    def __init__(self, knowledge: list[dict[str, Any]] | None = None) -> None:
        self.knowledge = knowledge if knowledge is not None else []
        self.calls: list[tuple[str, str | None, int]] = []

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        self.calls.append((card_type, query, limit))
        return self.knowledge
