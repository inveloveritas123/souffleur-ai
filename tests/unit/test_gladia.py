"""Unit-Tests adapters/stt/gladia.py — EU-Fallback-Adapter (Upload -> Transcription -> Poll)."""
from __future__ import annotations

import tempfile
import unittest
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings, remove_if_exists  # noqa: E402
from souffleur.adapters.stt.gladia import (  # noqa: E402
    GladiaApiKeyMissingError,
    GladiaTranscriptionError,
    GladiaTranscriptionPort,
    NonEuGladiaEndpointError,
)
from souffleur.ports.types import AudioRef, BatchOptions, SessionContext, StreamHandle  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeGladiaHttpClient:
    """Beantwortet `POST /v2/upload`, `POST /v2/transcription` und `GET <result_url>`."""

    def __init__(
        self,
        upload_response: dict[str, Any],
        transcription_response: dict[str, Any],
        poll_responses: list[dict[str, Any]],
    ) -> None:
        self._upload_response = upload_response
        self._transcription_response = transcription_response
        self._poll_responses = list(poll_responses)
        self.post_calls: list[tuple[str, dict]] = []
        self.get_calls: list[str] = []

    async def post(self, path: str, *, headers: dict, **kwargs: Any) -> _FakeResponse:
        self.post_calls.append((path, kwargs))
        if path == "/v2/upload":
            return _FakeResponse(self._upload_response)
        if path == "/v2/transcription":
            return _FakeResponse(self._transcription_response)
        raise AssertionError(f"unerwarteter POST-Pfad: {path}")

    async def get(self, url: str, *, headers: dict) -> _FakeResponse:
        self.get_calls.append(url)
        response = self._poll_responses.pop(0)
        return _FakeResponse(response)


def _tmp_audio_file() -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(b"fake-audio")
    handle.close()
    return handle.name


class GladiaConstructorTest(unittest.TestCase):
    def test_default_eu_base_url_is_accepted(self) -> None:
        port = GladiaTranscriptionPort(default_settings())
        self.assertIsNotNone(port)

    def test_non_eu_base_url_raises(self) -> None:
        settings = default_settings(gladia_base_url="https://gladia.example.com")
        with self.assertRaises(NonEuGladiaEndpointError):
            GladiaTranscriptionPort(settings)

    def test_capabilities(self) -> None:
        port = GladiaTranscriptionPort(default_settings())
        capabilities = port.capabilities()
        self.assertFalse(capabilities.supports_streaming)
        self.assertTrue(capabilities.supports_diarization)
        self.assertEqual(capabilities.residency, "EU")


class GladiaLiveStreamingNotImplementedTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_push_close_raise_not_implemented(self) -> None:
        port = GladiaTranscriptionPort(default_settings())
        session = SessionContext(
            tenant_id="t1", session_id="s1", consent_ref="c1", sample_rate=16000, channels=2
        )
        with self.assertRaises(NotImplementedError):
            await port.open_stream(session)
        with self.assertRaises(NotImplementedError):
            await port.push_audio(StreamHandle(provider_handle="h", correlation_id="h"), b"\x00")
        with self.assertRaises(NotImplementedError):
            await port.close_stream(StreamHandle(provider_handle="h", correlation_id="h"))

    async def test_events_raises_not_implemented_on_first_iteration(self) -> None:
        port = GladiaTranscriptionPort(default_settings())
        with self.assertRaises(NotImplementedError):
            async for _event in port.events(StreamHandle(provider_handle="h", correlation_id="h")):
                pass


class GladiaTranscribeBatchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._audio_path = _tmp_audio_file()
        self.addCleanup(remove_if_exists, self._audio_path)

    async def test_missing_local_path_raises_value_error(self) -> None:
        port = GladiaTranscriptionPort(default_settings(gladia_api_key="k"))
        with self.assertRaises(ValueError):
            await port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions())

    async def test_missing_api_key_raises_before_any_http_call(self) -> None:
        port = GladiaTranscriptionPort(default_settings(gladia_api_key=None))
        with self.assertRaises(GladiaApiKeyMissingError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_full_success_path_parses_utterances_and_words(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/files/1"},
            transcription_response={"result_url": "https://api.gladia.io/v2/transcription/1"},
            poll_responses=[
                {"status": "processing"},
                {
                    "status": "done",
                    "result": {
                        "metadata": {"audio_duration": 5.0},
                        "transcription": {
                            "utterances": [
                                {
                                    "speaker": 0,
                                    "text": "Hallo",
                                    "start": 0.0,
                                    "end": 1.0,
                                    "words": [{"word": "Hallo", "start": 0.0, "end": 1.0}],
                                },
                                {"speaker_id": "1", "text": "Servus", "start": 1.0, "end": 2.0},
                            ]
                        },
                    },
                },
            ],
        )
        settings = default_settings(gladia_api_key="real-key")
        port = GladiaTranscriptionPort(settings, client=client, poll_interval_s=0, max_polls=5)  # type: ignore[arg-type]

        result = await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

        self.assertEqual(result.provider, "gladia")
        self.assertEqual(result.duration_ms, 5000)
        self.assertEqual(result.speakers, ["0", "1"])
        self.assertEqual(result.segments[0].words[0].text, "Hallo")  # type: ignore[index]
        self.assertEqual(client.post_calls[0][0], "/v2/upload")
        self.assertEqual(client.post_calls[1][0], "/v2/transcription")

    async def test_upload_without_audio_url_raises(self) -> None:
        client = _FakeGladiaHttpClient(upload_response={}, transcription_response={}, poll_responses=[])
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0  # type: ignore[arg-type]
        )
        with self.assertRaises(GladiaTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_transcription_without_result_url_raises(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/f/1"},
            transcription_response={},
            poll_responses=[],
        )
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0  # type: ignore[arg-type]
        )
        with self.assertRaises(GladiaTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_non_eu_result_url_raises(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/f/1"},
            transcription_response={"result_url": "https://evil.example.com/r/1"},
            poll_responses=[],
        )
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0  # type: ignore[arg-type]
        )
        with self.assertRaises(NonEuGladiaEndpointError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_poll_status_error_raises(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/f/1"},
            transcription_response={"result_url": "https://api.gladia.io/r/1"},
            poll_responses=[{"status": "error", "error": "boom"}],
        )
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0  # type: ignore[arg-type]
        )
        with self.assertRaises(GladiaTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_poll_exhaustion_raises(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/f/1"},
            transcription_response={"result_url": "https://api.gladia.io/r/1"},
            poll_responses=[{"status": "processing"}, {"status": "processing"}],
        )
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0, max_polls=2  # type: ignore[arg-type]
        )
        with self.assertRaises(GladiaTranscriptionError):
            await port.transcribe_batch(AudioRef(local_path=self._audio_path), BatchOptions())

    async def test_diarization_options_and_language_and_speaker_hint_are_forwarded(self) -> None:
        client = _FakeGladiaHttpClient(
            upload_response={"audio_url": "https://api.gladia.io/f/1"},
            transcription_response={"result_url": "https://api.gladia.io/r/1"},
            poll_responses=[{"status": "done", "result": {"transcription": {"utterances": []}}}],
        )
        port = GladiaTranscriptionPort(
            default_settings(gladia_api_key="k"), client=client, poll_interval_s=0  # type: ignore[arg-type]
        )

        result = await port.transcribe_batch(
            AudioRef(local_path=self._audio_path),
            BatchOptions(diarization=True, language="de", num_speakers_hint=2),
        )

        transcription_kwargs = client.post_calls[1][1]
        self.assertEqual(transcription_kwargs["json"]["language"], "de")
        self.assertEqual(transcription_kwargs["json"]["diarization_config"], {"number_of_speakers": 2})
        self.assertEqual(result.speakers, ["unknown"])  # keine Utterances -> Fallback


if __name__ == "__main__":
    unittest.main()
