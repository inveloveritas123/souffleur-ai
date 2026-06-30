"""TranscriptionPort — austauschbares STT-Interface (ARCHITECTURE.md).

Provider-Wechsel ist reine Konfiguration über `SOUFFLEUR_STT_PROVIDER`
(`adapters/stt/factory.py`); kein Aufrufer kennt den konkreten Adapter
(voxtral_api, voxtral_local, gladia). Signaturen wörtlich aus ARCHITECTURE.md
"STT-Port-Interface" übernommen.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from souffleur.ports.types import (
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    SessionContext,
    StreamHandle,
    TranscriptEvent,
    TranscriptResult,
)


@runtime_checkable
class TranscriptionPort(Protocol):
    """Vertrag, den jeder STT-Adapter erfüllen muss."""

    # --- Phase 2 — Live-Streaming ---
    async def open_stream(self, session: SessionContext) -> StreamHandle: ...

    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None: ...

    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]: ...

    async def close_stream(self, handle: StreamHandle) -> TranscriptResult: ...

    # --- Phase 1 — Batch (Protokoll mit Diarisation + Wort-Zeitstempeln) ---
    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult: ...

    # --- Metadaten — erlaubt latenz-/feature-bewusstes Routing ---
    def capabilities(self) -> ProviderCapabilities: ...
