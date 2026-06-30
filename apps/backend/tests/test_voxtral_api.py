"""Welle 4 — STT-Adapter voxtral_api (Batch, Phase 1).

Verifiziert gegen das installierte `mistralai`-SDK (1.10.0): `Mistral().audio.transcriptions
.complete_async` akzeptiert in dieser SDK-Version *kein* `diarize`- oder `context_bias`-Kwarg
und `timestamp_granularities` ist auf `Literal["segment"]` typisiert (per `inspect.signature`
verifiziert) — abweichend vom MISTRAL-API-CHEATSHEET. Der Adapter ruft daher nur Parameter auf,
die die installierte SDK-Methode tatsächlich entgegennimmt (sonst TypeError im Echtbetrieb),
und parst Diarisation/Wort-Zeitstempel defensiv aus etwaigen Zusatzfeldern der Antwort
(Pydantic `extra="allow"` auf den Response-Modellen lässt das zu). Tests mocken den Client
vollständig — keine echten Netzaufrufe (Gate E1/E2).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

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


def _fake_client(response: object) -> SimpleNamespace:
    transcriptions = SimpleNamespace(complete_async=AsyncMock(return_value=response))
    audio = SimpleNamespace(transcriptions=transcriptions)
    return SimpleNamespace(audio=audio)


def _diarized_response() -> SimpleNamespace:
    """Antwortform, die der Cheatsheet-Vertrag (diarize + word timestamps) verspricht.

    Da `speaker`/`words` keine getypten Felder der installierten SDK-Response-Modelle sind,
    kommen sie (sofern die Live-API sie liefert) als Pydantic-Extra-Felder durch — im Mock
    hier als einfache Attribute/Dicts nachgebildet.
    """
    segment_a = SimpleNamespace(
        text="Ich verstehe Ihren Einwand.",
        start=0.0,
        end=2.5,
        speaker="coach",
        words=[
            {"text": "Ich", "start": 0.0, "end": 0.3},
            {"text": "verstehe", "start": 0.3, "end": 0.9},
        ],
    )
    segment_b = SimpleNamespace(
        text="Das Budget ist mir zu hoch.",
        start=2.5,
        end=5.0,
        speaker="counterpart",
        words=[
            {"text": "Das", "start": 2.5, "end": 2.7},
            {"text": "Budget", "start": 2.7, "end": 3.1},
        ],
    )
    return SimpleNamespace(
        model="voxtral-mini-2602",
        text="Ich verstehe Ihren Einwand. Das Budget ist mir zu hoch.",
        segments=[segment_a, segment_b],
        usage=SimpleNamespace(prompt_audio_seconds=5),
    )


def _undiarized_response() -> SimpleNamespace:
    """Antwort ohne Sprecher-/Wort-Zusatzfelder — heutiger Realfall (SDK-Limitierung)."""
    segment = SimpleNamespace(text="Ein einzelnes Segment ohne Diarisation.", start=0.0, end=3.0)
    return SimpleNamespace(
        model="voxtral-mini-2602",
        text="Ein einzelnes Segment ohne Diarisation.",
        segments=[segment],
        usage=SimpleNamespace(prompt_audio_seconds=3),
    )


def test_transcribe_batch_returns_diarized_result_with_word_timestamps(tmp_path) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"RIFF....fake-audio-bytes")

    client = _fake_client(_diarized_response())
    port = VoxtralApiTranscriptionPort(_settings(), client=client)

    import asyncio

    result = asyncio.run(
        port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())
    )

    assert result.provider == "voxtral_api"
    assert result.model == "voxtral-mini-2602"
    assert len(result.speakers) >= 2
    assert set(result.speakers) == {"coach", "counterpart"}
    assert len(result.segments) == 2

    first = result.segments[0]
    assert first.kind == "final"
    assert first.speaker == "coach"
    assert first.t_start_ms == 0
    assert first.t_end_ms == 2500
    assert first.words is not None
    assert len(first.words) == 2
    assert first.words[0].text == "Ich"
    assert first.words[0].t_start_ms == 0
    assert first.words[0].t_end_ms == 300

    assert result.duration_ms == 5000


def test_transcribe_batch_calls_sdk_with_only_supported_kwargs(tmp_path) -> None:
    """Belegt, dass `diarize`/`context_bias` NICHT übergeben werden (installierte SDK kennt sie nicht)."""
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    client = _fake_client(_diarized_response())
    port = VoxtralApiTranscriptionPort(_settings(), client=client)

    import asyncio

    asyncio.run(port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions()))

    call = client.audio.transcriptions.complete_async
    call.assert_awaited_once()
    _, kwargs = call.call_args
    assert kwargs["model"] == "voxtral-mini-2602"
    assert kwargs["file"]["file_name"] == "gespraech.wav"
    assert kwargs["file"]["content"] == b"fake-bytes"
    assert "diarize" not in kwargs
    assert "context_bias" not in kwargs
    assert kwargs["timestamp_granularities"] == ["segment"]


def test_transcribe_batch_falls_back_to_single_speaker_without_diarization_data(tmp_path) -> None:
    """Ehrliche Degradation: ohne Diarisations-Zusatzfelder wird kein Sprecher fabriziert."""
    audio_path = tmp_path / "mono.wav"
    audio_path.write_bytes(b"fake-bytes")

    client = _fake_client(_undiarized_response())
    port = VoxtralApiTranscriptionPort(_settings(), client=client)

    import asyncio

    result = asyncio.run(
        port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())
    )

    assert result.speakers == ["unknown"]
    assert result.segments[0].words is None
    assert result.duration_ms == 3000


def test_transcribe_batch_requires_local_path() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), client=_fake_client(_diarized_response()))

    import asyncio

    with pytest.raises(ValueError):
        asyncio.run(
            port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions())
        )


def test_capabilities_reports_eu_residency_and_diarization_support() -> None:
    port = VoxtralApiTranscriptionPort(_settings(), client=_fake_client(_diarized_response()))

    caps = port.capabilities()

    assert caps.residency == "EU"
    assert caps.supports_diarization is True
    assert caps.supports_word_timestamps is True


def test_live_stream_methods_are_not_yet_implemented() -> None:
    """Phase-2-Live-Streaming folgt erst in Welle 12 — hier nur Protocol-Stubs."""
    port = VoxtralApiTranscriptionPort(_settings(), client=_fake_client(_diarized_response()))

    import asyncio

    with pytest.raises(NotImplementedError):
        asyncio.run(port.open_stream(session=None))  # type: ignore[arg-type]


def test_client_is_constructed_against_eu_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne expliziten Client-Override baut der Adapter den Mistral-Client selbst (EU, Gate E1)."""
    captured: dict[str, object] = {}

    class _FakeMistral:
        def __init__(self, api_key: str | None = None, server_url: str | None = None) -> None:
            captured["api_key"] = api_key
            captured["server_url"] = server_url

    monkeypatch.setattr("souffleur.adapters.stt.voxtral_api.Mistral", _FakeMistral)

    VoxtralApiTranscriptionPort(_settings())

    assert captured["server_url"] == "https://api.mistral.ai"
    assert captured["api_key"] == "test-key"
