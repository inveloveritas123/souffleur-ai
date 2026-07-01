"""Welle 12/Fix — voxtral_api Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`).

Die WS-Verbindung ist vollständig gemockt (`FakeWebSocket` unten) — kein echter Netzaufruf
gegen `wss://api.mistral.ai` (Gate E1/E2). Das hier gemockte Wireformat ist NICHT mehr eine
Annahme, sondern das VERIFIZIERTE Format (siehe Modul-Docstring in `voxtral_api.py`
"Live-Streaming"): ein eigenständiges Probe-Skript hat gegen den echten Endpunkt ein
vollständiges deutsches Transkript zurückbekommen. Kernpunkte, die diese Tests belegen:

- Handshake: `session.created` zuerst, dann sendet der Adapter `session.update`.
- Audio geht als `{"type":"input_audio.append","audio":"<base64>"}` (JSON-Text), NICHT als
  roher Binär-Frame.
- Events heißen `transcription.text.delta` (partial, kein Zeitstempel vom Server),
  `transcription.segment` (final, mit echten `start`/`end`/optionalem `speaker_id` —
  laut Referenz-Schema real, in eigenen Probe-Läufen aber nie beobachtet, hier defensiv
  getestet) und `transcription.done` (final, der tatsächlich beobachtete Pfad, ausgelöst durch
  `input_audio.flush`/`input_audio.end`).
- Kein `channel`-Feld existiert real — Live-Events tragen `speaker="unknown"`, außer
  `transcription.segment` liefert ein reales `speaker_id`.
- `close_stream` sendet `input_audio.flush` + `input_audio.end` (kein "session.end").
"""
from __future__ import annotations

import asyncio
import base64
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


_SESSION_CREATED = {
    "type": "session.created",
    "session": {
        "request_id": "ws-test-request-id",
        "model": "voxtral-mini-transcribe-realtime-2602",
        "audio_format": {"encoding": "pcm_s16le", "sample_rate": 16000},
        "target_streaming_delay_ms": None,
    },
}


class FakeWebSocket:
    """Minimaler WS-Double: sammelt gesendete Frames, liefert vorgegebene Server-Nachrichten
    als fortlaufende Queue (KEIN Reset bei erneutem `__aiter__` — das entspricht einer echten
    Websocket-Verbindung, bei der `open_stream` bereits eine Nachricht konsumiert, bevor
    `events()` weiterliest)."""

    def __init__(self, server_messages: list[dict[str, Any]]) -> None:
        self._queue: list[dict[str, Any]] = list(server_messages)
        self.sent: list[Any] = []
        self.closed = False

    async def send(self, message: Any) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> FakeWebSocket:
        return self

    async def __anext__(self) -> str:
        if not self._queue:
            raise StopAsyncIteration
        return json.dumps(self._queue.pop(0))

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        return [json.loads(m) for m in self.sent]


def _ws_connect_factory(fake_ws: FakeWebSocket) -> AsyncMock:
    return AsyncMock(return_value=fake_ws)


def test_open_stream_connects_to_eu_wss_endpoint_with_live_model_and_completes_handshake() -> None:
    fake_ws = FakeWebSocket([_SESSION_CREATED])
    connect = _ws_connect_factory(fake_ws)
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=connect)

    handle = asyncio.run(port.open_stream(_dual_source_session()))

    assert handle.correlation_id
    connect.assert_awaited_once()
    args, kwargs = connect.call_args
    url = args[0]
    assert url == "wss://api.mistral.ai/v1/audio/transcriptions/realtime?model=voxtral-mini-transcribe-realtime-2602"
    assert kwargs["additional_headers"]["Authorization"] == "Bearer test-key"

    # VERIFIZIERT: nach session.created sendet der Adapter session.update mit dem echten
    # Audioformat (encoding/sample_rate), NICHT als Query-Parameter.
    assert len(fake_ws.sent_messages) == 1
    update = fake_ws.sent_messages[0]
    assert update["type"] == "session.update"
    assert update["session"]["audio_format"] == {"encoding": "pcm_s16le", "sample_rate": 16000}
    assert update["session"]["target_streaming_delay_ms"] == 480


def test_open_stream_raises_if_first_message_is_not_session_created() -> None:
    fake_ws = FakeWebSocket([{"type": "transcription.text.delta", "text": "zu früh"}])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    with pytest.raises(VoxtralLiveStreamError):
        asyncio.run(port.open_stream(_dual_source_session()))


def test_open_stream_raises_on_realtime_error_during_handshake() -> None:
    fake_ws = FakeWebSocket([{"type": "error", "error": {"message": "invalid model", "code": 1}}])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    with pytest.raises(VoxtralLiveStreamError, match="invalid model"):
        asyncio.run(port.open_stream(_dual_source_session()))


def test_push_audio_sends_base64_json_input_audio_append_not_raw_bytes() -> None:
    """VERIFIZIERT: ein roher Binär-Frame wird vom echten Server ignoriert (keine Antwort,
    keine Transkription) — Audio muss als base64-JSON-Textnachricht gehen."""
    fake_ws = FakeWebSocket([_SESSION_CREATED])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> None:
        handle = await port.open_stream(_dual_source_session())
        await port.push_audio(handle, b"\x00\x01\x02\x03")

    asyncio.run(scenario())

    # sent[0] ist das session.update aus dem Handshake, sent[1] der Audio-Frame.
    assert len(fake_ws.sent_messages) == 2
    append = fake_ws.sent_messages[1]
    assert append["type"] == "input_audio.append"
    assert base64.b64decode(append["audio"]) == b"\x00\x01\x02\x03"


def test_push_audio_rejects_chunks_over_the_verified_server_limit() -> None:
    fake_ws = FakeWebSocket([_SESSION_CREATED])
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))
    oversized_chunk = b"\x00" * (262144 + 1)

    async def scenario() -> None:
        handle = await port.open_stream(_dual_source_session())
        await port.push_audio(handle, oversized_chunk)

    with pytest.raises(VoxtralLiveStreamError):
        asyncio.run(scenario())


def test_events_yields_partial_deltas_and_final_done_event() -> None:
    """VERIFIZIERT der tatsächlich beobachtete Live-Pfad: text.delta (partial, kein
    Zeitstempel vom Server) gefolgt von transcription.done (final, ausgelöst durch
    flush/end) nach echtem Probe-Lauf gegen wss://api.mistral.ai."""
    server_messages: list[dict[str, Any]] = [
        _SESSION_CREATED,
        {"type": "session.updated", "session": _SESSION_CREATED["session"]},
        {"type": "transcription.text.delta", "text": "Das"},
        {"type": "transcription.text.delta", "text": " Budget"},
        {
            "type": "transcription.done",
            "model": "voxtral-mini-transcribe-realtime-2602",
            "text": "Das Budget ist zu hoch.",
            "language": None,
            "segments": [],
            "usage": {"prompt_audio_seconds": 1},
        },
    ]
    fake_ws = FakeWebSocket(server_messages)
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> list[Any]:
        handle = await port.open_stream(_dual_source_session())
        await port.push_audio(handle, b"\x00\x00" * 8000)  # 8000 Samples @16kHz = 500ms
        events = []
        async for event in port.events(handle):
            events.append(event)
        return events

    events = asyncio.run(scenario())

    assert len(events) == 3
    assert events[0].kind == "partial"
    assert events[0].text == "Das"
    assert events[0].speaker == "unknown"  # kein channel-Feld real — ehrlicher Fallback
    assert events[1].kind == "partial"
    assert events[1].text == " Budget"
    assert events[2].kind == "final"
    assert events[2].text == "Das Budget ist zu hoch."
    assert events[2].t_end_ms == 500  # aus der lokal gezählten Audiolänge, nicht vom Server


def test_events_yields_final_from_transcription_segment_with_speaker_id() -> None:
    """`transcription.segment` ist laut Referenz-Schema real (text/start/end/speaker_id),
    in eigenen Probe-Läufen aber NIE beobachtet — hier defensiv abgesichert."""
    server_messages: list[dict[str, Any]] = [
        _SESSION_CREATED,
        {
            "type": "transcription.segment",
            "text": "Das Budget ist zu hoch.",
            "start": 0.0,
            "end": 1.2,
            "speaker_id": "1",
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

    assert len(events) == 1
    assert events[0].kind == "final"
    assert events[0].speaker == "speaker_1"
    assert events[0].t_start_ms == 0
    assert events[0].t_end_ms == 1200


def test_events_raises_on_realtime_error_message() -> None:
    fake_ws = FakeWebSocket(
        [_SESSION_CREATED, {"type": "error", "error": {"message": "quota exceeded", "code": 42}}]
    )
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(fake_ws))

    async def scenario() -> None:
        handle = await port.open_stream(_dual_source_session())
        async for _event in port.events(handle):
            pass

    with pytest.raises(VoxtralLiveStreamError, match="quota exceeded"):
        asyncio.run(scenario())


def test_close_stream_sends_flush_then_end_and_returns_transcript_result() -> None:
    """VERIFIZIERT: kein 'session.end' — stattdessen input_audio.flush gefolgt von
    input_audio.end (das reale Protokoll kennt kein session.end)."""
    server_messages: list[dict[str, Any]] = [
        _SESSION_CREATED,
        {"type": "transcription.text.delta", "text": "partial"},
        {
            "type": "transcription.done",
            "model": "voxtral-mini-transcribe-realtime-2602",
            "text": "final text",
            "language": None,
            "segments": [],
            "usage": {},
        },
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
    assert len(result.segments) == 1  # nur final (transcription.done), kein partial
    assert result.segments[0].text == "final text"
    assert result.speakers == ["unknown"]
    assert fake_ws.closed is True

    sent = fake_ws.sent_messages
    assert sent[-2] == {"type": "input_audio.flush"}
    assert sent[-1] == {"type": "input_audio.end"}


def test_events_publishes_transcript_events_onto_the_bus() -> None:
    """Kern-Akzeptanz W12: publiziert transcript-Events auf den Bus."""
    server_messages: list[dict[str, Any]] = [
        _SESSION_CREATED,
        {
            "type": "transcription.done",
            "model": "voxtral-mini-transcribe-realtime-2602",
            "text": "Hallo Welt",
            "language": None,
            "segments": [],
            "usage": {},
        },
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
    # Verifizierte Lücke: ohne echtes channel-Feld ist der Sprecher nicht coach/counterpart
    # zuordenbar — der Bus bekommt ehrlich None statt eines erfundenen Sprechers.
    assert bus_event.payload.speaker is None
    assert bus_event.payload.text == "Hallo Welt"
    assert bus_event.seq == 1


def test_push_audio_on_unknown_handle_raises_live_stream_error() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), ws_connect=_ws_connect_factory(FakeWebSocket([])))
    from souffleur.ports.types import StreamHandle

    async def scenario() -> None:
        await port.push_audio(StreamHandle(provider_handle="ghost", correlation_id="ghost"), b"\x00")

    with pytest.raises(VoxtralLiveStreamError):
        asyncio.run(scenario())
