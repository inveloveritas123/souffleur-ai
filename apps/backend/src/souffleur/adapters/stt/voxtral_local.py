"""voxtral_local — Kostenspar-STT-Adapter über lokale MLX-Inferenz (Apple Silicon).

Implementiert denselben `TranscriptionPort` wie `voxtral_api`, aber ohne API-Calls:
die Inferenz läuft on-device via MLX (Apple-Silicon-GPU). Kein API-Key, keine
laufenden Kosten, Audio verlässt das Gerät nie (`capabilities().residency == "local"`).
Das ist die explizite Kostenspar-Option für Nutzer mit Apple-Silicon-Hardware
(siehe MISTRAL-API-CHEATSHEET.md, Abschnitt "Lokale Kostenspar-Option").

Lazy-Import + Lazy-Weight-Download (Pflicht, keine Ausnahme):
`mlx_audio`/`mlx_voxtral` wird **nicht** beim Modul-Import geladen — sonst würde
schon ein `import souffleur.adapters.stt.voxtral_local` auf einer Nicht-Apple-
Silicon-Maschine (z.B. Linux-CI) crashen, obwohl der Provider gar nicht aktiv ist.
Stattdessen passiert der Import (und ein impliziter Download der ~2,5GB
Q4-Gewichte `mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit` beim allerersten
Lauf, sofern noch nicht im HuggingFace-Cache) ausschließlich beim ersten echten
Aufruf von `transcribe_batch` — über `_default_model_loader`, der per Konstruktor-
Parameter `model_loader` austauschbar ist (Dependency-Injection fürs Testen).

Optionale Dependency — NICHT in pyproject.toml eingetragen (Scope dieser Welle
sind ausschließlich `voxtral_local.py`/`gladia.py` + ihre Tests; pyproject.toml
bleibt unberührt). Wer den Provider aktivieren will, installiert manuell:
    pip install mlx-audio    # bevorzugt: STT auf MLX, Streaming token-by-token
    # ODER, falls mlx-audio fehlt:
    pip install mlx-voxtral  # dedizierte MLX-Voxtral-Inferenz
Beide Pakete sind nur auf Apple Silicon (macOS, M-Serie) lauffähig.

Live-Streaming (`open_stream`/`push_audio`/`events`/`close_stream`): die MLX-
STT-Bibliotheken bieten (Stand dieser Welle) keinen stabilen Push/Pull-Chunking-
Vertrag für ein Server-seitiges Streaming-Protokoll wie `TranscriptionPort` es
für Phase 2 vorsieht (Token-für-Token-Generatoren ohne Zwischenstand-Snapshot).
Statt das vorzutäuschen, werfen diese vier Methoden einen ehrlichen
`NotImplementedError` mit klarer Begründung — analog zum Stub-Pattern in
`voxtral_api.py` (dort: "folgt erst in Welle 12"). Für Live-Streaming bleibt
`voxtral_api` (oder künftig `gladia`) der richtige Provider.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from typing import Any

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

# Gepinnte lokale Gewichte (Gate F1-Geist: kein bewegliches Tag) — Q4, ~2,5GB,
# passt auf 16GB Apple-Silicon-Unified-Memory (siehe Cheatsheet).
_MLX_MODEL_ID = "mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit"

_FALLBACK_SPEAKER = "unknown"

_LIVE_STREAMING_ERROR = (
    "voxtral_local unterstützt kein Live-Streaming: die lokalen MLX-STT-Bibliotheken "
    "(mlx-audio/mlx-voxtral) bieten kein stabiles Push/Pull-Chunking-Protokoll für "
    "Phase-2-Streaming. Für Live-Streaming `voxtral_api` oder `gladia` verwenden."
)


class VoxtralLocalUnavailableError(RuntimeError):
    """Weder `mlx_audio` noch `mlx_voxtral` ist installiert (Apple Silicon vorausgesetzt)."""


class VoxtralLocalTranscriptionError(RuntimeError):
    """Die lokale MLX-Batch-Transkription ist fehlgeschlagen."""


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Liest ein Feld sowohl von dict-artigen als auch von attribut-artigen Objekten.

    Dieselbe Strategie wie in `voxtral_api._get` — bewusst hier dupliziert statt
    importiert, damit `voxtral_local` keine Laufzeit-Abhängigkeit zu `voxtral_api`
    bekommt (zwei unabhängig austauschbare Adapter desselben Ports, Scope dieser
    Welle verbietet zudem Änderungen an `voxtral_api.py`).
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _default_model_loader() -> Any:
    """Lazy-Import + Lazy-Weight-Download — wird NIE beim Modul-Import aufgerufen.

    Importiert beim ersten echten Lauf `mlx_audio` (bevorzugt, Streaming-fähige
    MLX-STT-Bibliothek) oder fällt auf `mlx_voxtral` zurück, und lädt das gepinnte
    Modell. Beide Bibliotheken bieten ein `load_model(model_id)`-Factory-Pattern;
    das löst ggf. den Download der Gewichte von Hugging Face aus (gecached unter
    `~/.cache/huggingface`, identisch zum üblichen MLX-Verhalten).
    """
    try:
        import mlx_audio as mlx_backend  # type: ignore[import-not-found]
    except ImportError:
        try:
            import mlx_voxtral as mlx_backend  # type: ignore[import-not-found,no-redef]
        except ImportError as exc:
            raise VoxtralLocalUnavailableError(
                "Keine lokale MLX-STT-Bibliothek installiert — `pip install mlx-audio` "
                "(bevorzugt) oder `pip install mlx-voxtral` (beide optional, nur auf "
                "Apple Silicon; siehe MISTRAL-API-CHEATSHEET.md, Abschnitt "
                "'Lokale Kostenspar-Option')."
            ) from exc
    return mlx_backend.load_model(_MLX_MODEL_ID)


class VoxtralLocalTranscriptionPort:
    """Kostenspar-STT-Adapter (`SOUFFLEUR_STT_PROVIDER=voxtral_local`) — Batch, on-device MLX.

    Kein Netzwerk-Call, keine API-Kosten. `model_loader` ist ein Dependency-
    Injection-Hook fürs Testen: ein Fake liefert direkt ein Objekt mit `.transcribe(path)`
    zurück, ohne dass jemals `mlx_audio`/`mlx_voxtral` importiert oder ein Download
    ausgelöst wird. Ohne expliziten `model_loader` wird `_default_model_loader`
    verwendet — aber erst beim ersten `transcribe_batch`-Aufruf, nie im Konstruktor
    (also auch nicht, wenn die Factory diese Klasse instanziiert).
    """

    def __init__(self, settings: Settings, model_loader: Callable[[], Any] | None = None) -> None:
        self._settings = settings
        self._model_loader = model_loader or _default_model_loader
        self._model: Any = None  # lazy — erst bei _ensure_model() gesetzt

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = self._model_loader()
        return self._model

    # --- Phase 2 — Live-Streaming: kein stabiler MLX-Streaming-Vertrag (siehe Modul-Docstring) --
    async def open_stream(self, session: SessionContext) -> StreamHandle:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)
        yield  # pragma: no cover - macht die Methode zum Async-Generator

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
        raise NotImplementedError(_LIVE_STREAMING_ERROR)

    # --- Phase 1 — Batch (on-device, kostenfrei) ------------------------------------
    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        if not audio.local_path:
            raise ValueError(
                "voxtral_local.transcribe_batch benötigt AudioRef.local_path (Batch-Datei)"
            )
        if not os.path.exists(audio.local_path):
            raise ValueError(f"voxtral_local: Datei nicht gefunden: {audio.local_path!r}")

        model = self._ensure_model()
        try:
            raw_result = model.transcribe(audio.local_path)
        except Exception as exc:  # noqa: BLE001 - in VoxtralLocalTranscriptionError übersetzt
            raise VoxtralLocalTranscriptionError(
                f"Lokale MLX-Batch-Transkription fehlgeschlagen: {exc}"
            ) from exc

        return self._parse_result(raw_result)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            # Keine Diarisation lokal: Sprechertrennung erfolgt 1:1 über getrennte
            # Audio-Quellen (System-Audio=Gegenüber, Mikrofon=Coach), nicht über ein
            # Diarisations-Modell — siehe ARCHITECTURE.md.
            supports_diarization=False,
            supports_word_timestamps=True,
            typical_final_latency_ms=800,  # on-device, hardwareabhängig, nicht garantiert
            residency="local",
        )

    # --- Parsing (defensiv — Antwortform der optionalen MLX-Bibliothek ungetypt) ----
    def _parse_result(self, raw_result: Any) -> TranscriptResult:
        raw_segments = _get(raw_result, "segments") or []
        events: list[TranscriptEvent] = []

        for raw_segment in raw_segments:
            words = self._extract_words(raw_segment)
            events.append(
                TranscriptEvent(
                    kind="final",
                    speaker=_FALLBACK_SPEAKER,
                    text=_get(raw_segment, "text", "") or "",
                    t_start_ms=self._seconds_to_ms(_get(raw_segment, "start", 0.0)),
                    t_end_ms=self._seconds_to_ms(_get(raw_segment, "end", 0.0)),
                    words=words,
                )
            )

        if not events:
            # Manche STT-Bibliotheken liefern nur `text` ohne Segment-Liste — ein
            # einzelnes Segment ist ehrlicher als ein leeres Ergebnis zu melden.
            text = _get(raw_result, "text", "") or ""
            if text:
                duration_ms = self._seconds_to_ms(_get(raw_result, "duration", 0.0))
                events.append(
                    TranscriptEvent(
                        kind="final",
                        speaker=_FALLBACK_SPEAKER,
                        text=text,
                        t_start_ms=0,
                        t_end_ms=duration_ms,
                        words=None,
                    )
                )

        duration_ms = self._extract_duration_ms(raw_result, raw_segments)

        return TranscriptResult(
            segments=events,
            speakers=[_FALLBACK_SPEAKER] if events else [],
            duration_ms=duration_ms,
            model=_MLX_MODEL_ID,
            provider="voxtral_local",
        )

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
    def _extract_duration_ms(cls, raw_result: Any, raw_segments: list[Any]) -> int:
        duration = _get(raw_result, "duration")
        if duration:
            return cls._seconds_to_ms(duration)
        if raw_segments:
            return cls._seconds_to_ms(_get(raw_segments[-1], "end", 0.0))
        return 0
