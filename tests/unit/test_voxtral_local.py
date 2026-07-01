"""Unit-Tests adapters/stt/voxtral_local.py — On-Device-MLX-Adapter, `model_loader` per DI.

Kein echter MLX-Download/-Import in diesen Tests: `model_loader` ersetzt `_default_model_loader`
komplett (genau das vom Modul-Docstring vorgesehene Testmuster). Der einzige Test, der die
*echte* `_default_model_loader`-Fallback-Kette anfasst, verifiziert nur den ehrlichen
`VoxtralLocalUnavailableError`, der auftritt, wenn (wie in dieser Sandbox) weder `mlx_audio`
noch `mlx_voxtral` installiert ist — kein Download, kein Netzaufruf.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings, remove_if_exists  # noqa: E402
from souffleur.adapters.stt.voxtral_local import (  # noqa: E402
    VoxtralLocalTranscriptionError,
    VoxtralLocalTranscriptionPort,
    VoxtralLocalUnavailableError,
    _default_model_loader,
)
from souffleur.ports.types import AudioRef, BatchOptions, SessionContext, StreamHandle  # noqa: E402


class _FakeModel:
    def __init__(self, result: Any = None, raises: Exception | None = None) -> None:
        self._result = result
        self._raises = raises
        self.transcribe_calls: list[str] = []

    def transcribe(self, path: str) -> Any:
        self.transcribe_calls.append(path)
        if self._raises is not None:
            raise self._raises
        return self._result


def _tmp_audio_file() -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(b"fake-audio")
    handle.close()
    return handle.name


class VoxtralLocalCapabilitiesTest(unittest.TestCase):
    def test_capabilities_report_local_residency_without_diarization(self) -> None:
        port = VoxtralLocalTranscriptionPort(default_settings())
        capabilities = port.capabilities()
        self.assertFalse(capabilities.supports_diarization)
        self.assertTrue(capabilities.supports_word_timestamps)
        self.assertEqual(capabilities.residency, "local")


class VoxtralLocalLiveStreamingNotImplementedTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_push_close_raise_not_implemented(self) -> None:
        port = VoxtralLocalTranscriptionPort(default_settings())
        session = SessionContext(
            tenant_id="t1", session_id="s1", consent_ref="c1", sample_rate=16000, channels=1
        )
        with self.assertRaises(NotImplementedError):
            await port.open_stream(session)
        with self.assertRaises(NotImplementedError):
            await port.push_audio(StreamHandle(provider_handle="h", correlation_id="h"), b"\x00")
        with self.assertRaises(NotImplementedError):
            await port.close_stream(StreamHandle(provider_handle="h", correlation_id="h"))

    async def test_events_raises_not_implemented(self) -> None:
        port = VoxtralLocalTranscriptionPort(default_settings())
        with self.assertRaises(NotImplementedError):
            async for _event in port.events(StreamHandle(provider_handle="h", correlation_id="h")):
                pass


class VoxtralLocalTranscribeBatchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._audio_path = _tmp_audio_file()
        self.addCleanup(remove_if_exists, self._audio_path)

    async def test_missing_local_path_raises_value_error(self) -> None:
        port = VoxtralLocalTranscriptionPort(default_settings())
        with self.assertRaises(ValueError):
            await port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions())

    async def test_nonexistent_file_raises_value_error(self) -> None:
        port = VoxtralLocalTranscriptionPort(default_settings())
        # `tempfile.gettempdir()` statt hartkodiertem "/tmp" (SAST-Befund B108 vermeiden).
        missing_path = os.path.join(tempfile.gettempdir(), "does-not-exist-souffleur.wav")
        with self.assertRaises(ValueError):
            await port.transcribe_batch(AudioRef(local_path=missing_path), BatchOptions())

    async def test_segments_are_parsed_with_words_and_fallback_speaker(self) -> None:
        model = _FakeModel(
            result={
                "segments": [
                    {
                        "text": "Hallo Welt",
                        "start": 0.0,
                        "end": 1.2,
                        "words": [{"text": "Hallo", "start": 0.0, "end": 0.5}],
                    }
                ],
                "duration": 1.2,
            }
        )
        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=lambda: model)

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.provider, "voxtral_local")
        self.assertEqual(result.speakers, ["unknown"])
        self.assertEqual(result.duration_ms, 1200)
        self.assertEqual(result.segments[0].words[0].text, "Hallo")  # type: ignore[index]

    async def test_model_loader_is_called_lazily_and_only_once(self) -> None:
        calls = 0

        def loader() -> _FakeModel:
            nonlocal calls
            calls += 1
            return _FakeModel(result={"segments": []})

        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=loader)
        self.assertEqual(calls, 0)  # kein Aufruf im Konstruktor

        await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())
        await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(calls, 1)  # zweiter Aufruf nutzt das zwischengespeicherte Modell

    async def test_no_segments_but_text_yields_single_fallback_event(self) -> None:
        model = _FakeModel(result={"text": "Nur Text ohne Segmente", "duration": 2.0})
        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=lambda: model)

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].text, "Nur Text ohne Segmente")
        self.assertEqual(result.duration_ms, 2000)

    async def test_completely_empty_result_yields_no_events_and_zero_duration(self) -> None:
        model = _FakeModel(result={})
        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=lambda: model)

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.segments, [])
        self.assertEqual(result.speakers, [])
        self.assertEqual(result.duration_ms, 0)

    async def test_duration_falls_back_to_last_segment_end_without_duration_field(self) -> None:
        model = _FakeModel(result={"segments": [{"text": "x", "start": 0.0, "end": 3.3}]})
        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=lambda: model)

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.duration_ms, 3300)

    async def test_model_transcribe_failure_is_translated_to_local_error(self) -> None:
        model = _FakeModel(raises=RuntimeError("MLX-Inferenz abgestürzt"))
        port = VoxtralLocalTranscriptionPort(default_settings(), model_loader=lambda: model)

        with self.assertRaises(VoxtralLocalTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())


class DefaultModelLoaderTest(unittest.TestCase):
    def test_raises_unavailable_when_neither_mlx_library_is_installed(self) -> None:
        """Ehrlicher Test der echten Fallback-Kette — kein Mock: in dieser Sandbox ist weder
        `mlx_audio` noch `mlx_voxtral` installiert (beide sind optionale Apple-Silicon-Pakete,
        siehe Modul-Docstring), daher MUSS `_default_model_loader()` diesen Fehler werfen."""
        try:
            import mlx_audio  # type: ignore[import-not-found]  # noqa: F401

            self.skipTest("mlx_audio ist installiert — Fallback-Pfad hier nicht anwendbar")
        except ImportError:
            pass
        try:
            import mlx_voxtral  # type: ignore[import-not-found]  # noqa: F401

            self.skipTest("mlx_voxtral ist installiert — Fallback-Pfad hier nicht anwendbar")
        except ImportError:
            pass

        with self.assertRaises(VoxtralLocalUnavailableError):
            _default_model_loader()


if __name__ == "__main__":
    unittest.main()
