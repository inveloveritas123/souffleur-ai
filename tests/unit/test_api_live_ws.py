"""Unit-Tests api/live.py — WebSocket-Live-API (Phase 2): Consent-Gate, Trigger, Bus-Weiterleitung.

Fährt den echten `/ws/v1/live`-Endpunkt über `TestClient.websocket_connect`, aber mit
gefaktem `TranscriptionPort`/`TriggerRouter` — keine echte STT-/LLM-Verbindung. Die
`ReasoningEngine` ist die ECHTE Implementierung (mit gefaktem `LlmPort`/MCP-Client), damit
zusätzlich der reale Karten-Streaming-Pfad über den Bus abgedeckt ist.
"""
from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import (  # noqa: E402
    FakeCoachingKnowledgeClient,
    FakeLlmPort,
    SpyAuditLog,
    default_settings,
)
from fastapi.testclient import TestClient  # noqa: E402
from souffleur.bus.event_bus import InProcessTranscriptEventBus  # noqa: E402
from souffleur.core.app import create_app  # noqa: E402
from souffleur.core.consent import ConsentGate, ConsentRecord  # noqa: E402
from souffleur.core.reasoning import ReasoningEngine  # noqa: E402
from souffleur.ports.types import StreamHandle, TranscriptEvent, TranscriptResult  # noqa: E402
from souffleur.trigger.router import TriggerDecision  # noqa: E402


class _FakeLiveTranscriptionPort:
    """Erfüllt nur den Live-Pfad (`open_stream`/`push_audio`/`events`/`close_stream`)."""

    def __init__(self, events_to_yield: list[TranscriptEvent]) -> None:
        self._events_to_yield = events_to_yield
        self.pushed_chunks: list[bytes] = []
        self.opened_session: Any = None
        self.closed = False

    async def open_stream(self, session: Any) -> StreamHandle:
        self.opened_session = session
        return StreamHandle(provider_handle="handle-1", correlation_id="corr-open-1")

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        self.pushed_chunks.append(pcm_chunk)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        for event in self._events_to_yield:
            yield event

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        self.closed = True
        return TranscriptResult(segments=[], speakers=["unknown"], duration_ms=0, model="m", provider="p")

    def capabilities(self) -> Any:  # pragma: no cover - vom Live-Endpoint nicht genutzt
        raise NotImplementedError


class _FixedTriggerRouter:
    """`TriggerRouter`-Double: feuert immer für Text, der `"trigger"` enthält."""

    def __init__(self) -> None:
        self.decide_calls: list[str] = []

    async def decide(self, *, session_id: str, tenant_id: str, text: str, **kwargs: Any) -> TriggerDecision:
        self.decide_calls.append(text)
        if "trigger" in text:
            return TriggerDecision(fire=True, card_type="objection", source="rules")
        return TriggerDecision(fire=False, card_type=None, source="rules")


def _build_ws_app(events_to_yield: list[TranscriptEvent]):
    settings = default_settings()
    consent_gate = ConsentGate()
    audit_log = SpyAuditLog()
    event_bus = InProcessTranscriptEventBus()
    transcription_port = _FakeLiveTranscriptionPort(events_to_yield)
    trigger_router = _FixedTriggerRouter()
    llm = FakeLlmPort(reasoning_deltas=["Karte-Teil-1 ", "Karte-Teil-2"])
    mcp = FakeCoachingKnowledgeClient(knowledge=[{"title": "t", "guidance": "g"}])
    reasoning_engine = ReasoningEngine(
        llm, mcp, event_bus, settings, audit_log=audit_log  # type: ignore[arg-type]
    )

    app = create_app(
        settings=settings,
        transcription_port=transcription_port,  # Phase-1-Pfad in diesen Tests ungenutzt
        llm_port=llm,  # type: ignore[arg-type]
        consent_gate=consent_gate,
        audit_log=audit_log,  # type: ignore[arg-type]
        event_bus=event_bus,
        live_transcription_port=transcription_port,
        mcp_client=mcp,
        trigger_router=trigger_router,  # type: ignore[arg-type]
        reasoning_engine=reasoning_engine,
    )
    return app, consent_gate, audit_log, transcription_port


def _drain_bus_events(websocket: Any, max_messages: int = 30) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for _ in range(max_messages):
        message = websocket.receive_json()
        messages.append(message)
        if message.get("type") == "session.closed":
            break
    return messages


class LiveWebsocketConsentDeniedTest(unittest.TestCase):
    def test_missing_consent_ref_closes_with_error_and_audit_denied_entry(self) -> None:
        app, _gate, audit_log, _port = _build_ws_app(events_to_yield=[])
        client = TestClient(app)

        with client.websocket_connect("/ws/v1/live") as websocket:
            websocket.send_text('{"tenant_id": "zukunftsbund", "session_id": "s1"}')
            error_message = websocket.receive_json()

        self.assertEqual(error_message["type"], "error")
        self.assertTrue(any(entry.result == "denied" for entry in audit_log.entries))


class LiveWebsocketHappyPathTest(unittest.TestCase):
    def test_final_transcript_triggers_card_and_forwards_bus_events_to_client(self) -> None:
        final_event = TranscriptEvent(
            kind="final", speaker="coach", text="trigger this please", t_start_ms=0, t_end_ms=500
        )
        partial_event = TranscriptEvent(
            kind="partial", speaker="coach", text="trig", t_start_ms=0, t_end_ms=100
        )
        app, gate, audit_log, port = _build_ws_app(events_to_yield=[partial_event, final_event])
        gate.register(
            ConsentRecord(
                consent_ref="c1", tenant_id="zukunftsbund", session_id="s1", granted_at="now"
            )
        )
        client = TestClient(app)

        with client.websocket_connect("/ws/v1/live") as websocket:
            websocket.send_text(
                '{"tenant_id": "zukunftsbund", "session_id": "s1", "consent_ref": "c1",'
                ' "sample_rate": 16000}'
            )
            websocket.send_bytes(b"\x00\x01\x02\x03")
            websocket.send_text('{"type": "stop"}')

            messages = _drain_bus_events(websocket)

        types = [message["type"] for message in messages]
        self.assertIn("trigger.fired", types)
        self.assertIn("card.streamed", types)
        self.assertIn("card.proposed", types)
        self.assertIn("session.closed", types)

        self.assertEqual(port.pushed_chunks, [b"\x00\x01\x02\x03"])
        self.assertTrue(port.closed)
        self.assertEqual(port.opened_session.channels, 2)  # Dual-Source

        model_call_entries = [e for e in audit_log.entries if e.action == "model_call"]
        self.assertTrue(any("open_stream" in e.resource for e in model_call_entries))


if __name__ == "__main__":
    unittest.main()
