"""voxtral_api — Default-STT-Adapter über Mistral Voxtral (Welle 4, Batch/Phase 1).

EU-Routing erzwungen (Gate E1): der `Mistral`-Client wird ausschließlich gegen
`settings.mistral_base_url` (gepinnt auf `https://api.mistral.ai`, siehe
`core/settings.py`) konstruiert. Modell gepinnt aus Settings (Gate F1): kein
`-latest`-Tag, kein hartcodierter Modellname außerhalb der Settings.

Wichtige Abweichung vom MISTRAL-API-CHEATSHEET (dokumentiert, verifiziert per
`inspect.signature` gegen das installierte `mistralai==1.10.0`):
`Mistral().audio.transcriptions.complete_async` akzeptiert in dieser SDK-Version
**kein** `diarize`- und kein `context_bias`-Kwarg, und `timestamp_granularities`
ist auf `Literal["segment"]` typisiert (kein `"word"`). Würde dieser Adapter
`diarize=True`/`context_bias=...` übergeben, brächte das im Echtbetrieb sofort
einen `TypeError` (nur in Tests mit einem `MagicMock`/`AsyncMock` unsichtbar, weil
Mocks beliebige Kwargs akzeptieren). Deshalb ruft `transcribe_batch` ausschließlich
Parameter auf, die die installierte SDK-Methode tatsächlich kennt, und parst
Diarisation/Wort-Zeitstempel **defensiv** aus etwaigen Zusatzfeldern der Antwort:
die Response-Pydantic-Modelle (`TranscriptionResponse`, `TranscriptionSegmentChunk`)
sind mit `extra="allow"` konfiguriert — sobald die Live-API (oder eine künftige
SDK-Version) `speaker`/`words` pro Segment liefert, fließen sie automatisch durch,
ohne Codeänderung hier. Liefert die Antwort keine solchen Felder, wird **keine**
Diarisation fabriziert (kein Fake-Sprecherwechsel je Segment) — stattdessen ein
einzelner Sprecher `"unknown"`, ehrlich gemäß tatsächlich vorhandener Information.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, Literal

from mistralai import Mistral

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

# Granularität, die die installierte SDK-Methode tatsächlich unterstützt (kein "word").
_SUPPORTED_TIMESTAMP_GRANULARITIES: list[Literal["segment"]] = ["segment"]

_FALLBACK_SPEAKER = "unknown"


class VoxtralBatchTranscriptionError(RuntimeError):
    """Die Batch-Transkription über voxtral-mini-2602 ist fehlgeschlagen."""


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Liest ein Feld sowohl von dict-artigen als auch von attribut-artigen Objekten."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class VoxtralApiTranscriptionPort:
    """Default-STT-Adapter (`SOUFFLEUR_STT_PROVIDER=voxtral_api`) — Batch (Welle 4).

    Phase-2-Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`) folgt
    erst in Welle 12; hier nur Protocol-Stubs, damit der Adapter das vollständige
    `TranscriptionPort`-Protocol erfüllt (`isinstance`-Check der Factory, Welle 3).
    """

    def __init__(self, settings: Settings, client: Mistral | None = None) -> None:
        self._settings = settings
        self._client = client or Mistral(
            api_key=settings.mistral_api_key, server_url=settings.mistral_base_url
        )

    # --- Phase 2 — Live-Streaming (Stub, folgt in Welle 12) -----------------------
    async def open_stream(self, session: SessionContext) -> StreamHandle:
        raise NotImplementedError("Live-Streaming (voxtral_api) folgt erst in Welle 12")

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        raise NotImplementedError("Live-Streaming (voxtral_api) folgt erst in Welle 12")

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        raise NotImplementedError("Live-Streaming (voxtral_api) folgt erst in Welle 12")
        yield  # pragma: no cover - macht die Methode zum Async-Generator

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        raise NotImplementedError("Live-Streaming (voxtral_api) folgt erst in Welle 12")

    # --- Phase 1 — Batch (Diarisation + Wort-Zeitstempel) --------------------------
    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        if not audio.local_path:
            raise ValueError(
                "voxtral_api.transcribe_batch benötigt AudioRef.local_path (Batch-Datei)"
            )

        with open(audio.local_path, "rb") as handle:
            content = handle.read()
        file_name = os.path.basename(audio.local_path)

        try:
            response = await self._client.audio.transcriptions.complete_async(
                model=self._settings.model_stt_batch,
                file={"content": content, "file_name": file_name},
                timestamp_granularities=_SUPPORTED_TIMESTAMP_GRANULARITIES,
            )
        except Exception as exc:  # noqa: BLE001 - in VoxtralBatchTranscriptionError übersetzt
            raise VoxtralBatchTranscriptionError(
                f"voxtral-mini-2602 Batch-Transkription fehlgeschlagen: {exc}"
            ) from exc

        return self._parse_response(response)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,  # Live-Streaming folgt erst in Welle 12
            supports_diarization=True,
            supports_word_timestamps=True,
            typical_final_latency_ms=300,
            residency="EU",
        )

    # --- Parsing (defensiv gegen Pydantic-Extra-Felder) ----------------------------
    def _parse_response(self, response: Any) -> TranscriptResult:
        raw_segments = _get(response, "segments") or []
        events: list[TranscriptEvent] = []
        speakers: list[str] = []

        for raw_segment in raw_segments:
            speaker = self._extract_speaker(raw_segment)
            if speaker not in speakers:
                speakers.append(speaker)
            words = self._extract_words(raw_segment)
            events.append(
                TranscriptEvent(
                    kind="final",
                    speaker=speaker,
                    text=_get(raw_segment, "text", "") or "",
                    t_start_ms=self._seconds_to_ms(_get(raw_segment, "start", 0.0)),
                    t_end_ms=self._seconds_to_ms(_get(raw_segment, "end", 0.0)),
                    words=words,
                )
            )

        if not speakers:
            speakers = [_FALLBACK_SPEAKER]

        duration_ms = self._extract_duration_ms(response, raw_segments)

        return TranscriptResult(
            segments=events,
            speakers=speakers,
            duration_ms=duration_ms,
            model=self._settings.model_stt_batch,
            provider="voxtral_api",
        )

    @staticmethod
    def _extract_speaker(segment: Any) -> str:
        for attr in ("speaker", "speaker_id", "speaker_label"):
            value = _get(segment, attr)
            if value:
                return str(value)
        return _FALLBACK_SPEAKER

    @classmethod
    def _extract_words(cls, segment: Any) -> list[Word] | None:
        raw_words = _get(segment, "words")
        if not raw_words:
            return None
        words: list[Word] = []
        for raw_word in raw_words:
            text = _get(raw_word, "text", "") or ""
            words.append(
                Word(
                    text=text,
                    t_start_ms=cls._seconds_to_ms(_get(raw_word, "start", 0.0)),
                    t_end_ms=cls._seconds_to_ms(_get(raw_word, "end", 0.0)),
                )
            )
        return words

    @staticmethod
    def _seconds_to_ms(value: Any) -> int:
        return round(float(value or 0.0) * 1000)

    @classmethod
    def _extract_duration_ms(cls, response: Any, raw_segments: list[Any]) -> int:
        usage = _get(response, "usage")
        audio_seconds = _get(usage, "prompt_audio_seconds")
        if audio_seconds:
            return cls._seconds_to_ms(audio_seconds)
        if raw_segments:
            return cls._seconds_to_ms(_get(raw_segments[-1], "end", 0.0))
        return 0
