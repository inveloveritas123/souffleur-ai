"""adapters/capture — Dual-Source-Capture-Konvention (Phase 2, Welle 12)."""
from __future__ import annotations

from souffleur.adapters.capture.dual_source import (
    CHANNEL_TO_SPEAKER,
    DUAL_SOURCE_CHANNELS,
    SOURCE_TO_CHANNEL,
    SOURCE_TO_SPEAKER,
    CaptureChunk,
    CaptureSource,
    UnknownCaptureSourceError,
    channel_for_source,
    speaker_for_source,
)

__all__ = [
    "CHANNEL_TO_SPEAKER",
    "DUAL_SOURCE_CHANNELS",
    "SOURCE_TO_CHANNEL",
    "SOURCE_TO_SPEAKER",
    "CaptureChunk",
    "CaptureSource",
    "UnknownCaptureSourceError",
    "channel_for_source",
    "speaker_for_source",
]
