"""Welle 14 — WebSocket-API für Live-Coaching (`api/live.py`).

Kein echter STT-/LLM-/MCP-Aufruf — `FakeTranscriptionPort`/`FakeLlmPort`/`FakeMcpClient`
ersetzen alle externen Abhängigkeiten (Gate E1/E2). `ConsentGate`/`AuditLog` sind echte
Instanzen (derselbe Vertrag wie Phase 1, `api/protocol.py`).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from souffleur.api.live import LIVE_WS_PATH, LiveDeps, build_live_router
from souffleur.audit.audit_log import AuditLog
from souffleur.bus import BusEvent, BusEventPayload, InProcessTranscriptEventBus, now_ms
from souffleur.core.consent import ConsentGate, ConsentRecord
from souffleur.core.reasoning import ReasoningEngine
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, ClassificationResult
from souffleur.ports.types import SessionContext, StreamHandle, TranscriptEvent, TranscriptResult
from souffleur.trigger.router import TriggerRouter
from starlette.websockets import WebSocketDisconnect


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


class FakeLlmPort:
    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        return ClassificationResult(label="no_card", raw_text="no_card", model="ministral-3b-2512")

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        for chunk in ("Karte", " bauen."):
            yield chunk


class FakeMcpClient:
    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        return [{"id": "k1", "card_type": card_type, "title": "Reframe", "guidance": "Frag nach."}]


class FakeTranscriptionPort:
    """Ersetzt den Live-STT-Adapter — publiziert Transkript-Events selbst auf den Bus,
    genau wie `VoxtralApiTranscriptionPort` es in Welle 12 tut (siehe test_voxtral_stream.py)."""

    def __init__(
        self,
        transcript_events: list[TranscriptEvent],
        event_bus: InProcessTranscriptEventBus | None = None,
    ) -> None:
        self._transcript_events = transcript_events
        self._event_bus = event_bus
        self.pushed_audio: list[bytes] = []
        self.opened_sessions: list[SessionContext] = []
        self.closed_handles: list[StreamHandle] = []
        self._session: SessionContext | None = None

    async def open_stream(self, session: SessionContext) -> StreamHandle:
        self._session = session
        self.opened_sessions.append(session)
        return StreamHandle(provider_handle="live-handle-1", correlation_id="corr-open-1")

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        self.pushed_audio.append(pcm_chunk)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        assert self._session is not None
        seq = 0
        for event in self._transcript_events:
            if self._event_bus is not None:
                seq += 1
                await self._event_bus.publish(
                    self._session.session_id,
                    BusEvent(
                        type="transcript.final" if event.kind == "final" else "transcript.partial",
                        session_id=self._session.session_id,
                        tenant_id=self._session.tenant_id,
                        seq=seq,
                        ts_ms=now_ms(),
                        payload=BusEventPayload(
                            speaker=event.speaker,
                            text=event.text,
                            t_start_ms=event.t_start_ms,
                            t_end_ms=event.t_end_ms,
                        ),
                        correlation_id=handle.correlation_id,
                    ),
                )
            yield event

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        self.closed_handles.append(handle)
        return TranscriptResult(
            segments=[], speakers=["unknown"], duration_ms=0, model="voxtral-mini-transcribe-realtime-2602",
            provider="voxtral_api",
        )

    def capabilities(self) -> Any:  # pragma: no cover - nicht benötigt in diesem Test
        raise NotImplementedError


def _build_app(deps: LiveDeps) -> FastAPI:
    app = FastAPI()
    app.include_router(build_live_router(deps))
    return app


def _drain_messages(ws: Any, max_messages: int = 30) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for _ in range(max_messages):
        try:
            messages.append(ws.receive_json())
        except WebSocketDisconnect:
            break
    return messages


def test_live_ws_rejects_audio_processing_without_consent(tmp_path: Any) -> None:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    settings = _settings()
    bus = InProcessTranscriptEventBus()
    transcription_port = FakeTranscriptionPort([], event_bus=bus)
    deps = LiveDeps(
        settings=settings,
        transcription_port=transcription_port,
        consent_gate=ConsentGate(),  # keine Einwilligung registriert
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=TriggerRouter(FakeLlmPort(), settings),
        reasoning_engine=ReasoningEngine(FakeLlmPort(), FakeMcpClient(), bus, settings, audit_log=audit_log),
    )
    app = _build_app(deps)
    client = TestClient(app)

    with client.websocket_connect(LIVE_WS_PATH) as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "start",
                    "tenant_id": "zukunftsbund",
                    "session_id": "s-denied",
                    "consent_ref": "missing-ref",
                }
            )
        )
        response = ws.receive_json()

    assert response["type"] == "error"
    assert transcription_port.opened_sessions == []  # nie verarbeitet

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["result"] == "denied"
    assert entry["tenant_id"] == "zukunftsbund"


def test_live_ws_accepts_audio_after_consent_and_forwards_transcript_and_card_events(
    tmp_path: Any,
) -> None:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    settings = _settings()
    bus = InProcessTranscriptEventBus()
    consent_gate = ConsentGate()
    consent_gate.register(
        ConsentRecord(
            consent_ref="consent-1", tenant_id="zukunftsbund", session_id="s1", granted_at="2026-07-01T00:00:00Z"
        )
    )
    transcript_events = [
        TranscriptEvent(
            kind="final", speaker="counterpart", text="Das Budget ist zu hoch.", t_start_ms=0, t_end_ms=900
        )
    ]
    transcription_port = FakeTranscriptionPort(transcript_events, event_bus=bus)
    trigger_router = TriggerRouter(FakeLlmPort(), settings)  # "zu hoch" -> Regel-Fast-Path: objection
    reasoning_engine = ReasoningEngine(FakeLlmPort(), FakeMcpClient(), bus, settings, audit_log=audit_log)

    deps = LiveDeps(
        settings=settings,
        transcription_port=transcription_port,
        consent_gate=consent_gate,
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=trigger_router,
        reasoning_engine=reasoning_engine,
    )
    app = _build_app(deps)
    client = TestClient(app)

    with client.websocket_connect(LIVE_WS_PATH) as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "start",
                    "tenant_id": "zukunftsbund",
                    "session_id": "s1",
                    "consent_ref": "consent-1",
                    "sample_rate": 16000,
                }
            )
        )
        ws.send_bytes(b"\x00\x01\x02\x03")
        ws.send_text(json.dumps({"type": "stop"}))
        messages = _drain_messages(ws)

    event_types = [m["type"] for m in messages]

    assert "transcript.final" in event_types
    assert "trigger.fired" in event_types
    assert "card.streamed" in event_types
    assert "card.proposed" in event_types
    assert "session.closed" in event_types

    transcript_msg = next(m for m in messages if m["type"] == "transcript.final")
    assert transcript_msg["payload"]["text"] == "Das Budget ist zu hoch."
    assert transcript_msg["session_id"] == "s1"
    assert transcript_msg["tenant_id"] == "zukunftsbund"

    trigger_msg = next(m for m in messages if m["type"] == "trigger.fired")
    assert trigger_msg["payload"]["text"] == "objection"

    assert transcription_port.pushed_audio == [b"\x00\x01\x02\x03"]
    assert transcription_port.opened_sessions[0].channels == 2  # Dual-Source
    assert len(transcription_port.closed_handles) == 1

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines]
    resources = [e["resource"] for e in entries]
    assert any("voxtral-mini-transcribe-realtime-2602" in r for r in resources)
    assert any("magistral-medium-2509" in r for r in resources)
    assert all(e["result"] == "success" for e in entries)
    assert all(e["pii_present"] is False for e in entries)
    assert all(e["routing_region"] == "EU" for e in entries)


def test_live_ws_forgets_trigger_cooldown_state_when_session_closes(tmp_path: Any) -> None:
    """Finding 15 (Leak): `TriggerRouter._last_fired_at_ms` darf nach Session-Ende keinen
    Eintrag mehr für die beendete Session halten — sonst wächst das Dict unbegrenzt über die
    Prozesslaufzeit (jede Live-Session, die je eine Karte ausgelöst hat, bliebe für immer drin)."""
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    settings = _settings()
    bus = InProcessTranscriptEventBus()
    consent_gate = ConsentGate()
    consent_gate.register(
        ConsentRecord(
            consent_ref="consent-1", tenant_id="zukunftsbund", session_id="s1", granted_at="2026-07-01T00:00:00Z"
        )
    )
    transcript_events = [
        TranscriptEvent(
            kind="final", speaker="counterpart", text="Das Budget ist zu hoch.", t_start_ms=0, t_end_ms=900
        )
    ]
    transcription_port = FakeTranscriptionPort(transcript_events, event_bus=bus)
    trigger_router = TriggerRouter(FakeLlmPort(), settings)  # "zu hoch" -> Regel-Fast-Path: objection
    reasoning_engine = ReasoningEngine(FakeLlmPort(), FakeMcpClient(), bus, settings, audit_log=audit_log)

    deps = LiveDeps(
        settings=settings,
        transcription_port=transcription_port,
        consent_gate=consent_gate,
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=trigger_router,
        reasoning_engine=reasoning_engine,
    )
    app = _build_app(deps)
    client = TestClient(app)

    with client.websocket_connect(LIVE_WS_PATH) as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "start",
                    "tenant_id": "zukunftsbund",
                    "session_id": "s1",
                    "consent_ref": "consent-1",
                    "sample_rate": 16000,
                }
            )
        )
        ws.send_text(json.dumps({"type": "stop"}))
        _drain_messages(ws)

    # Der Trigger tatsächlich gefeuert zu haben, ist Voraussetzung dafür, dass dieser Test
    # den Leak überhaupt beobachten könnte (sonst gäbe es nie einen Eintrag).
    assert "s1" not in trigger_router._last_fired_at_ms  # noqa: SLF001 - Leak-Test, interner Zustand


def test_live_ws_rejects_missing_consent_ref_entirely(tmp_path: Any) -> None:
    """`consent_ref` fehlt komplett in der Start-Nachricht — auch das ist eine Ablehnung."""
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    settings = _settings()
    bus = InProcessTranscriptEventBus()
    transcription_port = FakeTranscriptionPort([], event_bus=bus)
    deps = LiveDeps(
        settings=settings,
        transcription_port=transcription_port,
        consent_gate=ConsentGate(),
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=TriggerRouter(FakeLlmPort(), settings),
        reasoning_engine=ReasoningEngine(FakeLlmPort(), FakeMcpClient(), bus, settings, audit_log=audit_log),
    )
    app = _build_app(deps)
    client = TestClient(app)

    with client.websocket_connect(LIVE_WS_PATH) as ws:
        ws.send_text(json.dumps({"type": "start", "tenant_id": "zukunftsbund", "session_id": "s2"}))
        response = ws.receive_json()

    assert response["type"] == "error"
    assert transcription_port.opened_sessions == []


class _FlakyOnceLlmPort:
    """`classify` wirft beim ERSTEN Aufruf (simuliert einen einmaligen Trigger-/LLM-Fehler),
    danach klassifiziert es normal weiter — für Finding 9 (Live-Pipeline stirbt still)."""

    def __init__(self) -> None:
        self.classify_calls = 0

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        self.classify_calls += 1
        if self.classify_calls == 1:
            raise RuntimeError("boom - ministral-3b-Klassifikation vorübergehend fehlgeschlagen")
        return ClassificationResult(label="objection", raw_text="objection", model="ministral-3b-2512")

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        for chunk in ("Karte", " bauen."):
            yield chunk


def test_live_ws_survives_single_trigger_error_and_keeps_processing_later_segments(
    tmp_path: Any,
) -> None:
    """Finding 9 (Live-Pipeline stirbt still): früher umschloss `contextlib.suppress(Exception)`
    die GANZE `async for`-Schleife über STT-Events — ein einzelner Fehler (hier: der erste
    `ministral-3b`-Klassifikationsversuch) beendete die Schleife komplett und STILL; alle
    folgenden Segmente der Session wurden nie mehr verarbeitet. Der Fix fängt Fehler PRO
    Iteration — das erste (unsichere, nicht regelbasierte) Segment scheitert, das zweite muss
    trotzdem noch eine Karte auslösen."""
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    settings = _settings()
    bus = InProcessTranscriptEventBus()
    consent_gate = ConsentGate()
    consent_gate.register(
        ConsentRecord(
            consent_ref="consent-1", tenant_id="zukunftsbund", session_id="s1", granted_at="2026-07-01T00:00:00Z"
        )
    )
    # Beide Texte sind absichtlich UNCERTAIN im Regel-Vorfilter (kein "?", kein Einwand-Marker,
    # keine lange Stille) — nur so ruft der TriggerRouter tatsächlich `classify` auf.
    transcript_events = [
        TranscriptEvent(
            kind="final",
            speaker="counterpart",
            text="Wir haben letzte Woche über die neuen Ziele fürs Team gesprochen und Notizen gemacht.",
            t_start_ms=0,
            t_end_ms=900,
        ),
        TranscriptEvent(
            kind="final",
            speaker="counterpart",
            text="Lassen Sie uns die Roadmap fuer das naechste Quartal gemeinsam durchgehen und Notizen dazu machen.",
            t_start_ms=900,
            t_end_ms=1800,
        ),
    ]
    transcription_port = FakeTranscriptionPort(transcript_events, event_bus=bus)
    flaky_llm = _FlakyOnceLlmPort()
    trigger_router = TriggerRouter(flaky_llm, settings, cooldown_ms=0)
    reasoning_engine = ReasoningEngine(flaky_llm, FakeMcpClient(), bus, settings, audit_log=audit_log)

    deps = LiveDeps(
        settings=settings,
        transcription_port=transcription_port,
        consent_gate=consent_gate,
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=trigger_router,
        reasoning_engine=reasoning_engine,
    )
    app = _build_app(deps)
    client = TestClient(app)

    with client.websocket_connect(LIVE_WS_PATH) as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "start",
                    "tenant_id": "zukunftsbund",
                    "session_id": "s1",
                    "consent_ref": "consent-1",
                    "sample_rate": 16000,
                }
            )
        )
        ws.send_text(json.dumps({"type": "stop"}))
        messages = _drain_messages(ws)

    event_types = [m["type"] for m in messages]

    # Trotz des ersten (gescheiterten) Klassifikationsversuchs: die Session läuft normal zu
    # Ende (kein Hang, kein Abbruch) UND das zweite Segment löst noch eine Karte aus.
    assert flaky_llm.classify_calls == 2  # beide Segmente wurden versucht, keines übersprungen
    assert "trigger.fired" in event_types
    assert "card.streamed" in event_types
    assert "card.proposed" in event_types
    assert "session.closed" in event_types


def test_live_ws_does_not_break_phase_1_rest_router(tmp_path: Any) -> None:
    """Der Live-Router lässt sich neben dem Phase-1-REST-Router einhängen (kein Konflikt)."""
    from unittest.mock import MagicMock

    from souffleur.api.protocol import ProtocolDeps, build_protocol_router

    settings = _settings()
    bus = InProcessTranscriptEventBus()
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    protocol_deps = ProtocolDeps(
        settings=settings,
        transcription_port=MagicMock(),
        llm_port=MagicMock(),
        consent_gate=ConsentGate(),
        audit_log=audit_log,
    )
    live_deps = LiveDeps(
        settings=settings,
        transcription_port=FakeTranscriptionPort([], event_bus=bus),
        consent_gate=ConsentGate(),
        audit_log=audit_log,
        event_bus=bus,
        trigger_router=TriggerRouter(FakeLlmPort(), settings),
        reasoning_engine=ReasoningEngine(FakeLlmPort(), FakeMcpClient(), bus, settings, audit_log=audit_log),
    )

    app = FastAPI()
    app.include_router(build_protocol_router(protocol_deps))
    app.include_router(build_live_router(live_deps))

    route_paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/protocol" in route_paths
    assert LIVE_WS_PATH in route_paths
