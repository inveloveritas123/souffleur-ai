"""Unit-Tests adapters/stt/voxtral_api.py — Live-Streaming (`open_stream`/`push_audio`/

`events`/`close_stream`), Roh-WS vollständig gemockt (kein echter Netzaufruf).

Das hier gemockte Wireformat ist VERIFIZIERT (2026-07, siehe Modul-Docstring in
`voxtral_api.py` "Live-Streaming") — ein eigenständiges Probe-Skript hat gegen den echten
`wss://api.mistral.ai`-Endpunkt ein vollständiges deutsches Transkript zurückbekommen. Diese
Suite spiegelt `apps/backend/tests/test_voxtral_stream.py` (pytest-Variante derselben
Verifikation) in `unittest`-Form, weil `unittest discover -s tests` (Gate C1/C2) diese Datei
separat ausführt.
"""
from __future__ import annotations

import asyncio
import base64
import json
import unittest
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings  # noqa: E402
from souffleur.adapters.stt.voxtral_api import (  # noqa: E402
    VoxtralApiTranscriptionPort,
    VoxtralLiveStreamError,
)
from souffleur.bus.event_bus import BusEvent, InProcessTranscriptEventBus  # noqa: E402
from souffleur.ports.types import SessionContext, StreamHandle  # noqa: E402

_SESSION_CREATED = {
    "type": "session.created",
    "session": {
        "request_id": "ws-test-request-id",
        "model": "voxtral-mini-transcribe-realtime-2602",
        "audio_format": {"encoding": "pcm_s16le", "sample_rate": 16000},
        "target_streaming_delay_ms": None,
    },
}


class _FakeWebSocket:
    """Persistente Nachrichten-Queue — KEIN Reset bei erneutem `__aiter__()` (das entspricht
    einer echten Websocket-Verbindung: `open_stream` konsumiert bereits `session.created` im
    Handshake, `events()` liest danach weiter, ohne die Queue neu zu starten)."""

    def __init__(self, incoming: list[Any]) -> None:
        self._queue: list[Any] = list(incoming)
        self.sent: list[Any] = []
        self.closed = False
        self.send_raises: Exception | None = None
        self.close_raises: Exception | None = None

    async def send(self, message: Any) -> None:
        if self.send_raises is not None:
            raise self.send_raises
        self.sent.append(message)

    async def close(self) -> None:
        if self.close_raises is not None:
            raise self.close_raises
        self.closed = True

    def __aiter__(self) -> _FakeWebSocket:
        return self

    async def __anext__(self) -> Any:
        if not self._queue:
            raise StopAsyncIteration
        return self._queue.pop(0)

    @property
    def sent_json(self) -> list[dict[str, Any]]:
        return [json.loads(m) for m in self.sent if isinstance(m, str)]


def _session() -> SessionContext:
    return SessionContext(
        tenant_id="zukunftsbund", session_id="session-1", consent_ref="c1", sample_rate=16000, channels=2
    )


def _msg(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


class OpenStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_ws_url_with_model_query_param_and_bearer_header(self) -> None:
        captured: dict[str, Any] = {}

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            captured["url"] = url
            captured["headers"] = additional_headers
            return _FakeWebSocket([_msg(_SESSION_CREATED)])

        settings = default_settings(mistral_api_key="secret-key")
        port = VoxtralApiTranscriptionPort(settings, ws_connect=ws_connect)

        handle = await port.open_stream(_session())

        # VERIFIZIERT (2026-07, echter Probe-Lauf): NUR `model` wirkt als Query-Parameter —
        # `channels`/`encoding`/`sample_rate` in der Query werden vom Server ignoriert und
        # gehören daher NICHT mehr in die URL (Abweichung von der vorherigen Annahme).
        self.assertEqual(
            captured["url"],
            f"wss://api.mistral.ai/v1/audio/transcriptions/realtime?model={settings.model_stt_live}",
        )
        self.assertEqual(captured["headers"], {"Authorization": "Bearer secret-key"})
        self.assertEqual(handle.provider_handle, handle.correlation_id)

    async def test_connection_failure_is_translated_to_live_stream_error(self) -> None:
        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            raise RuntimeError("Verbindung abgelehnt")

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)

        with self.assertRaises(VoxtralLiveStreamError):
            await port.open_stream(_session())

    async def test_open_stream_raises_if_first_message_is_not_session_created(self) -> None:
        websocket = _FakeWebSocket([_msg({"type": "transcription.text.delta", "text": "zu früh"})])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)

        with self.assertRaises(VoxtralLiveStreamError):
            await port.open_stream(_session())

    async def test_open_stream_sends_session_update_after_handshake(self) -> None:
        websocket = _FakeWebSocket([_msg(_SESSION_CREATED)])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        await port.open_stream(_session())

        self.assertEqual(len(websocket.sent_json), 1)
        update = websocket.sent_json[0]
        self.assertEqual(update["type"], "session.update")
        self.assertEqual(update["session"]["audio_format"], {"encoding": "pcm_s16le", "sample_rate": 16000})
        self.assertEqual(update["session"]["target_streaming_delay_ms"], 480)


class PushAudioAndEventsTest(unittest.IsolatedAsyncioTestCase):
    async def _open(
        self, incoming_after_handshake: list[Any]
    ) -> tuple[VoxtralApiTranscriptionPort, StreamHandle, _FakeWebSocket]:
        websocket = _FakeWebSocket([_msg(_SESSION_CREATED), *incoming_after_handshake])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())
        return port, handle, websocket

    async def test_push_audio_sends_base64_json_not_raw_bytes(self) -> None:
        """VERIFIZIERT: ein roher Binär-Frame wird vom echten Server ignoriert (keine
        Antwort/Transkription) — Audio muss als base64-JSON-Textnachricht gehen."""
        port, handle, websocket = await self._open([])
        await port.push_audio(handle, b"\x00\x01\x02")

        # sent_json[0] ist das session.update aus dem Handshake.
        append = websocket.sent_json[1]
        self.assertEqual(append["type"], "input_audio.append")
        self.assertEqual(base64.b64decode(append["audio"]), b"\x00\x01\x02")

    async def test_push_audio_rejects_oversized_chunk(self) -> None:
        port, handle, _ws = await self._open([])
        with self.assertRaises(VoxtralLiveStreamError):
            await port.push_audio(handle, b"\x00" * (262144 + 1))

    async def test_push_audio_with_unknown_handle_raises(self) -> None:
        port, _handle, _ws = await self._open([])
        with self.assertRaises(VoxtralLiveStreamError):
            await port.push_audio(StreamHandle(provider_handle="ghost", correlation_id="x"), b"\x00")

    async def test_events_yields_partial_deltas_and_final_done(self) -> None:
        """VERIFIZIERT der tatsächlich beobachtete Live-Pfad: transcription.text.delta
        (partial, kein Server-Zeitstempel) gefolgt von transcription.done (final)."""
        incoming = [
            _msg({"type": "transcription.text.delta", "text": "Guten "}),
            _msg({
                "type": "transcription.done",
                "model": "voxtral-mini-transcribe-realtime-2602",
                "text": "Guten Tag.",
                "language": None,
                "segments": [],
                "usage": {},
            }),
        ]
        port, handle, _ws = await self._open(incoming)

        events = [event async for event in port.events(handle)]

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].kind, "partial")
        self.assertEqual(events[0].speaker, "unknown")  # kein channel-Feld real
        self.assertEqual(events[1].kind, "final")
        self.assertEqual(events[1].text, "Guten Tag.")

    async def test_events_yields_final_from_segment_with_speaker_id(self) -> None:
        """`transcription.segment` ist laut Referenz-Schema real (text/start/end/speaker_id),
        in eigenen Probe-Läufen aber NIE beobachtet — hier defensiv abgesichert."""
        incoming = [
            _msg({"type": "transcription.segment", "text": "Hallo.", "start": 0.2, "end": 0.9, "speaker_id": "1"}),
        ]
        port, handle, _ws = await self._open(incoming)

        events = [event async for event in port.events(handle)]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "final")
        self.assertEqual(events[0].speaker, "speaker_1")
        self.assertEqual(events[0].t_start_ms, 200)
        self.assertEqual(events[0].t_end_ms, 900)

    async def test_missing_speaker_id_falls_back_to_unknown_speaker(self) -> None:
        incoming = [_msg({"type": "transcription.segment", "text": "Text", "start": 0.0, "end": 0.1})]
        port, handle, _ws = await self._open(incoming)

        events = [event async for event in port.events(handle)]
        self.assertEqual(events[0].speaker, "unknown")

    async def test_error_message_raises_live_stream_error(self) -> None:
        incoming = [_msg({"type": "error", "error": {"message": "Realtime kaputt", "code": 1}})]
        port, handle, _ws = await self._open(incoming)

        with self.assertRaises(VoxtralLiveStreamError):
            async for _event in port.events(handle):
                pass

    async def test_events_with_unknown_handle_raises(self) -> None:
        port, _handle, _ws = await self._open([])
        with self.assertRaises(VoxtralLiveStreamError):
            async for _event in port.events(StreamHandle(provider_handle="ghost", correlation_id="x")):
                pass

    async def test_events_publish_to_bus_when_configured(self) -> None:
        bus = InProcessTranscriptEventBus()
        websocket = _FakeWebSocket(
            [
                _msg(_SESSION_CREATED),
                _msg({
                    "type": "transcription.done",
                    "model": "voxtral-mini-transcribe-realtime-2602",
                    "text": "Hi",
                    "language": None,
                    "segments": [],
                    "usage": {},
                }),
            ]
        )

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect, event_bus=bus)
        handle = await port.open_stream(_session())

        received: list[BusEvent] = []

        async def consume() -> None:
            async for event in bus.subscribe("session-1"):
                received.append(event)

        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)

        async for _event in port.events(handle):
            pass
        await bus.close_session("session-1")
        await asyncio.wait_for(task, timeout=1)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, "transcript.final")
        # Verifizierte Lücke: ohne echtes channel-Feld ist der Sprecher nicht coach/counterpart
        # zuordenbar — der Bus bekommt ehrlich None statt eines erfundenen Sprechers.
        self.assertIsNone(received[0].payload.speaker)


class CloseStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_stream_returns_result_with_speakers_and_duration(self) -> None:
        incoming = [
            _msg(_SESSION_CREATED),
            _msg({"type": "transcription.segment", "text": "Hi", "start": 0.0, "end": 0.5, "speaker_id": "1"}),
            _msg({"type": "transcription.segment", "text": "Ho", "start": 0.5, "end": 1.2, "speaker_id": "2"}),
        ]
        websocket = _FakeWebSocket(incoming)

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        settings = default_settings()
        port = VoxtralApiTranscriptionPort(settings, ws_connect=ws_connect)
        handle = await port.open_stream(_session())

        async for _event in port.events(handle):
            pass

        result = await port.close_stream(handle)

        self.assertEqual(result.provider, "voxtral_api")
        self.assertEqual(result.model, settings.model_stt_live)
        self.assertEqual(result.duration_ms, 1200)
        self.assertEqual(set(result.speakers), {"speaker_1", "speaker_2"})
        # VERIFIZIERT: kein "session.end" — stattdessen input_audio.flush + input_audio.end
        # (das reale Protokoll kennt kein session.end).
        self.assertIn(json.dumps({"type": "input_audio.flush"}), websocket.sent)
        self.assertIn(json.dumps({"type": "input_audio.end"}), websocket.sent)
        self.assertTrue(websocket.closed)

    async def test_close_stream_without_segments_falls_back_to_unknown_speaker(self) -> None:
        websocket = _FakeWebSocket([_msg(_SESSION_CREATED)])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())

        result = await port.close_stream(handle)

        self.assertEqual(result.speakers, ["unknown"])
        self.assertEqual(result.duration_ms, 0)

    async def test_close_stream_suppresses_send_and_close_errors(self) -> None:
        websocket = _FakeWebSocket([_msg(_SESSION_CREATED)])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())

        websocket.send_raises = RuntimeError("Socket schon weg")
        websocket.close_raises = RuntimeError("Socket schon weg")

        result = await port.close_stream(handle)  # darf trotz Socket-Fehlern nicht werfen
        self.assertEqual(result.speakers, ["unknown"])


if __name__ == "__main__":
    unittest.main()
