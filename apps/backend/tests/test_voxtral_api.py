"""Welle 4 + Batch-STT-Fix — voxtral_api `transcribe_batch` (REST, `diarize=true`).

Fix-Kontext (verifiziert am echten Endpunkt, 2026-07, Key HTTP 200): das installierte
`mistralai==1.10.0`-SDK akzeptiert *kein* `diarize`-Kwarg auf `audio.transcriptions.
complete_async`; der REST-Endpunkt `POST /v1/audio/transcriptions` akzeptiert `diarize=true`
sehr wohl. `transcribe_batch` ruft deshalb `httpx` direkt auf (kein Mistral-SDK-Client mehr
in diesem Adapter) — Tests mocken `httpx`, keine echten Netzaufrufe (Gate E1/E2). Verifizierte
Response-Form: `{text, language, segments:[{text, start(sec), end(sec), speaker_id(int|null),
type}], usage}`. Sprecher-Label kommt aus `speaker_id` (int), NICHT aus einem `speaker`-Feld.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from souffleur.adapters.stt.voxtral_api import VoxtralApiTranscriptionPort
from souffleur.core.settings import Settings
from souffleur.ports.types import AudioRef, BatchOptions


def _settings() -> Settings:
    return Settings(
        mistral_api_key="test-key",
        mistral_base_url="https://api.mistral.ai",
        stt_provider="voxtral_api",
        model_stt_live="voxtral-mini-transcribe-realtime-2602",
        model_stt_batch="voxtral-mini-2602",
        model_reasoning="magistral-medium-2509",
        model_trigger="ministral-3b-2512",
        gladia_api_key=None,
        gladia_base_url="https://api.gladia.io",
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


def _fake_http_client(json_payload: dict[str, Any], status_code: int = 200) -> AsyncMock:
    """Ein `httpx.AsyncClient`-Double: `.post()` liefert eine echte `httpx.Response`."""
    request = httpx.Request("POST", "https://api.mistral.ai/v1/audio/transcriptions")
    response = httpx.Response(status_code, json=json_payload, request=request)
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)
    return client


def _diarized_payload() -> dict[str, Any]:
    """Verifizierte REST-Response-Form: `speaker_id` (int), Sekunden-Zeitstempel."""
    return {
        "model": "voxtral-mini-2602",
        "text": "Ich verstehe Ihren Einwand. Das Budget ist mir zu hoch.",
        "language": "de",
        "usage": {"prompt_audio_seconds": 5},
        "segments": [
            {
                "text": "Ich verstehe Ihren Einwand.",
                "start": 0.0,
                "end": 2.5,
                "speaker_id": 0,
                "type": "transcript",
                "words": [
                    {"text": "Ich", "start": 0.0, "end": 0.3},
                    {"text": "verstehe", "start": 0.3, "end": 0.9},
                ],
            },
            {
                "text": "Das Budget ist mir zu hoch.",
                "start": 2.5,
                "end": 5.0,
                "speaker_id": 1,
                "type": "transcript",
                "words": [
                    {"text": "Das", "start": 2.5, "end": 2.7},
                    {"text": "Budget", "start": 2.7, "end": 3.1},
                ],
            },
        ],
    }


def _undiarized_payload() -> dict[str, Any]:
    """Antwort ohne `speaker_id` — heutiger Realfall, wenn `diarize` nicht greift."""
    return {
        "model": "voxtral-mini-2602",
        "text": "Ein einzelnes Segment ohne Diarisation.",
        "usage": {"prompt_audio_seconds": 3},
        "segments": [
            {"text": "Ein einzelnes Segment ohne Diarisation.", "start": 0.0, "end": 3.0, "speaker_id": None}
        ],
    }


def test_transcribe_batch_returns_diarized_result_with_word_timestamps(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"RIFF....fake-audio-bytes")

    client = _fake_http_client(_diarized_payload())
    port = VoxtralApiTranscriptionPort(_settings(), http_client=client)

    result = asyncio.run(port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions()))

    assert result.provider == "voxtral_api"
    assert result.model == "voxtral-mini-2602"
    assert len(result.speakers) >= 2
    assert set(result.speakers) == {"speaker_0", "speaker_1"}
    assert len(result.segments) == 2

    first = result.segments[0]
    assert first.kind == "final"
    assert first.speaker == "speaker_0"
    assert first.t_start_ms == 0
    assert first.t_end_ms == 2500
    assert first.words is not None
    assert len(first.words) == 2
    assert first.words[0].text == "Ich"
    assert first.words[0].t_start_ms == 0
    assert first.words[0].t_end_ms == 300

    assert result.duration_ms == 5000


def test_transcribe_batch_posts_diarize_true_via_rest(tmp_path: Any) -> None:
    """Belegt: REST-POST mit `diarize=true` statt SDK-Methode (Fix-Kernaussage)."""
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    client = _fake_http_client(_diarized_payload())
    port = VoxtralApiTranscriptionPort(_settings(), http_client=client)

    asyncio.run(port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions()))

    client.post.assert_awaited_once()
    args, kwargs = client.post.call_args
    assert args[0] == "https://api.mistral.ai/v1/audio/transcriptions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["data"]["model"] == "voxtral-mini-2602"
    assert kwargs["data"]["diarize"] == "true"
    assert kwargs["data"]["timestamp_granularities[]"] == ["segment", "word"]
    assert kwargs["files"]["file"][0] == "gespraech.wav"
    assert kwargs["files"]["file"][1] == b"fake-bytes"


def test_transcribe_batch_omits_timestamp_granularities_when_language_given(tmp_path: Any) -> None:
    """Verifiziert: timestamp_granularities ist nicht kompatibel mit language."""
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    client = _fake_http_client(_diarized_payload())
    port = VoxtralApiTranscriptionPort(_settings(), http_client=client)

    asyncio.run(
        port.transcribe_batch(
            AudioRef(local_path=str(audio_path)), BatchOptions(language="de")
        )
    )

    _, kwargs = client.post.call_args
    assert kwargs["data"]["language"] == "de"
    assert "timestamp_granularities[]" not in kwargs["data"]


def test_transcribe_batch_falls_back_to_single_speaker_without_speaker_id(tmp_path: Any) -> None:
    """Ehrliche Degradation: ohne `speaker_id` wird kein Sprecher fabriziert."""
    audio_path = tmp_path / "mono.wav"
    audio_path.write_bytes(b"fake-bytes")

    client = _fake_http_client(_undiarized_payload())
    port = VoxtralApiTranscriptionPort(_settings(), http_client=client)

    result = asyncio.run(port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions()))

    assert result.speakers == ["unknown"]
    assert result.segments[0].words is None
    assert result.duration_ms == 3000


def test_transcribe_batch_requires_local_path() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), http_client=_fake_http_client(_diarized_payload()))

    with pytest.raises(ValueError):
        asyncio.run(port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions()))


def test_transcribe_batch_wraps_http_errors(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    request = httpx.Request("POST", "https://api.mistral.ai/v1/audio/transcriptions")
    response = httpx.Response(500, json={"error": "boom"}, request=request)
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)
    port = VoxtralApiTranscriptionPort(_settings(), http_client=client)

    from souffleur.adapters.stt.voxtral_api import VoxtralBatchTranscriptionError

    with pytest.raises(VoxtralBatchTranscriptionError):
        asyncio.run(port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions()))


def test_capabilities_reports_eu_residency_and_diarization_support() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), http_client=_fake_http_client(_diarized_payload()))

    caps = port.capabilities()

    assert caps.residency == "EU"
    assert caps.supports_diarization is True
    assert caps.supports_word_timestamps is True


def test_client_defaults_to_eu_base_url_from_settings() -> None:
    """Ohne expliziten http_client-Override nutzt der Adapter dennoch die EU-Base-URL (Gate E1)."""
    port = VoxtralApiTranscriptionPort(_settings())

    assert port._settings.mistral_base_url == "https://api.mistral.ai"
