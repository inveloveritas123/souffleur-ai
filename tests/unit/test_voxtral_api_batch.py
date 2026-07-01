"""Unit-Tests adapters/stt/voxtral_api.py — Batch (`transcribe_batch`, REST, Diarisation)."""
from __future__ import annotations

import tempfile
import unittest
from typing import Any
from unittest import mock

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings, remove_if_exists  # noqa: E402
from souffleur.adapters.stt.voxtral_api import (  # noqa: E402
    VoxtralApiTranscriptionPort,
    VoxtralBatchTranscriptionError,
)
from souffleur.ports.types import AudioRef, BatchOptions  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_ok: bool = True) -> None:
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self) -> None:
        if not self._status_ok:
            raise RuntimeError("HTTP-Fehler (simuliert)")

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpClient:
    def __init__(self, response: _FakeResponse | None = None, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises
        self.calls: list[dict[str, Any]] = []
        self.aclose_called = False

    async def post(self, url: str, *, headers: dict, data: dict, files: dict) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "data": data, "files": files})
        if self._raises is not None:
            raise self._raises
        assert self._response is not None
        return self._response

    async def aclose(self) -> None:
        self.aclose_called = True


def _tmp_audio_file() -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(b"RIFF-fake-audio-bytes")
    handle.close()
    return handle.name


class TranscribeBatchSuccessTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._audio_path = _tmp_audio_file()
        self.addCleanup(remove_if_exists, self._audio_path)

    async def test_parses_segments_with_speaker_ids_and_words(self) -> None:
        payload = {
            "model": "voxtral-mini-2602",
            "segments": [
                {
                    "text": "Guten Tag.",
                    "start": 0.0,
                    "end": 1.5,
                    "speaker_id": 0,
                    "words": [{"text": "Guten", "start": 0.0, "end": 0.5}],
                },
                {"text": "Hallo.", "start": 1.5, "end": 2.5, "speaker_id": 1},
                {"text": "Unklar.", "start": 2.5, "end": 3.0, "speaker_id": None},  # Fallback
            ],
            "usage": {"prompt_audio_seconds": 3.0},
        }
        client = _FakeHttpClient(response=_FakeResponse(payload))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.provider, "voxtral_api")
        self.assertEqual(result.model, "voxtral-mini-2602")
        self.assertEqual(result.duration_ms, 3000)
        self.assertEqual(result.speakers, ["speaker_0", "speaker_1", "unknown"])
        self.assertEqual(len(result.segments), 3)
        self.assertEqual(result.segments[0].speaker, "speaker_0")
        self.assertEqual(result.segments[0].t_end_ms, 1500)
        self.assertIsNotNone(result.segments[0].words)
        assert result.segments[0].words is not None
        self.assertEqual(result.segments[0].words[0].text, "Guten")
        self.assertEqual(result.segments[2].speaker, "unknown")

    async def test_duration_falls_back_to_last_segment_end_without_usage(self) -> None:
        payload = {"segments": [{"text": "x", "start": 0.0, "end": 4.2, "speaker_id": 0}]}
        client = _FakeHttpClient(response=_FakeResponse(payload))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.duration_ms, 4200)

    async def test_no_segments_and_no_usage_gives_zero_duration_and_fallback_speaker(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({"segments": []}))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.duration_ms, 0)
        self.assertEqual(result.speakers, ["unknown"])

    async def test_model_missing_in_payload_falls_back_to_settings_model(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({"segments": []}))
        settings = default_settings()
        port = VoxtralApiTranscriptionPort(settings, http_client=client)  # type: ignore[arg-type]

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.model, settings.model_stt_batch)

    async def test_language_option_sets_language_form_field_without_granularities(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({"segments": []}))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        await port.transcribe_batch(
            AudioRef(local_path=self._audio_path), BatchOptions(language="de", word_timestamps=True)
        )

        data = client.calls[0]["data"]
        self.assertEqual(data["language"], "de")
        self.assertNotIn("timestamp_granularities[]", data)

    async def test_without_language_and_without_word_timestamps_only_segment_granularity(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({"segments": []}))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        await port.transcribe_batch(
            AudioRef(local_path=self._audio_path),
            BatchOptions(diarization=False, word_timestamps=False, language=None),
        )

        data = client.calls[0]["data"]
        self.assertNotIn("diarize", data)
        self.assertEqual(data["timestamp_granularities[]"], ["segment"])

    async def test_diarization_true_sets_diarize_form_field(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({"segments": []}))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions(diarization=True))

        self.assertEqual(client.calls[0]["data"]["diarize"], "true")


class TranscribeBatchErrorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._audio_path = _tmp_audio_file()
        self.addCleanup(remove_if_exists, self._audio_path)

    async def test_missing_local_path_raises_value_error(self) -> None:
        port = VoxtralApiTranscriptionPort(default_settings())
        with self.assertRaises(ValueError):
            await port.transcribe_batch(AudioRef(stream_source="mic-1"), BatchOptions())

    async def test_http_failure_is_translated_to_batch_error(self) -> None:
        client = _FakeHttpClient(raises=RuntimeError("Netz kaputt"))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        with self.assertRaises(VoxtralBatchTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_non_2xx_status_is_translated_to_batch_error(self) -> None:
        client = _FakeHttpClient(response=_FakeResponse({}, status_ok=False))
        port = VoxtralApiTranscriptionPort(default_settings(), http_client=client)  # type: ignore[arg-type]

        with self.assertRaises(VoxtralBatchTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_without_injected_client_owns_and_closes_its_own_client(self) -> None:
        fake_client = _FakeHttpClient(response=_FakeResponse({"segments": []}))

        with mock.patch(
            "souffleur.adapters.stt.voxtral_api.httpx.AsyncClient", return_value=fake_client
        ):
            port = VoxtralApiTranscriptionPort(default_settings())
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertTrue(fake_client.aclose_called)


class CapabilitiesTest(unittest.TestCase):
    def test_capabilities_report_eu_diarization_and_word_timestamps(self) -> None:
        port = VoxtralApiTranscriptionPort(default_settings())
        capabilities = port.capabilities()
        self.assertTrue(capabilities.supports_streaming)
        self.assertTrue(capabilities.supports_diarization)
        # LIVE verifiziert: Batch liefert nur Segment-Ebene (word -> HTTP 422)
        self.assertFalse(capabilities.supports_word_timestamps)
        self.assertEqual(capabilities.residency, "EU")


if __name__ == "__main__":
    unittest.main()
