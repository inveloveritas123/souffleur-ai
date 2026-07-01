"""Welle 12 — voxtral_api Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`).

Die WS-Verbindung ist vollständig gemockt (`FakeWebSocket` unten) — kein echter Netzaufruf
gegen `wss://api.mistral.ai` (Gate E1/E2). Siehe Modul-Docstring in `voxtral_api.py`
"Abweichung/Annahme (dokumentiert)": das Roh-WS-JSON-Wireformat ist ein eigener, dokumentierter
Kontrakt dieses Adapters (die SDK-seitige `audio.realtime`-Semantik ist verifiziert, das rohe
Wireformat nicht) — dieser Test belegt genau diesen Kontrakt.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from souffleur.adapters.stt.voxtral_api import (
    VoxtralApiTranscriptionPort,
    VoxtralLiveStreamError,
)
from souffleur.bus import InProcessTranscriptEventBus
from souffleur.core.settings import Settings
from souffleur.ports.types import SessionContext


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


def _dual_source_session() -> SessionContext:
    return SessionContext(
        tenant_id="zukunftsbund",
        session_id="live-session-1",
        consent_ref="consent-1",
        sample_rate=16000,
        channels=2,
    )


class FakeWebSocket:
    """Minimaler WS-Double: sammelt gesendete Frames, liefert vorgegebene Server-Nachrichten."""

    def __init__(self, server_messages: list[dict[str, Any]]) -> None:
        self._server_messages = server_messages
        self.sent: list[Any] = []
        self.closed = False

    async def send(self, message: Any) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> FakeWebSocket:
        self._iter = iter(self._server_messages)
        return self

    async def __anext__(self) -> str:
        try:
            message = next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
        return json.dumps(message)


def _ws_connect_factory(fake_ws: FakeWebSocket) -> AsyncMock:
    return AsyncMock(return_value=fake_ws)


def test_open_stream_connects_to_eu_wss_endpoint_with_live_model() -> None:
    fake_ws = FakeWebSocket([])
    connect = _ws_connect_factory(fake_ws)
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=connect)

    handle = asyncio.run(port.open_stream(_dual_source_session()))

    assert handle.correlation_id
    connect.assert_awaited_once()
    args, kwargs = connect.call_args
    url = args[0]
    assert url.startswith("wss://api.mistral.ai")
    assert "model=voxtral-mini-transcribe-realtime-2602" in url
    assert "channels=2" in url
    assert kwargs["additional_headers"]["Authorization"] == "Bearer test-key"


def test_push_audio_sends_raw_pcm_bytes_over_the_websocket() -> None:
    fake_ws = FakeWebSocket([])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> None:
        handle = await port.open_stream(_dual_source_session())
        await port.push_audio(handle, b"\x00\x01\x02\x03")

    asyncio.run(scenario())

    assert fake_ws.sent == [b"\x00\x01\x02\x03"]


def test_events_yields_partial_and_final_transcript_events() -> None:
    server_messages: list[dict[str, Any]] = [
        {"type": "session.created"},
        {"type": "transcript.delta", "text": "Das Budget", "channel": 1, "start_ms": 0, "end_ms": 400},
        {
            "type": "transcript.completed",
            "text": "Das Budget ist zu hoch.",
            "channel": 1,
            "start_ms": 0,
            "end_ms": 1200,
        },
    ]
    fake_ws = FakeWebSocket(server_messages)
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> list[Any]:
        handle = await port.open_stream(_dual_source_session())
        events = []
        async for event in port.events(handle):
            events.append(event)
        return events

    events = asyncio.run(scenario())

    assert len(events) == 2
    assert events[0].kind == "partial"
    assert events[0].text == "Das Budget"
    assert events[0].speaker == "counterpart"  # Kanal 1 -> System-Audio -> Gegenüber
    assert events[1].kind == "final"
    assert events[1].text == "Das Budget ist zu hoch."
    assert events[1].t_end_ms == 1200


def test_events_raises_on_realtime_error_message() -> None:
    fake_ws = FakeWebSocket([{"type": "error", "message": "quota exceeded"}])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> None:
        handle = await port.open_stream(_dual_source_session())
        async for _event in port.events(handle):
            pass

    with pytest.raises(VoxtralLiveStreamError):
        asyncio.run(scenario())


def test_close_stream_returns_transcript_result_with_final_segments_only() -> None:
    server_messages = [
        {"type": "transcript.delta", "text": "partial", "channel": 0, "start_ms": 0, "end_ms": 100},
        {"type": "transcript.completed", "text": "final text", "channel": 0, "start_ms": 0, "end_ms": 900},
    ]
    fake_ws = FakeWebSocket(server_messages)
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> Any:
        handle = await port.open_stream(_dual_source_session())
        async for _event in port.events(handle):
            pass
        return await port.close_stream(handle)

    result = asyncio.run(scenario())

    assert result.provider == "voxtral_api"
    assert result.model == "voxtral-mini-transcribe-realtime-2602"
    assert len(result.segments) == 1  # nur final, kein partial
    assert result.segments[0].text == "final text"
    assert result.speakers == ["coach"]  # Kanal 0 -> Mikrofon -> Coach
    assert result.duration_ms == 900
    assert fake_ws.closed is True


def test_events_publishes_transcript_events_onto_the_bus() -> None:
    """Kern-Akzeptanz W12: publiziert transcript-Events auf den Bus."""
    server_messages = [
        {"type": "transcript.completed", "text": "Hallo Welt", "channel": 1, "start_ms": 0, "end_ms": 500},
    ]
    fake_ws = FakeWebSocket(server_messages)
    bus = InProcessTranscriptEventBus()
    port = VoxtralApiTranscriptionPort(
        _settings(), ws_connect=_ws_connect_factory(fake_ws), event_bus=bus
    )
    session = _dual_source_session()

    async def scenario() -> list[Any]:
        received: list[Any] = []

        async def consume() -> None:
            async for bus_event in bus.subscribe(session.session_id):
                received.append(bus_event)
                return

        consumer = asyncio.ensure_future(consume())
        await asyncio.sleep(0)

        handle = await port.open_stream(session)
        async for _event in port.events(handle):
            pass

        await asyncio.wait_for(consumer, timeout=1)
        return received

    received = asyncio.run(scenario())

    assert len(received) == 1
    bus_event = received[0]
    assert bus_event.type == "transcript.final"
    assert bus_event.session_id == "live-session-1"
    assert bus_event.tenant_id == "zukunftsbund"
    assert bus_event.payload.speaker == "counterpart"
    assert bus_event.payload.text == "Hallo Welt"
    assert bus_event.seq == 1


def test_push_audio_on_unknown_handle_raises_live_stream_error() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(FakeWebSocket([])))
    from souffleur.ports.types import StreamHandle

    async def scenario() -> None:
        await port.push_audio(StreamHandle(provider_handle="ghost", correlation_id="ghost"), b"\x00")

    with pytest.raises(VoxtralLiveStreamError):
        asyncio.run(scenario())
