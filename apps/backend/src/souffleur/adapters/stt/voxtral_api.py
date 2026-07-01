"""voxtral_api — Default-STT-Adapter über Mistral Voxtral (Batch Welle 4/Fix, Live Welle 12/Fix).

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

## Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`, Phase 2, Welle 12/Fix)

**VERIFIZIERT am echten Endpunkt (2026-07)** — nicht mehr nur eine Annahme. Das installierte
SDK (1.10.0) hat kein `audio.realtime`-Modul (auch nicht in der neuesten auf PyPI verfügbaren
Version — geprüft, 1.10.0 ist LATEST); Live-Streaming geht daher über die `websockets`-
Bibliothek direkt gegen `wss://api.mistral.ai` (EU-Routing, Gate E1).

Das reale Roh-WS-Wireformat wurde in zwei Schritten ermittelt: (1) der `main`-Branch von
`mistralai/client-python` (GitHub, noch **nicht** auf PyPI released — `pip install
'mistralai[realtime]'` existiert dort als Extra, aber nicht in 1.10.0) enthält den vollständigen
Referenz-Client (`src/mistralai/extra/realtime/{connection,transcription}.py` +
`src/mistralai/client/models/realtimetranscription*.py`); (2) ein eigenständiges Probe-Skript
(nicht Teil dieses Repos) hat dieses Format gegen den ECHTEN `wss://api.mistral.ai`-Endpunkt
mit einem deutschen Test-Audio verifiziert — ein vollständiges, korrektes deutsches Transkript
kam zurück ("Ich habe gerade ehrlich gesagt wenig Zeit, und das Budget ist bei uns sehr eng,
verstehe, was müsste sich denn ändern, damit Zeit und Budget für Sie kein Thema mehr wären.").

**Verifiziertes Wireformat (weicht in mehreren Punkten von der vorherigen Annahme ab):**

- URL: `wss://api.mistral.ai/v1/audio/transcriptions/realtime?model=<model>` — NUR `model`
  wirkt als Query-Parameter. `encoding`/`sample_rate`/`channels`/`target_streaming_delay_ms`
  in der Query werden vom Server stillschweigend IGNORIERT (kein Fehler, aber ohne Effekt —
  empirisch belegt: `session.created` liefert dann `target_streaming_delay_ms: null` und die
  Default-Werte für `audio_format`, egal was in der Query stand).
- Handshake: die ERSTE Server-Nachricht nach dem WS-Upgrade ist immer `{"type":
  "session.created", "session": {"request_id", "model", "audio_format", ...}}`. Erst danach
  darf der Client `{"type": "session.update", "session": {"audio_format": {...},
  "target_streaming_delay_ms": ...}}` senden, um das echte Audioformat zu setzen (VOR dem
  ersten Audio-Chunk — Updates danach werden laut Referenz-Client abgelehnt).
- Audio-Frames sind **JSON-Textnachrichten, NICHT raw binary** (Abweichung von der
  ursprünglichen Annahme!): `{"type": "input_audio.append", "audio": "<base64 pcm_s16le>"}`.
  Ein roher Binär-Frame wird vom Server kommentarlos ignoriert (empirisch belegt: keine
  Antwort, kein Fehler, keine Transkription). Laut Referenz-Client max. 262144 dekodierte
  Bytes pro `input_audio.append` (hier defensiv geprüft, siehe `_MAX_INPUT_AUDIO_APPEND_BYTES`).
- Session-Ende: `{"type": "input_audio.flush"}` gefolgt von `{"type": "input_audio.end"}` (KEIN
  `session.end`, das gibt es nicht). `input_audio.flush` ALLEIN (ohne `end`) erzwingt bereits
  ein `transcription.done` für das bisher Gesagte, OHNE die Verbindung zu schließen — das ist
  der Mechanismus für mehrere finale Segmente auf derselben Verbindung (z. B. an natürlichen
  Sprechpausen), empirisch bestätigt (zwei Sätze getrennt geflusht → zwei `transcription.done`,
  Verbindung blieb dazwischen offen und nahm weiteres Audio an).
- Server-Events (verifizierte Typnamen, komplett anders als ursprünglich angenommen):
  `session.created`, `session.updated`, `error` (Fehlerdetail unter `error.error.message`/
  `.code`, NICHT `error.message`), `transcription.language` (`audio_language`),
  `transcription.text.delta` (`text` — ein Wort-/Token-Fragment, KEIN kumulativer Text, siehe
  unten), `transcription.segment` (`text`/`start`/`end`/optional `speaker_id` — laut
  Referenz-Client-Schema real, aber in den eigenen Probe-Läufen NIE beobachtet; hier defensiv
  unterstützt, aber unverifiziert markiert), `transcription.done` (`text` = vollständiger,
  seit dem letzten `done`/Sessionstart akkumulierter Text — DAS ist der primäre, tatsächlich
  beobachtete Finalisierungsmechanismus, ausgelöst durch `input_audio.flush`/`input_audio.end`).
  Die Verbindung wird vom Server nach `transcription.done` abrupt mit Close-Code 1006
  geschlossen (kein sauberer Close-Frame) — empirisch beobachtet, hier über die bestehenden
  `contextlib.suppress(Exception)`-Guards in `close_stream` abgefangen.
- `transcription.text.delta`/`transcription.done` tragen KEINE Zeitstempel (kein `start_ms`/
  `end_ms`). Dieser Adapter zählt daher lokal die kumulierte Audiolänge der über `push_audio`
  gesendeten PCM-Bytes (`_LiveStreamState.pushed_audio_ms`) und stempelt `TranscriptEvent`s
  damit — ehrlich vom tatsächlich gesendeten Audio abgeleitet, nicht vom Server erfunden.

**Offene, ehrlich dokumentierte Lücke — Dual-Source/Kanaltrennung:** Die vorherige Annahme,
eine eingehende Server-Nachricht trage ein `channel`-Feld (0 = Mikrofon/Coach, 1 =
System-Audio/Gegenüber), ist VERIFIZIERT FALSCH — kein einziger der oben genannten
Event-Typen kennt ein `channel`-Feld, und `AudioFormat` kennt nur `encoding`/`sample_rate`,
KEIN `channels`-Feld. Das reale Realtime-Protokoll ist rein monaural pro Verbindung; es gibt
keinen serverseitigen Mechanismus, zwei Audioquellen über EINE WS-Verbindung getrennt zu
transkribieren. Echte Dual-Source-Unterstützung (Mikrofon=Coach getrennt von
System-Audio=Gegenüber) würde ZWEI unabhängige Realtime-Verbindungen erfordern (eine pro
Quelle) — das würde eine Änderung der `TranscriptionPort.push_audio`-Signatur nötig machen
(sie kennt aktuell keinen Quellen-/Kanalparameter, siehe `adapters/capture/dual_source.py`),
was außerhalb des Scopes dieses Fixes liegt (Port-Signatur bewusst unberührt gelassen). Bis
diese Architekturentscheidung getroffen ist: `SessionContext.channels` wird für die
Live-Verbindung NICHT mehr an den Server übertragen (wirkungslos, siehe oben) und
Live-Transkript-Events tragen ehrlich `speaker = "unknown"` (Fallback), AUSSER ein
`transcription.segment`-Event liefert ein reales `speaker_id`-Feld (dann wird — analog zum
Batch-Pfad — `speaker_<id>` daraus abgeleitet). Der Bus-Publish-Pfad (`_publish_transcript_bus_event`)
mappt nur `"coach"`/`"counterpart"` auf ein sichtbares `payload.speaker`; alles andere
(aktuell praktisch immer) wird ehrlich als `None` weitergereicht statt einen Sprecher zu
erfinden.

Tests mocken die WS-Verbindung vollständig (kein echter Netzaufruf, Gate E1/E2) — das echte
Wireformat oben wurde einmalig gegen den echten Endpunkt mit einem eigenständigen, nicht im
Repo enthaltenen Probe-Skript verifiziert (kein API-Key im Repo, keine echten Calls in CI).
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import websockets

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

# Deutscher Coaching-Kontext (context_bias) — verbessert die Erkennung typischer
# Coaching-/Sales-Fachbegriffe. Überschreibbar via BatchOptions.context_bias.
_DEFAULT_CONTEXT_BIAS_DE = (
    "Coaching,Einwand,Budget,Zeitdruck,Skalenfrage,Wunderfrage,Ressource,"
    "Zielvereinbarung,Reframing,GROW,systemisch,Perspektivwechsel"
)

# Explizites Timeout für den Batch-REST-Call (Gate D1/SAST B113: kein httpx-Client ohne
# Timeout) — Diarisation langer Aufnahmen darf dauern, aber nicht unbegrenzt blockieren.
_BATCH_HTTP_TIMEOUT_SECONDS = 60.0

# VERIFIZIERTER Roh-WS-Nachrichtenkontrakt (2026-07, siehe Modul-Docstring "Live-Streaming").
# Server -> Client:
_MSG_TYPE_SESSION_CREATED = "session.created"
_MSG_TYPE_SESSION_UPDATED = "session.updated"
_MSG_TYPE_ERROR = "error"
_MSG_TYPE_LANGUAGE = "transcription.language"
_MSG_TYPE_SEGMENT = "transcription.segment"  # unverifiziert live, aber reales Schema
_MSG_TYPE_TEXT_DELTA = "transcription.text.delta"
_MSG_TYPE_DONE = "transcription.done"
# Client -> Server:
_CLIENT_MSG_SESSION_UPDATE = "session.update"
_CLIENT_MSG_INPUT_AUDIO_APPEND = "input_audio.append"
_CLIENT_MSG_INPUT_AUDIO_FLUSH = "input_audio.flush"
_CLIENT_MSG_INPUT_AUDIO_END = "input_audio.end"

# Verifiziertes Server-Limit: max. dekodierte Bytes pro input_audio.append-Nachricht.
_MAX_INPUT_AUDIO_APPEND_BYTES = 262144


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
    # Lokale Audio-Uhr (Millisekunden seit Sessionstart) — der Server liefert für
    # transcription.text.delta/transcription.done KEINE Zeitstempel (verifiziert), daher wird
    # hier ehrlich aus der tatsächlich gesendeten PCM-Menge gerechnet statt etwas zu erfinden.
    pushed_audio_ms: int = 0
    finalized_audio_ms: int = 0


class VoxtralApiTranscriptionPort:
    """Default-STT-Adapter (`SOUFFLEUR_STT_PROVIDER=voxtral_api`) — Batch (Fix) + Live (W12/Fix)."""

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

    # --- Phase 2 — Live-Streaming (Welle 12, VERIFIZIERT 2026-07) ------------------

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
        state = _LiveStreamState(websocket=websocket, session=session, correlation_id=correlation_id)
        self._streams[handle.provider_handle] = state

        try:
            await self._complete_handshake(state)
        except Exception:
            del self._streams[handle.provider_handle]
            with contextlib.suppress(Exception):
                await websocket.close()
            raise

        return handle

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        state = self._require_stream(handle)
        if len(pcm_chunk) > _MAX_INPUT_AUDIO_APPEND_BYTES:
            raise VoxtralLiveStreamError(
                f"PCM-Chunk zu groß ({len(pcm_chunk)} Bytes) — Realtime-API erlaubt max. "
                f"{_MAX_INPUT_AUDIO_APPEND_BYTES} dekodierte Bytes pro input_audio.append"
            )
        # VERIFIZIERT: Audio geht als base64-JSON-Textnachricht, NICHT als roher Binär-Frame
        # (ein roher Binär-Frame wird vom Server kommentarlos ignoriert — keine Antwort, keine
        # Transkription, kein Fehler).
        append_message = {
            "type": _CLIENT_MSG_INPUT_AUDIO_APPEND,
            "audio": base64.b64encode(pcm_chunk).decode("ascii"),
        }
        try:
            await state.websocket.send(json.dumps(append_message))
        except Exception as exc:  # noqa: BLE001 - in VoxtralLiveStreamError übersetzt
            raise VoxtralLiveStreamError(f"input_audio.append fehlgeschlagen: {exc}") from exc
        state.pushed_audio_ms += self._pcm_duration_ms(pcm_chunk, state.session.sample_rate)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        state = self._require_stream(handle)
        async for raw in state.websocket:
            if isinstance(raw, bytes):
                continue  # nur JSON-Textnachrichten werden geparst
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == _MSG_TYPE_ERROR:
                raise VoxtralLiveStreamError(self._extract_error_message(message))
            if msg_type in (_MSG_TYPE_SESSION_CREATED, _MSG_TYPE_SESSION_UPDATED, _MSG_TYPE_LANGUAGE):
                continue  # Session-Lifecycle/Sprachmetadaten — kein TranscriptEvent

            if msg_type == _MSG_TYPE_TEXT_DELTA:
                event = self._partial_event_from_delta(state, message)
            elif msg_type == _MSG_TYPE_SEGMENT:
                event = self._final_event_from_segment(message)
            elif msg_type == _MSG_TYPE_DONE:
                event = self._final_event_from_done(state, message)
            else:
                continue  # unbekannter/zukünftiger Event-Typ — forward-compat, kein Hard-Fail

            if event.speaker not in state.speakers:
                state.speakers.append(event.speaker)
            if event.kind == "final":
                state.segments.append(event)
            if self._event_bus is not None:
                await self._publish_transcript_bus_event(state, event)
            yield event

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        state = self._streams.pop(handle.provider_handle)
        # VERIFIZIERT: kein "session.end" — stattdessen flush (erzwingt ein finales
        # transcription.done für den Rest) gefolgt von end (beendet den Audio-Input). Der
        # Server schließt danach abrupt mit Close-Code 1006 (kein sauberer Close-Frame) —
        # deshalb bleiben alle drei Schritte defensiv `contextlib.suppress`-geschützt.
        with contextlib.suppress(Exception):
            await state.websocket.send(json.dumps({"type": _CLIENT_MSG_INPUT_AUDIO_FLUSH}))
        with contextlib.suppress(Exception):
            await state.websocket.send(json.dumps({"type": _CLIENT_MSG_INPUT_AUDIO_END}))
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
        # VERIFIZIERT (2026-07, echter Probe-Lauf): NUR `model` wirkt als Query-Parameter.
        # encoding/sample_rate/target_streaming_delay_ms werden vom Server ignoriert, wenn sie
        # hier angehängt werden — sie müssen per session.update NACH session.created gesetzt
        # werden (siehe `_complete_handshake`). `channels` existiert im Wireformat gar nicht
        # (siehe Moduldokstring "Offene, ehrlich dokumentierte Lücke").
        return f"{ws_base}{LIVE_WS_PATH}?model={self._settings.model_stt_live}"

    async def _complete_handshake(self, state: _LiveStreamState) -> None:
        """Wartet auf `session.created` (VERIFIZIERT: erste Server-Nachricht nach Connect) und
        sendet danach `session.update`, um `audio_format`/`target_streaming_delay_ms` explizit
        zu setzen — spiegelt `mistralai/client-python` (main-Branch,
        `extra/realtime/transcription.py::_recv_handshake`)."""
        raw = await self._recv_one(state.websocket)
        message = self._parse_message(raw)
        if message.get("type") == _MSG_TYPE_ERROR:
            raise VoxtralLiveStreamError(self._extract_error_message(message))
        if message.get("type") != _MSG_TYPE_SESSION_CREATED:
            raise VoxtralLiveStreamError(
                f"Unerwartete erste Realtime-Nachricht (erwartet {_MSG_TYPE_SESSION_CREATED}): "
                f"{message!r}"
            )

        update_message = {
            "type": _CLIENT_MSG_SESSION_UPDATE,
            "session": {
                "audio_format": {
                    "encoding": LIVE_AUDIO_ENCODING,
                    "sample_rate": state.session.sample_rate,
                },
                "target_streaming_delay_ms": TARGET_STREAMING_DELAY_MS,
            },
        }
        try:
            await state.websocket.send(json.dumps(update_message))
        except Exception as exc:  # noqa: BLE001 - in VoxtralLiveStreamError übersetzt
            raise VoxtralLiveStreamError(f"session.update fehlgeschlagen: {exc}") from exc

    @staticmethod
    async def _recv_one(websocket: _WsConnection) -> Any:
        try:
            return await websocket.__aiter__().__anext__()
        except StopAsyncIteration as exc:
            raise VoxtralLiveStreamError(
                "Realtime-Verbindung endete vor session.created (kein Handshake-Empfang)"
            ) from exc
        except VoxtralLiveStreamError:
            raise
        except Exception as exc:  # noqa: BLE001 - in VoxtralLiveStreamError übersetzt
            raise VoxtralLiveStreamError(f"Handshake-Empfang fehlgeschlagen: {exc}") from exc

    @staticmethod
    def _parse_message(raw: Any) -> dict[str, Any]:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise VoxtralLiveStreamError(f"Unerwartetes Nachrichtenformat (kein JSON-Objekt): {raw!r}")
        return parsed

    @staticmethod
    def _pcm_duration_ms(pcm_chunk: bytes, sample_rate: int) -> int:
        """pcm_s16le mono: 2 Bytes/Sample. Dual-Source (2 Kanäle) wird auf dem realen
        Live-Wireformat aktuell nicht unterstützt (siehe Moduldokstring) — hier zählt jeder
        Chunk als Mono-Sample-Block."""
        if sample_rate <= 0:
            return 0
        samples = len(pcm_chunk) // 2
        return round(samples / sample_rate * 1000)

    def _require_stream(self, handle: StreamHandle) -> _LiveStreamState:
        state = self._streams.get(handle.provider_handle)
        if state is None:
            raise VoxtralLiveStreamError(
                f"Unbekanntes oder bereits geschlossenes Stream-Handle: {handle.provider_handle!r}"
            )
        return state

    @staticmethod
    def _extract_error_message(message: dict[str, Any]) -> str:
        """`error`-Event-Form ist verifiziert `{"type":"error","error":{"message","code"}}` —
        `message` selbst kann laut Referenz-Schema String ODER Objekt sein (defensiv behandelt)."""
        error = message.get("error")
        if isinstance(error, dict):
            detail = error.get("message")
            if isinstance(detail, str):
                return detail
            if detail is not None:
                return json.dumps(detail, ensure_ascii=False)
        return "unbekannter Realtime-Fehler"

    def _partial_event_from_delta(
        self, state: _LiveStreamState, message: dict[str, Any]
    ) -> TranscriptEvent:
        """`transcription.text.delta` trägt nur ein Text-Fragment (Wort/Token), KEINE
        Zeitstempel — Zeit wird lokal aus der bisher gesendeten Audiolänge abgeleitet."""
        return TranscriptEvent(
            kind="partial",
            speaker=_FALLBACK_SPEAKER,
            text=message.get("text", "") or "",
            t_start_ms=state.finalized_audio_ms,
            t_end_ms=state.pushed_audio_ms,
        )

    def _final_event_from_segment(self, message: dict[str, Any]) -> TranscriptEvent:
        """`transcription.segment` — laut Referenz-Schema real (`text`/`start`/`end`/optional
        `speaker_id`), in eigenen Probe-Läufen aber NIE beobachtet (unverifiziert live,
        defensiv unterstützt für einen Fall, in dem der Server sie doch sendet)."""
        speaker = self._extract_speaker_label(message)
        return TranscriptEvent(
            kind="final",
            speaker=speaker,
            text=message.get("text", "") or "",
            t_start_ms=self._seconds_to_ms(message.get("start", 0.0)),
            t_end_ms=self._seconds_to_ms(message.get("end", 0.0)),
        )

    def _final_event_from_done(self, state: _LiveStreamState, message: dict[str, Any]) -> TranscriptEvent:
        """`transcription.done` — VERIFIZIERT der tatsächlich beobachtete Finalisierungspfad,
        ausgelöst durch `input_audio.flush`/`input_audio.end`. Trägt den vollständigen Text seit
        dem letzten `done` (oder Sessionstart), aber KEINE Zeitstempel — Zeit wird aus der
        lokalen Audio-Uhr übernommen."""
        t_start_ms = state.finalized_audio_ms
        t_end_ms = state.pushed_audio_ms
        state.finalized_audio_ms = t_end_ms
        return TranscriptEvent(
            kind="final",
            speaker=_FALLBACK_SPEAKER,
            text=message.get("text", "") or "",
            t_start_ms=t_start_ms,
            t_end_ms=t_end_ms,
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
        """Baut die multipart-Formularfelder — LIVE verifizierte REST-Parameter.

        `context_bias` (bis 100 kommagetrennte Begriffe) ist am echten Endpunkt verifiziert
        (HTTP 200) und verbessert die Erkennung von Coaching-Fachbegriffen. Override via
        `BatchOptions.context_bias`; sonst greift der deutsche Coaching-Default. `language`
        wird bewusst NICHT gesendet (führt hier zu HTTP 422)."""
        fields: dict[str, Any] = {"model": self._settings.model_stt_batch}
        if opts.diarization:
            fields["diarize"] = "true"
        bias = opts.context_bias or _DEFAULT_CONTEXT_BIAS_DE
        if bias:
            fields["context_bias"] = bias
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
        """Sprecher-Label aus dem verifizierten `speaker_id`-Feld (int|None) — kein Fake-Sprecher.
        Wird sowohl vom Batch-Pfad (`segments[].speaker_id`) als auch defensiv vom Live-Pfad
        (`transcription.segment.speaker_id`) verwendet — dieselbe Konvention, einzige Quelle."""
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
