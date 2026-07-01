"""gladia — EU-Drop-in-Fallback-STT-Adapter (Frankreich), Batch.

Tests mocken `httpx` vollständig über einen injizierten Fake-Client (Dependency-
Injection via `client=`-Konstruktor-Parameter) — keine echten Netzaufrufe, kein
`GLADIA_API_KEY` nötig außer für die Tests, die genau diese Validierung prüfen
(Gate E1/E2: keine Netz-/Modellaufrufe in Tests).
"""
from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any

import httpx
import pytest
from souffleur.adapters.stt.factory import build_transcription_port
from souffleur.adapters.stt.gladia import (
    GladiaApiKeyMissingError,
    GladiaTranscriptionError,
    GladiaTranscriptionPort,
    NonEuGladiaEndpointError,
)
from souffleur.core.settings import Settings
from souffleur.ports.transcription import TranscriptionPort
from souffleur.ports.types import AudioRef, BatchOptions


def _settings(*, gladia_api_key: str | None = "test-key", gladia_base_url: str = "https://api.gladia.io") -> Settings:
    return Settings(
        mistral_api_key=None,
        mistral_base_url="https://api.mistral.ai",
        stt_provider="gladia",
        model_stt_live="voxtral-mini-transcribe-realtime-2602",
        model_stt_batch="voxtral-mini-2602",
        model_reasoning="magistral-medium-2509",
        model_trigger="ministral-3b-2512",
        gladia_api_key=gladia_api_key,
        gladia_base_url=gladia_base_url,
        voxtral_local_url="http://voxtral-worker:9000",
        mcp_url="http://coaching-mcp:8080",
        backend_port=8000,
        web_port=5173,
        mcp_port=8080,
        tenant_id="zukunftsbund",
        audit_log_path="./data/audit-log.jsonl",
        retention_days=30,
        require_consent=True,
    )


class _FakeResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.gladia.io/v2/upload")
            raise httpx.HTTPStatusError(
                "fake error", request=request, response=httpx.Response(self.status_code, request=request)
            )

    def json(self) -> dict[str, Any]:
        return self._json_data


class _FakeClient:
    """Ersetzt `httpx.AsyncClient` — gibt vordefinierte Antworten zurück, ohne Netz."""

    def __init__(self, post_responses: list[_FakeResponse], get_responses: list[_FakeResponse]) -> None:
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.post_calls.append((url, kwargs))
        return self._post_responses.pop(0)

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.get_calls.append((url, kwargs))
        return self._get_responses.pop(0)


def _gladia_result_payload() -> dict[str, Any]:
    return {
        "status": "done",
        "result": {
            "metadata": {"audio_duration": 5.0},
            "transcription": {
                "utterances": [
                    {
                        "text": "Ich verstehe Ihren Einwand.",
                        "start": 0.0,
                        "end": 2.5,
                        "speaker": 0,
                        "words": [
                            {"word": "Ich", "start": 0.0, "end": 0.3},
                            {"word": "verstehe", "start": 0.3, "end": 0.9},
                        ],
                    },
                    {
                        "text": "Das Budget ist mir zu hoch.",
                        "start": 2.5,
                        "end": 5.0,
                        "speaker": 1,
                        "words": [{"word": "Das", "start": 2.5, "end": 2.7}],
                    },
                ]
            },
        },
    }


def test_constructor_rejects_non_eu_base_url() -> None:
    settings = _settings(gladia_base_url="https://api.us-east.gladia.io")

    with pytest.raises(NonEuGladiaEndpointError):
        GladiaTranscriptionPort(settings, client=_FakeClient([], []))


def test_capabilities_report_eu_residency_and_diarization_support() -> None:
    port = GladiaTranscriptionPort(_settings(), client=_FakeClient([], []))

    caps = port.capabilities()

    assert caps.residency == "EU"
    assert caps.supports_diarization is True
    assert caps.supports_word_timestamps is True


@pytest.mark.asyncio
async def test_transcribe_batch_requires_local_path() -> None:
    port = GladiaTranscriptionPort(_settings(), client=_FakeClient([], []))

    with pytest.raises(ValueError):
        await port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions())


@pytest.mark.asyncio
async def test_transcribe_batch_raises_clear_error_without_api_key(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_client = _FakeClient([], [])
    port = GladiaTranscriptionPort(_settings(gladia_api_key=None), client=fake_client)

    with pytest.raises(GladiaApiKeyMissingError):
        await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    # Ohne Key darf nicht einmal der Upload versucht werden.
    assert fake_client.post_calls == []


@pytest.mark.asyncio
async def test_transcribe_batch_happy_path_parses_diarized_result(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_client = _FakeClient(
        post_responses=[
            _FakeResponse({"audio_url": "https://api.gladia.io/files/abc.wav"}),
            _FakeResponse({"id": "job1", "result_url": "https://api.gladia.io/v2/transcription/job1"}),
        ],
        get_responses=[_FakeResponse(_gladia_result_payload())],
    )
    port = GladiaTranscriptionPort(_settings(), client=fake_client, poll_interval_s=0)

    result = await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    assert result.provider == "gladia"
    assert result.model == "gladia-v2"
    assert result.speakers == ["0", "1"]
    assert len(result.segments) == 2

    first = result.segments[0]
    assert first.speaker == "0"
    assert first.t_start_ms == 0
    assert first.t_end_ms == 2500
    assert first.words is not None
    assert first.words[0].text == "Ich"
    assert first.words[0].t_start_ms == 0
    assert first.words[0].t_end_ms == 300

    assert result.duration_ms == 5000

    # Auth-Header korrekt (Gladia: x-gladia-key, KEIN Bearer-Token).
    upload_url, upload_kwargs = fake_client.post_calls[0]
    assert upload_url == "/v2/upload"
    assert upload_kwargs["headers"]["x-gladia-key"] == "test-key"
    start_url, start_kwargs = fake_client.post_calls[1]
    assert start_url == "/v2/transcription"
    assert start_kwargs["headers"]["x-gladia-key"] == "test-key"
    assert start_kwargs["json"]["audio_url"] == "https://api.gladia.io/files/abc.wav"
    assert start_kwargs["json"]["diarization"] is True


@pytest.mark.asyncio
async def test_transcribe_batch_polls_until_done(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_client = _FakeClient(
        post_responses=[
            _FakeResponse({"audio_url": "https://api.gladia.io/files/abc.wav"}),
            _FakeResponse({"id": "job1", "result_url": "https://api.gladia.io/v2/transcription/job1"}),
        ],
        get_responses=[
            _FakeResponse({"status": "processing"}),
            _FakeResponse({"status": "processing"}),
            _FakeResponse(_gladia_result_payload()),
        ],
    )
    port = GladiaTranscriptionPort(_settings(), client=fake_client, poll_interval_s=0)

    result = await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    assert len(fake_client.get_calls) == 3
    assert result.provider == "gladia"


@pytest.mark.asyncio
async def test_transcribe_batch_raises_on_job_error_status(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_client = _FakeClient(
        post_responses=[
            _FakeResponse({"audio_url": "https://api.gladia.io/files/abc.wav"}),
            _FakeResponse({"id": "job1", "result_url": "https://api.gladia.io/v2/transcription/job1"}),
        ],
        get_responses=[_FakeResponse({"status": "error", "error": "boom"})],
    )
    port = GladiaTranscriptionPort(_settings(), client=fake_client, poll_interval_s=0)

    with pytest.raises(GladiaTranscriptionError, match="boom"):
        await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())


@pytest.mark.asyncio
async def test_transcribe_batch_rejects_non_eu_result_url(tmp_path: Any) -> None:
    """Defensive EU-Prüfung (Gate E1): selbst eine vom Server gelieferte Non-EU-URL wird abgelehnt."""
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_client = _FakeClient(
        post_responses=[
            _FakeResponse({"audio_url": "https://api.gladia.io/files/abc.wav"}),
            _FakeResponse({"id": "job1", "result_url": "https://api.us.example.com/v2/transcription/job1"}),
        ],
        get_responses=[],
    )
    port = GladiaTranscriptionPort(_settings(), client=fake_client, poll_interval_s=0)

    with pytest.raises(NonEuGladiaEndpointError):
        await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())


@pytest.mark.asyncio
async def test_live_stream_methods_raise_clear_not_implemented_error() -> None:
    port = GladiaTranscriptionPort(_settings(), client=_FakeClient([], []))

    with pytest.raises(NotImplementedError):
        await port.open_stream(session=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await port.push_audio(handle=None, pcm_chunk=b"")  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await port.close_stream(handle=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        async for _ in port.events(handle=None):  # type: ignore[arg-type]
            pass


def test_factory_builds_gladia_without_requiring_api_key_at_construction() -> None:
    """Die Factory wählt den echten `gladia`-Adapter rein über Config; Instanziierung allein
    braucht noch keinen API-Key (erst `transcribe_batch` prüft ihn)."""
    settings = _settings(gladia_api_key=None)

    port = build_transcription_port(settings)

    assert isinstance(port, GladiaTranscriptionPort)
    assert isinstance(port, TranscriptionPort)
    caps = port.capabilities()
    assert caps.residency == "EU"


def test_factory_does_not_touch_network_module_state() -> None:
    """Reine Sicherheits-Kontrolle: das Bauen des Adapters importiert kein mlx-Paket."""
    settings = _settings(gladia_api_key=None)

    build_transcription_port(settings)

    assert "mlx_audio" not in sys.modules
    assert "mlx_voxtral" not in sys.modules


def test_settings_replace_keeps_eu_check_meaningful() -> None:
    """Stellt sicher, dass `replace()` (Standard-Testmuster im Projekt) wirklich einen
    Non-EU-Wert erzeugt, den der Adapter ablehnt — keine triviale No-Op-Prüfung."""
    eu_settings = _settings()
    non_eu_settings = replace(eu_settings, gladia_base_url="https://eu-west-1.gladia.example.com")

    assert eu_settings.gladia_base_url != non_eu_settings.gladia_base_url
    with pytest.raises(NonEuGladiaEndpointError):
        GladiaTranscriptionPort(non_eu_settings, client=_FakeClient([], []))
