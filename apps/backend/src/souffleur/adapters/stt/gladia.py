"""gladia — EU-Drop-in-Fallback-STT-Adapter (Frankreich), Batch (Phase 1).

ARCHITECTURE.md: "gladia: Drop-in-Fallback, EU-Endpunkt (Frankreich), nur falls
Live-Latenz gemessen nicht ausreicht." Dieser Adapter implementiert denselben
`TranscriptionPort` wie `voxtral_api`/`voxtral_local` via `httpx` gegen die echte
Gladia-v2-REST-API (Upload -> Transcription-Job -> Poll-Result), EU-Region
erzwungen (Gate E1).

EU-Routing (Gate E1): einziger zulässiger Endpunkt ist `https://api.gladia.io`
(Gladia hat seinen Sitz in Frankreich; dieser Host ist der von Gladia dokumentierte
EU-Produktions-Endpunkt). Sowohl die konfigurierte `settings.gladia_base_url` als
auch jede vom Server zurückgegebene absolute `result_url` werden gegen dieses
Präfix geprüft — defensiv, zusätzlich zur bereits in `core/settings.py`
vorhandenen `NonEuEndpointError`-Validierung für Mistral (diese hier ist
adapter-lokal, weil `Settings` für Gladia aktuell keine äquivalente Validierung
hat und dieser Welle laut Scope `core/settings.py` nicht ändern darf).

Auth: `GLADIA_API_KEY` (Header `x-gladia-key`) aus `settings.gladia_api_key`
(liest `.env`/Umgebung — nie hartkodiert, Gate D3). Fehlt der Key, wirft jeder
Versuch einer echten Transkription `GladiaApiKeyMissingError` mit klarer
Meldung; Instanziierung und `capabilities()` funktionieren auch ohne Key (damit
die Factory den Adapter bauen kann, ohne dass ein Key vorhanden sein muss).

Tests mocken `httpx` vollständig (Client per Dependency-Injection ersetzbar) —
keine echten Netzaufrufe, kein Key nötig (Gate E1/E2).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import httpx

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

# Einziger zulässiger Gladia-Endpunkt (EU, Frankreich) — Gate E1.
_ALLOWED_GLADIA_HOST = "api.gladia.io"

# Gladia hat kein gepinntes "Modell" wie Mistral (Single-Provider-API); dieser
# Bezeichner dokumentiert nur, welche API-Version dieser Adapter anspricht.
_GLADIA_MODEL = "gladia-v2"

_FALLBACK_SPEAKER = "unknown"
_SPEAKER_FIELDS = ("speaker", "speaker_id", "speaker_label")

_LIVE_STREAMING_ERROR = (
    "gladia unterstützt in dieser Welle kein Live-Streaming — nur Batch "
    "(transcribe_batch). Live-Streaming via Gladia folgt erst, falls die "
    "gemessene Voxtral-Live-Latenz nicht ausreicht (ARCHITECTURE.md)."
)


class NonEuGladiaEndpointError(ValueError):
    """Eine Gladia-URL (Base-URL oder Result-URL) zeigt nicht auf den EU-Endpunkt (Gate E1)."""


class GladiaApiKeyMissingError(RuntimeError):
    """`GLADIA_API_KEY` ist nicht gesetzt — Gladia-Adapter kann keine echte Anfrage stellen."""


class GladiaTranscriptionError(RuntimeError):
    """Die Batch-Transkription über die Gladia-API ist fehlgeschlagen."""


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Liest ein Feld sowohl von dict-artigen als auch von attribut-artigen Objekten."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _require_eu_host(url: str, *, what: str) -> None:
    """Exakter Host-Vergleich (kein Präfix-Vergleich) — Gate E1, BLOCKER-Fix.

    `url.startswith("https://api.gladia.io")` würde `https://api.gladia.io.attacker.example`
    fälschlich akzeptieren (der Angreifer-Host beginnt textuell mit dem erlaubten Präfix).
    `urlsplit(...).hostname` liefert stattdessen den tatsächlichen Host, gegen den exakt
    verglichen wird; zusätzlich wird `https` als Schema erzwungen (kein Downgrade).
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != _ALLOWED_GLADIA_HOST:
        raise NonEuGladiaEndpointError(
            f"{what} muss auf https://{_ALLOWED_GLADIA_HOST} (EU, Frankreich) zeigen, "
            f"war: {url!r}"
        )


class GladiaTranscriptionPort:
    """EU-Drop-in-Fallback-STT-Adapter (`SOUFFLEUR_STT_PROVIDER=gladia`) — Batch.

    Ablauf je `transcribe_batch`-Aufruf (Gladia-v2-Vertrag):
    1. `POST /v2/upload` (multipart) -> `audio_url`
    2. `POST /v2/transcription` (json, inkl. Diarisations-Optionen) -> `result_url`
    3. `GET result_url` wiederholt, bis `status == "done"` (oder `"error"`)

    `client` ist ein Dependency-Injection-Hook fürs Testen (ersetzt den echten
    `httpx.AsyncClient`). `poll_interval_s`/`max_polls` sind in Tests auf `0`/klein
    setzbar, damit kein Test echte Wartezeit braucht.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        poll_interval_s: float = 1.0,
        max_polls: int = 60,
    ) -> None:
        _require_eu_host(settings.gladia_base_url, what="GLADIA_BASE_URL")
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.gladia_base_url, timeout=30.0
        )
        self._poll_interval_s = poll_interval_s
        self._max_polls = max_polls

    def _require_api_key(self) -> str:
        api_key = self._settings.gladia_api_key
        if not api_key:
            raise GladiaApiKeyMissingError(
                "GLADIA_API_KEY ist nicht gesetzt — der gladia-Adapter benötigt einen "
                "API-Key für echte Transkriptionen (siehe .env.example, GLADIA_API_KEY)."
            )
        return api_key

    # --- Phase 2 — Live-Streaming: nicht in dieser Welle (siehe Modul-Docstring) ----
    async def open_stream(self, session: SessionContext) -> StreamHandle:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)
        yield  # pragma: no cover - macht die Methode zum Async-Generator

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    # --- Phase 1 — Batch (Diarisation + Wort-Zeitstempel via Gladia-v2) ------------
    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        if not audio.local_path:
            raise ValueError(
                "gladia.transcribe_batch benötigt AudioRef.local_path (Batch-Datei)"
            )

        api_key = self._require_api_key()
        try:
            audio_url = await self._upload(audio.local_path, api_key)
            result_url = await self._start_transcription(audio_url, opts, api_key)
            result = await self._poll_result(result_url, api_key)
        except httpx.HTTPError as exc:
            raise GladiaTranscriptionError(
                f"Gladia-Batch-Transkription fehlgeschlagen: {exc}"
            ) from exc

        return self._parse_result(result)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            supports_diarization=True,
            supports_word_timestamps=True,
            typical_final_latency_ms=600,
            residency="EU",
        )

    # --- Gladia-v2-Aufrufe -----------------------------------------------------------
    async def _upload(self, local_path: str, api_key: str) -> str:
        with open(local_path, "rb") as handle:
            content = handle.read()
        file_name = os.path.basename(local_path)

        response = await self._client.post(
            "/v2/upload",
            headers={"x-gladia-key": api_key},
            files={"audio": (file_name, content)},
        )
        response.raise_for_status()
        data = response.json()
        audio_url = data.get("audio_url")
        if not audio_url:
            raise GladiaTranscriptionError("Gladia /v2/upload lieferte keine audio_url")
        return str(audio_url)

    async def _start_transcription(self, audio_url: str, opts: BatchOptions, api_key: str) -> str:
        payload: dict[str, Any] = {
            "audio_url": audio_url,
            "diarization": opts.diarization,
        }
        if opts.language:
            payload["language"] = opts.language
        if opts.num_speakers_hint:
            payload["diarization_config"] = {"number_of_speakers": opts.num_speakers_hint}

        response = await self._client.post(
            "/v2/transcription",
            headers={"x-gladia-key": api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        result_url = data.get("result_url")
        if not result_url:
            raise GladiaTranscriptionError(
                "Gladia /v2/transcription lieferte keine result_url"
            )
        _require_eu_host(str(result_url), what="Gladia result_url")
        return str(result_url)

    async def _poll_result(self, result_url: str, api_key: str) -> dict[str, Any]:
        import asyncio

        for attempt in range(self._max_polls):
            if attempt > 0:
                await asyncio.sleep(self._poll_interval_s)

            response = await self._client.get(result_url, headers={"x-gladia-key": api_key})
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "done":
                return data
            if status == "error":
                raise GladiaTranscriptionError(
                    f"Gladia-Transkriptionsjob meldet Fehler: {data.get('error')!r}"
                )

        raise GladiaTranscriptionError(
            f"Gladia-Transkriptionsjob nicht fertig nach {self._max_polls} Polls"
        )

    # --- Parsing (defensiv gegen das Gladia-v2-Response-Schema) ---------------------
    def _parse_result(self, response: dict[str, Any]) -> TranscriptResult:
        result = _get(response, "result") or response
        transcription = _get(result, "transcription") or {}
        raw_utterances = _get(transcription, "utterances") or []

        events: list[TranscriptEvent] = []
        speakers: list[str] = []

        for raw in raw_utterances:
            speaker = self._extract_speaker(raw)
            if speaker not in speakers:
                speakers.append(speaker)
            events.append(
                TranscriptEvent(
                    kind="final",
                    speaker=speaker,
                    text=_get(raw, "text", "") or "",
                    t_start_ms=self._seconds_to_ms(_get(raw, "start", 0.0)),
                    t_end_ms=self._seconds_to_ms(_get(raw, "end", 0.0)),
                    words=self._extract_words(raw),
                )
            )

        if not speakers:
            speakers = [_FALLBACK_SPEAKER]

        duration_ms = self._extract_duration_ms(result, raw_utterances)

        return TranscriptResult(
            segments=events,
            speakers=speakers,
            duration_ms=duration_ms,
            model=_GLADIA_MODEL,
            provider="gladia",
        )

    @staticmethod
    def _extract_speaker(segment: Any) -> str:
        for field in _SPEAKER_FIELDS:
            value = _get(segment, field)
            if value is not None and value != "":
                return str(value)
        return _FALLBACK_SPEAKER

    @classmethod
    def _extract_words(cls, segment: Any) -> list[Word] | None:
        raw_words = _get(segment, "words")
        if not raw_words:
            return None
        words: list[Word] = []
        for raw_word in raw_words:
            # Gladia nennt das Wortfeld "word" (nicht "text"); defensiv beides prüfen.
            text = _get(raw_word, "word") or _get(raw_word, "text", "") or ""
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
    def _extract_duration_ms(cls, result: Any, raw_utterances: list[Any]) -> int:
        metadata = _get(result, "metadata")
        audio_duration = _get(metadata, "audio_duration")
        if audio_duration:
            return cls._seconds_to_ms(audio_duration)
        if raw_utterances:
            return cls._seconds_to_ms(_get(raw_utterances[-1], "end", 0.0))
        return 0
