"""Unit-Tests adapters/capture/dual_source.py — Kanal<->Sprecher-Konvention (Dual-Source)."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.adapters.capture.dual_source import (  # noqa: E402
    CHANNEL_TO_SPEAKER,
    DUAL_SOURCE_CHANNELS,
    SOURCE_TO_CHANNEL,
    SOURCE_TO_SPEAKER,
    CaptureChunk,
    UnknownCaptureSourceError,
    channel_for_source,
    speaker_for_source,
)


class ConstantsTest(unittest.TestCase):
    def test_dual_source_uses_two_channels(self) -> None:
        self.assertEqual(DUAL_SOURCE_CHANNELS, 2)

    def test_channel_to_speaker_mapping(self) -> None:
        self.assertEqual(CHANNEL_TO_SPEAKER, {0: "coach", 1: "counterpart"})

    def test_source_mappings_are_consistent_with_channel_mapping(self) -> None:
        for source, channel in SOURCE_TO_CHANNEL.items():
            self.assertEqual(CHANNEL_TO_SPEAKER[channel], SOURCE_TO_SPEAKER[source])


class SpeakerForSourceTest(unittest.TestCase):
    def test_microphone_is_coach(self) -> None:
        self.assertEqual(speaker_for_source("microphone"), "coach")

    def test_system_audio_is_counterpart(self) -> None:
        self.assertEqual(speaker_for_source("system_audio"), "counterpart")

    def test_unknown_source_raises(self) -> None:
        with self.assertRaises(UnknownCaptureSourceError):
            speaker_for_source("bluetooth")  # type: ignore[arg-type]


class ChannelForSourceTest(unittest.TestCase):
    def test_microphone_is_channel_zero(self) -> None:
        self.assertEqual(channel_for_source("microphone"), 0)

    def test_system_audio_is_channel_one(self) -> None:
        self.assertEqual(channel_for_source("system_audio"), 1)

    def test_unknown_source_raises(self) -> None:
        with self.assertRaises(UnknownCaptureSourceError):
            channel_for_source("bluetooth")  # type: ignore[arg-type]


class CaptureChunkTest(unittest.TestCase):
    def test_holds_source_and_pcm_bytes(self) -> None:
        chunk = CaptureChunk(source="microphone", pcm=b"\x00\x01")
        self.assertEqual(chunk.source, "microphone")
        self.assertEqual(chunk.pcm, b"\x00\x01")


if __name__ == "__main__":
    unittest.main()
