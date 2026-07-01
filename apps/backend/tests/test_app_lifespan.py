"""Finding 10 (MCP-Zombie) — `create_app` muss den Coaching-MCP-Client UND den LLM-Client
beim FastAPI-Shutdown sauber schließen (`aclose()`). Vorher wurde `CoachingMcpStdioClient.
aclose()` nie aufgerufen — der stdio-Subprozess blieb als Zombie zurück, sobald die App
beendet wurde (kein Lifespan-Hook registriert). Tests treiben den FastAPI-Lifespan über den
`TestClient`-Context-Manager (`with TestClient(app) as client: ...`) — das feuert Starlettes
Startup-/Shutdown-Events genauso wie ein echter Server-Prozess.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from souffleur.audit.audit_log import AuditLog
from souffleur.core.app import create_app
from souffleur.core.consent import ConsentGate
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, ClassificationResult
from souffleur.ports.types import (
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    TranscriptEvent,
    TranscriptResult,
)


def _settings() -> Settings:
    return Settings(
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


class _FakeTranscriptionPort:
    async def open_stream(self, session: object) -> object:
        raise NotImplementedError

    async def push_audio(self, handle: object, pcm_chunk: bytes) -> None:
        raise NotImplementedError

    async def events(self, handle: object) -> AsyncIterator[TranscriptEvent]:
        raise NotImplementedError
        yield  # pragma: no cover

    async def close_stream(self, handle: object) -> TranscriptResult:
        raise NotImplementedError

    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        raise NotImplementedError

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            supports_diarization=True,
            supports_word_timestamps=True,
            typical_final_latency_ms=300,
            residency="EU",
        )


class _FakeLlmPortWithAclose:
    """Erfüllt LlmPort UND trägt zusätzlich `aclose()` — wie `MistralLlmAdapter` (Finding 15)."""

    def __init__(self) -> None:
        self.aclose_calls = 0

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        yield "x"

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        return ClassificationResult(label="no_card", raw_text="no_card", model="ministral-3b-2512")

    async def aclose(self) -> None:
        self.aclose_calls += 1


class _FakeMcpClientWithAclose:
    """Erfüllt CoachingKnowledgeClient UND trägt `aclose()` — wie `CoachingMcpStdioClient`."""

    def __init__(self) -> None:
        self.aclose_calls = 0

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        return []

    async def aclose(self) -> None:
        self.aclose_calls += 1


class _FakeMcpClientWithoutAclose:
    """Ältere/abweichende `CoachingKnowledgeClient`-Implementierung OHNE `aclose()` — der
    Lifespan-Hook darf hierbei nicht crashen (nur best-effort schließen, wenn vorhanden)."""

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        return []


def _build_app(tmp_path: Path, mcp_client: object, llm_port: object) -> Any:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    return create_app(
        settings=_settings(),
        transcription_port=_FakeTranscriptionPort(),
        llm_port=llm_port,
        consent_gate=ConsentGate(),
        audit_log=audit_log,
        mcp_client=mcp_client,
    )


def test_lifespan_closes_mcp_client_and_llm_client_on_shutdown(tmp_path: Path) -> None:
    mcp_client = _FakeMcpClientWithAclose()
    llm_port = _FakeLlmPortWithAclose()
    app = _build_app(tmp_path, mcp_client, llm_port)

    with TestClient(app) as client:
        assert mcp_client.aclose_calls == 0
        assert llm_port.aclose_calls == 0
        response = client.get("/api/v1/protocol/does-not-exist")
        assert response.status_code in (403, 404)  # Route existiert, Consent/IDOR-Fix greift

    # Nach dem `with`-Block hat Starlette die Shutdown-Events gefeuert -> beide aclose()-Hooks
    # müssen gelaufen sein (Finding 10: MCP-Zombie; Finding 15: Mistral-Client-Leak).
    assert mcp_client.aclose_calls == 1
    assert llm_port.aclose_calls == 1


def test_lifespan_does_not_crash_when_mcp_client_has_no_aclose(tmp_path: Path) -> None:
    """Fail-safe: ein Coaching-Knowledge-Client ohne `aclose()` darf den Shutdown nicht brechen."""
    app = _build_app(tmp_path, _FakeMcpClientWithoutAclose(), _FakeLlmPortWithAclose())

    with TestClient(app) as client:
        client.get("/api/v1/protocol/does-not-exist")
    # Kein Crash beim Verlassen des `with`-Blocks == bestanden.
