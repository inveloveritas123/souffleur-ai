"""Welle 12 — adapters/capture: Dual-Source-Konvention (reine Datenstrukturen, kein I/O)."""
from __future__ import annotations

import pytest
from souffleur.adapters.capture import (
    CHANNEL_TO_SPEAKER,
    DUAL_SOURCE_CHANNELS,
    CaptureChunk,
    UnknownCaptureSourceError,
    channel_for_source,
    speaker_for_source,
)
from souffleur.ports.types import SessionContext


def test_dual_source_channels_constant_is_two() -> None:
    assert DUAL_SOURCE_CHANNELS == 2


def test_session_context_with_dual_source_channels() -> None:
    session = SessionContext(
        tenant_id="zukunftsbund",
        session_id="s1",
        consent_ref="c1",
        sample_rate=16000,
        channels=DUAL_SOURCE_CHANNELS,
    )
    assert session.channels == 2


def test_speaker_for_source_maps_microphone_to_coach() -> None:
    assert speaker_for_source("microphone") == "coach"


def test_speaker_for_source_maps_system_audio_to_counterpart() -> None:
    assert speaker_for_source("system_audio") == "counterpart"


def test_speaker_for_source_rejects_unknown_source() -> None:
    with pytest.raises(UnknownCaptureSourceError):
        speaker_for_source("bluetooth_headset")  # type: ignore[arg-type]


def test_channel_for_source_matches_channel_to_speaker_table() -> None:
    mic_channel = channel_for_source("microphone")
    system_channel = channel_for_source("system_audio")

    assert CHANNEL_TO_SPEAKER[mic_channel] == "coach"
    assert CHANNEL_TO_SPEAKER[system_channel] == "counterpart"


def test_capture_chunk_carries_source_and_pcm_bytes() -> None:
    chunk = CaptureChunk(source="microphone", pcm=b"\x00\x01")
    assert chunk.source == "microphone"
    assert chunk.pcm == b"\x00\x01"
