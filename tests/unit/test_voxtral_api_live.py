"""Unit-Tests adapters/stt/voxtral_api.py — Live-Streaming (`open_stream`/`push_audio`/

`events`/`close_stream`), Roh-WS vollständig gemockt (kein echter Netzaufruf).
"""
from __future__ import annotations

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


class _FakeWebSocket:
    def __init__(self, incoming: list[Any]) -> None:
        self.incoming = list(incoming)
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

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for item in self.incoming:
            yield item


def _session() -> SessionContext:
    return SessionContext(
        tenant_id="zukunftsbund", session_id="session-1", consent_ref="c1", sample_rate=16000, channels=2
    )


class OpenStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_ws_url_with_query_params_and_bearer_header(self) -> None:
        captured: dict[str, Any] = {}

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            captured["url"] = url
            captured["headers"] = additional_headers
            return _FakeWebSocket([])

        settings = default_settings(mistral_api_key="secret-key")
        port = VoxtralApiTranscriptionPort(settings, ws_connect=ws_connect)

        handle = await port.open_stream(_session())

        self.assertTrue(captured["url"].startswith("wss://api.mistral.ai/v1/audio/transcriptions/realtime"))
        self.assertIn(f"model={settings.model_stt_live}", captured["url"])
        self.assertIn("channels=2", captured["url"])
        self.assertEqual(captured["headers"], {"Authorization": "Bearer secret-key"})
        self.assertEqual(handle.provider_handle, handle.correlation_id)

    async def test_connection_failure_is_translated_to_live_stream_error(self) -> None:
        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            raise RuntimeError("Verbindung abgelehnt")

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)

        with self.assertRaises(VoxtralLiveStreamError):
            await port.open_stream(_session())


class PushAudioAndEventsTest(unittest.IsolatedAsyncioTestCase):
    async def _open(self, incoming: list[Any]) -> tuple[VoxtralApiTranscriptionPort, StreamHandle, _FakeWebSocket]:
        websocket = _FakeWebSocket(incoming)

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())
        return port, handle, websocket

    async def test_push_audio_sends_pcm_chunk_over_the_socket(self) -> None:
        port, handle, websocket = await self._open([])
        await port.push_audio(handle, b"\x00\x01\x02")
        self.assertEqual(websocket.sent, [b"\x00\x01\x02"])

    async def test_push_audio_with_unknown_handle_raises(self) -> None:
        port, _handle, _ws = await self._open([])
        with self.assertRaises(VoxtralLiveStreamError):
            await port.push_audio(StreamHandle(provider_handle="ghost", correlation_id="x"), b"\x00")

    async def test_events_yields_partial_and_final_with_channel_speaker_mapping(self) -> None:
        incoming = [
            b"\x00\x01",  # binäre Nachricht -> wird ignoriert
            json.dumps({"type": "session.created"}),  # unbekannter Typ -> ignoriert
            json.dumps({"type": "transcript.delta", "channel": 0, "text": "Guten ", "start_ms": 0, "end_ms": 200}),
            json.dumps(
                {"type": "transcript.completed", "channel": 1, "text": "Hallo.", "start_ms": 200, "end_ms": 900}
            ),
        ]
        port, handle, _ws = await self._open(incoming)

        events = [event async for event in port.events(handle)]

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].kind, "partial")
        self.assertEqual(events[0].speaker, "coach")  # Kanal 0
        self.assertEqual(events[1].kind, "final")
        self.assertEqual(events[1].speaker, "counterpart")  # Kanal 1

    async def test_missing_channel_falls_back_to_unknown_speaker(self) -> None:
        incoming = [json.dumps({"type": "transcript.completed", "text": "Text", "start_ms": 0, "end_ms": 100})]
        port, handle, _ws = await self._open(incoming)

        events = [event async for event in port.events(handle)]
        self.assertEqual(events[0].speaker, "unknown")

    async def test_error_message_raises_live_stream_error(self) -> None:
        incoming = [json.dumps({"type": "error", "message": "Realtime kaputt"})]
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
            [json.dumps({"type": "transcript.completed", "channel": 0, "text": "Hi", "start_ms": 0, "end_ms": 100})]
        )

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect, event_bus=bus)
        handle = await port.open_stream(_session())

        received: list[BusEvent] = []

        import asyncio

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
        self.assertEqual(received[0].payload.speaker, "coach")


class CloseStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_stream_returns_result_with_speakers_and_duration(self) -> None:
        incoming = [
            json.dumps({"type": "transcript.completed", "channel": 0, "text": "Hi", "start_ms": 0, "end_ms": 500}),
            json.dumps(
                {"type": "transcript.completed", "channel": 1, "text": "Ho", "start_ms": 500, "end_ms": 1200}
            ),
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
        self.assertEqual(set(result.speakers), {"coach", "counterpart"})
        self.assertIn(json.dumps({"type": "session.end"}), websocket.sent)
        self.assertTrue(websocket.closed)

    async def test_close_stream_without_segments_falls_back_to_unknown_speaker(self) -> None:
        websocket = _FakeWebSocket([])

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())

        result = await port.close_stream(handle)

        self.assertEqual(result.speakers, ["unknown"])
        self.assertEqual(result.duration_ms, 0)

    async def test_close_stream_suppresses_send_and_close_errors(self) -> None:
        websocket = _FakeWebSocket([])
        websocket.send_raises = RuntimeError("Socket schon weg")
        websocket.close_raises = RuntimeError("Socket schon weg")

        async def ws_connect(url: str, additional_headers: dict) -> _FakeWebSocket:
            return websocket

        port = VoxtralApiTranscriptionPort(default_settings(), ws_connect=ws_connect)
        handle = await port.open_stream(_session())

        result = await port.close_stream(handle)  # darf trotz Socket-Fehlern nicht werfen
        self.assertEqual(result.speakers, ["unknown"])


if __name__ == "__main__":
    unittest.main()
