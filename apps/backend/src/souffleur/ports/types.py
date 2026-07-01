"""Hilfstypen für den STT-Port (ARCHITECTURE.md "STT-Port-Interface").

Spiegelt `packages/shared/src/types.ts` (Single Source of Truth für Web/Overlay).
Diese Typen tragen niemals Audio-Rohdaten und werden nicht ins Audit-Log geschrieben
(Audit-Felder bleiben Metadaten, Gate E2/E4).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TranscriptEventKind = Literal["partial", "final"]


@dataclass(frozen=True)
class SessionContext:
    """Kontext einer Transkriptions-Session (Phase 1 Batch oder Phase 2 Live-Stream)."""

    tenant_id: str
    session_id: str
    consent_ref: str
    sample_rate: int
    channels: int  # 2 für Dual-Source (System-Audio = Gegenüber, Mikrofon = Coach)
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("SessionContext.tenant_id ist Pflicht (Mandantentrennung, Gate E3)")
        if not self.consent_ref:
            raise ValueError("SessionContext.consent_ref ist Pflicht (§201 StGB ConsentGate)")


@dataclass(frozen=True)
class StreamHandle:
    """Provider-internes Handle für eine offene Live-Stream-Session."""

    provider_handle: str
    correlation_id: str


@dataclass(frozen=True)
class Word:
    """Ein Wort-Zeitstempel innerhalb eines Transkript-Segments."""

    text: str
    t_start_ms: int
    t_end_ms: int


@dataclass(frozen=True)
class TranscriptEvent:
    """Ein partielles oder finales Transkript-Segment mit Sprecher-Label."""

    kind: TranscriptEventKind
    speaker: str
    text: str
    t_start_ms: int
    t_end_ms: int
    words: list[Word] | None = None


@dataclass(frozen=True)
class TranscriptResult:
    """Ergebnis einer Batch-Transkription oder einer geschlossenen Live-Stream-Session."""

    segments: list[TranscriptEvent]
    speakers: list[str]
    duration_ms: int
    model: str
    provider: str


@dataclass(frozen=True)
class ProviderCapabilities:
    """Metadaten eines STT-Adapters — erlaubt latenz-/feature-bewusstes Routing."""

    supports_streaming: bool
    supports_diarization: bool
    supports_word_timestamps: bool
    typical_final_latency_ms: int
    residency: str = "EU"


@dataclass(frozen=True)
class AudioRef:
    """Referenz auf eine Audio-Quelle (lokaler Pfad oder Stream) — niemals Audio im Log."""

    local_path: str | None = None
    stream_source: str | None = None

    def __post_init__(self) -> None:
        if not self.local_path and not self.stream_source:
            raise ValueError("AudioRef benötigt local_path oder stream_source")


@dataclass(frozen=True)
class BatchOptions:
    """Optionen für die Phase-1-Batch-Transkription (Diarisation, Wort-Zeitstempel)."""

    diarization: bool = True
    word_timestamps: bool = True
    language: str | None = None
    num_speakers_hint: int | None = None
    context_bias: str | None = None  # Domänen-Begriffe (kommagetrennt) zur Erkennungs-Verbesserung
