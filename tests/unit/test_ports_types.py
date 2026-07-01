"""Unit-Tests ports/types.py — Validierungen (Mandantentrennung, Consent) und Dataclass-Vertrag."""
from __future__ import annotations

import dataclasses
import os
import tempfile
import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.ports.types import (  # noqa: E402
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    SessionContext,
    StreamHandle,
    TranscriptEvent,
    TranscriptResult,
    Word,
)


class SessionContextTest(unittest.TestCase):
    def test_valid_context_constructs(self) -> None:
        context = SessionContext(
            tenant_id="t1", session_id="s1", consent_ref="c1", sample_rate=16000, channels=2
        )
        self.assertEqual(context.channels, 2)
        self.assertIsNone(context.language)

    def test_missing_tenant_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            SessionContext(
                tenant_id="", session_id="s1", consent_ref="c1", sample_rate=16000, channels=1
            )

    def test_missing_consent_ref_raises(self) -> None:
        with self.assertRaises(ValueError):
            SessionContext(
                tenant_id="t1", session_id="s1", consent_ref="", sample_rate=16000, channels=1
            )

    def test_is_frozen(self) -> None:
        context = SessionContext(
            tenant_id="t1", session_id="s1", consent_ref="c1", sample_rate=16000, channels=1
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.channels = 2  # type: ignore[misc]


class AudioRefTest(unittest.TestCase):
    def test_local_path_alone_is_valid(self) -> None:
        # `tempfile.gettempdir()` statt hartkodiertem "/tmp" (SAST-Befund B108 vermeiden) —
        # reiner Dataclass-Feldtest, es findet kein Datei-I/O statt.
        path = os.path.join(tempfile.gettempdir(), "audio.wav")
        ref = AudioRef(local_path=path)
        self.assertEqual(ref.local_path, path)

    def test_stream_source_alone_is_valid(self) -> None:
        ref = AudioRef(stream_source="mic-1")
        self.assertEqual(ref.stream_source, "mic-1")

    def test_neither_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            AudioRef()


class OtherTypesTest(unittest.TestCase):
    def test_word_fields(self) -> None:
        word = Word(text="Hallo", t_start_ms=0, t_end_ms=250)
        self.assertEqual(word.text, "Hallo")

    def test_transcript_event_defaults_words_to_none(self) -> None:
        event = TranscriptEvent(kind="final", speaker="coach", text="Hi", t_start_ms=0, t_end_ms=1)
        self.assertIsNone(event.words)

    def test_transcript_result_fields(self) -> None:
        result = TranscriptResult(
            segments=[], speakers=["coach"], duration_ms=1000, model="m", provider="p"
        )
        self.assertEqual(result.provider, "p")

    def test_provider_capabilities_default_residency_is_eu(self) -> None:
        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_diarization=True,
            supports_word_timestamps=True,
            typical_final_latency_ms=300,
        )
        self.assertEqual(capabilities.residency, "EU")

    def test_batch_options_defaults(self) -> None:
        options = BatchOptions()
        self.assertTrue(options.diarization)
        self.assertTrue(options.word_timestamps)
        self.assertIsNone(options.language)
        self.assertIsNone(options.num_speakers_hint)

    def test_stream_handle_fields(self) -> None:
        handle = StreamHandle(provider_handle="h1", correlation_id="c1")
        self.assertEqual(handle.provider_handle, "h1")


if __name__ == "__main__":
    unittest.main()
