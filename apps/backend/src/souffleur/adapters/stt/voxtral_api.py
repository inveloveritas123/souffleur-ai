"""voxtral_api — Default-STT-Adapter über Mistral Voxtral (Batch Welle 4/Fix, Live Welle 12).

## Batch (`transcribe_batch`, Phase 1) — REST statt SDK (Diarisations-Fix)

Verifiziert am echten Endpunkt (2026-07, Key HTTP 200, siehe
`MISTRAL-API-CHEATSHEET.md`): das installierte `mistralai==1.10.0` SDK akzeptiert **kein**
`diarize`-Kwarg auf `audio.transcriptions.complete_async` — der REST-Endpunkt
`POST /v1/audio/transcriptions` akzeptiert `diarize=true` jedoch sehr wohl. Deshalb ruft
`transcribe_batch` diesen Endpunkt direkt über `httpx` auf (kein Mistral-SDK-Client mehr in
diesem Adapter). Verifizierte Response-Form:
```json
{"model": "...", "text": "...", "language": "de",
 "usage": {...},
 "segments": [{"text": "...", "start": <sec float>, "end": <sec float>,
               "speaker_id": <int|null>, "type": "..."}]}
```
Sprecher-Label-Feld ist `speaker_id` (int, NICHT `speaker`); `start`/`end` sind Sekunden
(float), werden hier nach Millisekunden gewandelt. Ein fehlendes `speaker_id` erzeugt
**keinen** fabrizierten Sprecher — stattdessen den ehrlichen Fallback `"unknown"` (kein
Fake-Sprecherwechsel, siehe Direktive "keine Fake-Sprecher erfinden"). Wort-Zeitstempel
(`words` pro Segment) sind in der verifizierten Response-Form nicht dokumentiert; sie werden
dennoch defensiv geparst, falls ein zukünftiger API-Stand sie liefert — ohne Codeänderung.

## Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`, Phase 2, Welle 12)

Das installierte SDK (1.10.0) hat **kein** `audio.realtime`-Modul — Live-Streaming geht daher
über die `websockets`-Bibliothek direkt gegen `wss://api.mistral.ai` (EU-Routing, Gate E1).

**Abweichung/Annahme (dokumentiert):** Das exakte Roh-WS-JSON-Wireformat von Mistral
Realtime ist NICHT Teil des verifizierten Cheatsheets (dort ist nur die SDK-seitige
`async for event in audio.realtime.transcribe_stream(...)`-Semantik mit Eventnamen wie
`RealtimeTranscriptionSessionCreated`/`TranscriptionStreamTextDelta`/`TranscriptionStreamDone`
verifiziert). Dieser Adapter definiert daher ein eigenes, dokumentiertes JSON-Kontraktformat
für die Roh-WS-Verbindung (`_MSG_TYPE_*`-Konstanten unten), das sich eng an diese verifizierten
SDK-Eventnamen anlehnt. Sollte das reale Wireformat abweichen, ist nur `_to_transcript_event`/
das Nachrichtenparsing hier anzupassen — Port-Signatur und Bus-Anbindung bleiben unberührt.
Tests mocken die WS-Verbindung vollständig (kein echter Netzaufruf, Gate E1/E2).

Dual-Source (ARCHITECTURE.md "Daten- und Latenzfluss", Welle 12-Entscheid): `SessionContext.
channels == 2` kennzeichnet eine Dual-Source-Session (System-Audio = Gegenüber, Mikrofon =
Coach). Trägt eine eingehende Server-Nachricht ein `channel`-Feld (0 = Mikrofon/Coach,
1 = System-Audio/Gegenüber), wird das Sprecher-Label daraus abgeleitet (siehe
`adapters/capture/dual_source.py` für die kanonische Kanal->Sprecher-Zuordnung); fehlt das
Feld (Mono-Session), wird der ehrliche Fallback `"unknown"` verwendet.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import websockets

from souffleur.adapters.capture.dual_source import CHANNEL_TO_SPEAKER
from souffleur.bus import BusEvent, BusEventPayload, TranscriptEventBus, now_ms
from souffleur.core.settings import Settings
from souffleur.ports.types import (
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    SessionContext,
    StreamHandle,
    TranscriptEvent,
    TranscriptResult,
    Word,
)

REST_TRANSCRIPTIONS_PATH = "/v1/audio/transcriptions"
LIVE_WS_PATH = "/v1/audio/transcriptions/realtime"
LIVE_AUDIO_ENCODING = "pcm_s16le"
TARGET_STREAMING_DELAY_MS = 480

_FALLBACK_SPEAKER = "unknown"

# Explizites Timeout für den Batch-REST-Call (Gate D1/SAST B113: kein httpx-Client ohne
# Timeout) — Diarisation langer Aufnahmen darf dauern, aber nicht unbegrenzt blockieren.
_BATCH_HTTP_TIMEOUT_SECONDS = 60.0

# Dokumentiertes Roh-WS-Nachrichtenkontrakt dieses Adapters (siehe Modul-Docstring "Abweichung").
_MSG_TYPE_SESSION_CREATED = "session.created"
_MSG_TYPE_TRANSCRIPT_DELTA = "transcript.delta"  # partial
_MSG_TYPE_TRANSCRIPT_COMPLETED = "transcript.completed"  # final
_MSG_TYPE_SESSION_END = "session.end"
_MSG_TYPE_ERROR = "error"


class VoxtralBatchTranscriptionError(RuntimeError):
    """Die Batch-Transkription über voxtral-mini-2602 (REST) ist fehlgeschlagen."""


class VoxtralLiveStreamError(RuntimeError):
    """Der Live-Stream über voxtral-mini-transcribe-realtime-2602 ist fehlgeschlagen."""


# `websockets.connect` liefert typisiert ein Async-Context-Manager/Coroutine — hier nur die
# Teilmenge modelliert, die dieser Adapter tatsächlich nutzt (send/close/async-iterierbar).
class _WsConnection(Protocol):
    async def send(self, message: Any) -> None: ...

    async def close(self) -> None: ...

    def __aiter__(self) -> AsyncIterator[Any]: ...


WsConnectFn = Callable[..., Awaitable[_WsConnection]]


@dataclass
class _LiveStreamState:
    websocket: _WsConnection
    session: SessionContext
    correlation_id: str
    segments: list[TranscriptEvent] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    seq: int = 0


class VoxtralApiTranscriptionPort:
    """Default-STT-Adapter (`SOUFFLEUR_STT_PROVIDER=voxtral_api`) — Batch (Fix) + Live (W12)."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
        event_bus: TranscriptEventBus | None = None,
        ws_connect: WsConnectFn | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._event_bus = event_bus
        self._ws_connect: WsConnectFn = ws_connect or websockets.connect  # type: ignore[assignment]
        self._streams: dict[str, _LiveStreamState] = {}

    # --- Phase 2 — Live-Streaming (Welle 12) --------------------------------------

    async def open_stream(self, session: SessionContext) -> StreamHandle:
        ws_url = self._live_ws_url(session)
        headers = {"Authorization": f"Bearer {self._settings.mistral_api_key}"}
        try:
            websocket = await self._ws_connect(ws_url, additional_headers=headers)
        except Exception as exc:  # noqa: BLE001 - in VoxtralLiveStreamError übersetzt
            raise VoxtralLiveStreamError(
                f"voxtral-mini-transcribe-realtime-2602 Verbindungsaufbau fehlgeschlagen: {exc}"
            ) from exc

        correlation_id = str(uuid.uuid4())
        handle = StreamHandle(provider_handle=correlation_id, correlation_id=correlation_id)
        self._streams[handle.provider_handle] = _LiveStreamState(
            websocket=websocket, session=session, correlation_id=correlation_id
        )
        return handle

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        state = self._require_stream(handle)
        await state.websocket.send(pcm_chunk)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        state = self._require_stream(handle)
        async for raw in state.websocket:
            if isinstance(raw, bytes):
                continue  # nur JSON-Textnachrichten werden geparst
            message = json.loads(raw)
            msg_type = message.get("type")
            if msg_type == _MSG_TYPE_ERROR:
                raise VoxtralLiveStreamError(message.get("message", "unbekannter Realtime-Fehler"))
            if msg_type not in (_MSG_TYPE_TRANSCRIPT_DELTA, _MSG_TYPE_TRANSCRIPT_COMPLETED):
                continue  # z. B. session.created — kein TranscriptEvent

            event = self._to_transcript_event(message, final=(msg_type == _MSG_TYPE_TRANSCRIPT_COMPLETED))
            if event.speaker not in state.speakers:
                state.speakers.append(event.speaker)
            if event.kind == "final":
                state.segments.append(event)
            if self._event_bus is not None:
                await self._publish_transcript_bus_event(state, event)
            yield event

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        state = self._streams.pop(handle.provider_handle)
        with contextlib.suppress(Exception):
            await state.websocket.send(json.dumps({"type": _MSG_TYPE_SESSION_END}))
        with contextlib.suppress(Exception):
            await state.websocket.close()

        speakers = state.speakers or [_FALLBACK_SPEAKER]
        duration_ms = state.segments[-1].t_end_ms if state.segments else 0
        return TranscriptResult(
            segments=state.segments,
            speakers=speakers,
            duration_ms=duration_ms,
            model=self._settings.model_stt_live,
            provider="voxtral_api",
        )

    # --- Phase 1 — Batch (Diarisation + Wort-Zeitstempel, REST-Fix) ----------------

    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        if not audio.local_path:
            raise ValueError(
                "voxtral_api.transcribe_batch benötigt AudioRef.local_path (Batch-Datei)"
            )

        # Finding 13 (Sync-Read auf async Pfad): ein direkter `open(...).read()` hier würde den
        # Event-Loop-Thread für die Dauer des Datei-I/O blockieren (andere Coroutinen/Sessions
        # der App stehen währenddessen still). `asyncio.to_thread` lagert den blockierenden Read
        # in einen Worker-Thread aus.
        content = await asyncio.to_thread(self._read_audio_file, audio.local_path)
        file_name = os.path.basename(audio.local_path)

        url = f"{self._settings.mistral_base_url}{REST_TRANSCRIPTIONS_PATH}"
        headers = {"Authorization": f"Bearer {self._settings.mistral_api_key}"}
        data = self._build_form_fields(opts)
        files = {"file": (file_name, content)}

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=_BATCH_HTTP_TIMEOUT_SECONDS)
        try:
            response = await client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - in VoxtralBatchTranscriptionError übersetzt
            raise VoxtralBatchTranscriptionError(
                f"voxtral-mini-2602 Batch-Transkription (REST, diarize) fehlgeschlagen: {exc}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        return self._parse_rest_response(payload)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_diarization=True,
            # LIVE verifiziert: voxtral-mini-2602 liefert für Batch nur Segment-Ebene,
            # keine Wort-Zeitstempel (timestamp_granularities[]=word -> HTTP 422).
            supports_word_timestamps=False,
            typical_final_latency_ms=300,
            residency="EU",
        )

    @staticmethod
    def _read_audio_file(local_path: str) -> bytes:
        """Blockierender Datei-Read — wird über `asyncio.to_thread` aufgerufen (Finding 13),
        nie direkt im Event-Loop-Thread."""
        with open(local_path, "rb") as handle:
            return handle.read()

    # --- Interna: Live-Streaming ----------------------------------------------------

    def _live_ws_url(self, session: SessionContext) -> str:
        ws_base = self._settings.mistral_base_url.replace("https://", "wss://").replace(
            "http://", "ws://"
        )
        return (
            f"{ws_base}{LIVE_WS_PATH}"
            f"?model={self._settings.model_stt_live}"
            f"&encoding={LIVE_AUDIO_ENCODING}"
            f"&sample_rate={session.sample_rate}"
            f"&channels={session.channels}"
            f"&target_streaming_delay_ms={TARGET_STREAMING_DELAY_MS}"
        )

    def _require_stream(self, handle: StreamHandle) -> _LiveStreamState:
        state = self._streams.get(handle.provider_handle)
        if state is None:
            raise VoxtralLiveStreamError(
                f"Unbekanntes oder bereits geschlossenes Stream-Handle: {handle.provider_handle!r}"
            )
        return state

    @staticmethod
    def _to_transcript_event(message: dict[str, Any], final: bool) -> TranscriptEvent:
        channel = message.get("channel")
        speaker = CHANNEL_TO_SPEAKER.get(channel, _FALLBACK_SPEAKER)
        return TranscriptEvent(
            kind="final" if final else "partial",
            speaker=speaker,
            text=message.get("text", "") or "",
            t_start_ms=int(message.get("start_ms", 0) or 0),
            t_end_ms=int(message.get("end_ms", 0) or 0),
        )

    async def _publish_transcript_bus_event(self, state: _LiveStreamState, event: TranscriptEvent) -> None:
        assert self._event_bus is not None
        state.seq += 1
        bus_speaker = event.speaker if event.speaker in ("coach", "counterpart") else None
        bus_event = BusEvent(
            type="transcript.final" if event.kind == "final" else "transcript.partial",
            session_id=state.session.session_id,
            tenant_id=state.session.tenant_id,
            seq=state.seq,
            ts_ms=now_ms(),
            payload=BusEventPayload(
                speaker=bus_speaker,
                text=event.text,
                t_start_ms=event.t_start_ms,
                t_end_ms=event.t_end_ms,
            ),
            correlation_id=state.correlation_id,
        )
        await self._event_bus.publish(state.session.session_id, bus_event)

    # --- Interna: Batch/REST ---------------------------------------------------------

    def _build_form_fields(self, opts: BatchOptions) -> dict[str, Any]:
        """Baut die multipart-Formularfelder — nur verifizierte REST-Parameter (kein context_bias)."""
        fields: dict[str, Any] = {"model": self._settings.model_stt_batch}
        if opts.diarization:
            fields["diarize"] = "true"
        if opts.language:
            # Verifiziert: timestamp_granularities ist NICHT kompatibel mit language.
            fields["language"] = opts.language
        else:
            # LIVE verifiziert (2026-07): der Endpunkt akzeptiert für voxtral-mini-2602 nur
            # timestamp_granularities[]=segment. "word" -> HTTP 422. Daher KEINE Wort-Ebene
            # anfragen (word_timestamps wird bewusst ignoriert; capabilities meldet dies ehrlich).
            fields["timestamp_granularities[]"] = ["segment"]
        return fields

    def _parse_rest_response(self, payload: dict[str, Any]) -> TranscriptResult:
        raw_segments = payload.get("segments") or []
        events: list[TranscriptEvent] = []
        speakers: list[str] = []

        for raw_segment in raw_segments:
            speaker = self._extract_speaker_label(raw_segment)
            if speaker not in speakers:
                speakers.append(speaker)
            words = self._extract_words(raw_segment.get("words"))
            events.append(
                TranscriptEvent(
                    kind="final",
                    speaker=speaker,
                    text=raw_segment.get("text", "") or "",
                    t_start_ms=self._seconds_to_ms(raw_segment.get("start", 0.0)),
                    t_end_ms=self._seconds_to_ms(raw_segment.get("end", 0.0)),
                    words=words,
                )
            )

        if not speakers:
            speakers = [_FALLBACK_SPEAKER]

        duration_ms = self._extract_duration_ms(payload, raw_segments)

        return TranscriptResult(
            segments=events,
            speakers=speakers,
            duration_ms=duration_ms,
            model=payload.get("model") or self._settings.model_stt_batch,
            provider="voxtral_api",
        )

    @staticmethod
    def _extract_speaker_label(segment: dict[str, Any]) -> str:
        """Sprecher-Label aus dem verifizierten `speaker_id`-Feld (int|None) — kein Fake-Sprecher."""
        speaker_id = segment.get("speaker_id")
        if speaker_id is None or speaker_id == "":
            return _FALLBACK_SPEAKER
        # LIVE verifiziert: der Endpunkt liefert speaker_id teils als String "speaker_1"
        # (nicht nur int). Kein Doppel-Präfix erzeugen.
        text = str(speaker_id)
        return text if text.startswith("speaker") else f"speaker_{text}"

    @classmethod
    def _extract_words(cls, raw_words: list[dict[str, Any]] | None) -> list[Word] | None:
        """Defensiv: `words` ist in der verifizierten Response-Form nicht dokumentiert."""
        if not raw_words:
            return None
        return [
            Word(
                text=raw_word.get("text", "") or "",
                t_start_ms=cls._seconds_to_ms(raw_word.get("start", 0.0)),
                t_end_ms=cls._seconds_to_ms(raw_word.get("end", 0.0)),
            )
            for raw_word in raw_words
        ]

    @staticmethod
    def _seconds_to_ms(value: Any) -> int:
        return round(float(value or 0.0) * 1000)

    @classmethod
    def _extract_duration_ms(
        cls, payload: dict[str, Any], raw_segments: list[dict[str, Any]]
    ) -> int:
        usage = payload.get("usage") or {}
        audio_seconds = usage.get("prompt_audio_seconds") or usage.get("audio_seconds")
        if audio_seconds:
            return cls._seconds_to_ms(audio_seconds)
        if raw_segments:
            return cls._seconds_to_ms(raw_segments[-1].get("end", 0.0))
        return 0
