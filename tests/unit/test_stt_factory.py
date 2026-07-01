"""Unit-Tests adapters/stt/factory.py — Provider-Wahl allein über `settings.stt_provider`."""
from __future__ import annotations

import dataclasses
import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings  # noqa: E402
from souffleur.adapters.stt.factory import (  # noqa: E402
    UnknownSttProviderError,
    build_transcription_port,
)
from souffleur.adapters.stt.gladia import GladiaTranscriptionPort  # noqa: E402
from souffleur.adapters.stt.voxtral_api import VoxtralApiTranscriptionPort  # noqa: E402
from souffleur.adapters.stt.voxtral_local import VoxtralLocalTranscriptionPort  # noqa: E402


class BuildTranscriptionPortTest(unittest.TestCase):
    def test_voxtral_api_is_default_provider(self) -> None:
        port = build_transcription_port(default_settings(stt_provider="voxtral_api"))
        self.assertIsInstance(port, VoxtralApiTranscriptionPort)

    def test_voxtral_local_provider(self) -> None:
        port = build_transcription_port(default_settings(stt_provider="voxtral_local"))
        self.assertIsInstance(port, VoxtralLocalTranscriptionPort)

    def test_gladia_provider(self) -> None:
        port = build_transcription_port(default_settings(stt_provider="gladia"))
        self.assertIsInstance(port, GladiaTranscriptionPort)

    def test_unknown_provider_raises_clear_error(self) -> None:
        # `Settings.from_env()` würde das schon ablehnen — direkt konstruiert, um die
        # Factory selbst (nicht die Settings-Validierung) zu prüfen.
        bogus_settings = dataclasses.replace(default_settings(), stt_provider="openai_whisper")
        with self.assertRaises(UnknownSttProviderError):
            build_transcription_port(bogus_settings)


if __name__ == "__main__":
    unittest.main()
