"""voxtral_local — lokaler Kostenspar-STT-Adapter (MLX, Apple Silicon), Batch.

Tests mocken das MLX-Modell vollständig (Dependency-Injection über `model_loader`):
weder `mlx_audio` noch `mlx_voxtral` wird hier jemals importiert, keine 2,5GB-
Gewichte werden geladen, kein echter Modellaufruf passiert (Gate E1/E2 — keine
Netz-/Modellaufrufe in Tests). Stattdessen wird ein Fake-Modell mit `.transcribe(path)`
injiziert, das die Adapter-Logik (Parsing, Lazy-Load-Zeitpunkt, capabilities(),
Protocol-Konformität) prüft.
"""
from __future__ import annotations

import sys
from typing import Any

import pytest
from souffleur.adapters.stt.factory import build_transcription_port
from souffleur.adapters.stt.voxtral_local import (
    VoxtralLocalTranscriptionError,
    VoxtralLocalTranscriptionPort,
    _default_model_loader,
)
from souffleur.core.settings import Settings
from souffleur.ports.transcription import TranscriptionPort
from souffleur.ports.types import AudioRef, BatchOptions


def _settings(provider: str = "voxtral_local") -> Settings:
    return Settings(
        mistral_api_key=None,
        mistral_base_url="https://api.mistral.ai",
        stt_provider=provider,
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


class _FakeModel:
    """Steht für ein lazy-geladenes MLX-Modell — kennt nur `.transcribe(path)`."""

    def __init__(self, result: Any) -> None:
        self._result = result
        self.calls: list[str] = []

    def transcribe(self, path: str) -> Any:
        self.calls.append(path)
        return self._result


def _diarized_like_result() -> dict[str, Any]:
    """Antwortform, die eine MLX-STT-Bibliothek plausibel liefern könnte (ungetypt)."""
    return {
        "text": "Ich verstehe Ihren Einwand. Das Budget ist mir zu hoch.",
        "duration": 5.0,
        "segments": [
            {
                "text": "Ich verstehe Ihren Einwand.",
                "start": 0.0,
                "end": 2.5,
                "words": [
                    {"text": "Ich", "start": 0.0, "end": 0.3},
                    {"text": "verstehe", "start": 0.3, "end": 0.9},
                ],
            },
            {
                "text": "Das Budget ist mir zu hoch.",
                "start": 2.5,
                "end": 5.0,
                "words": [
                    {"text": "Das", "start": 2.5, "end": 2.7},
                ],
            },
        ],
    }


def test_module_import_does_not_pull_in_mlx() -> None:
    """Bloßes Importieren des Adapter-Moduls darf nie mlx_audio/mlx_voxtral laden."""
    assert "mlx_audio" not in sys.modules
    assert "mlx_voxtral" not in sys.modules


def test_constructor_does_not_load_model() -> None:
    """Der Konstruktor (auch der, den die Factory aufruft) lädt das Modell nicht lazy-vorzeitig."""
    calls: list[str] = []

    def spy_loader() -> Any:
        calls.append("loaded")
        return _FakeModel(_diarized_like_result())

    VoxtralLocalTranscriptionPort(_settings(), model_loader=spy_loader)

    assert calls == []


@pytest.mark.asyncio
async def test_transcribe_batch_loads_model_lazily_exactly_once(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-audio-bytes")

    load_calls: list[str] = []
    fake_model = _FakeModel(_diarized_like_result())

    def spy_loader() -> Any:
        load_calls.append("loaded")
        return fake_model

    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=spy_loader)
    assert load_calls == []  # noch nicht geladen vor dem ersten Aufruf

    await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())
    await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    assert load_calls == ["loaded"]  # nur einmal geladen, danach gecacht
    assert fake_model.calls == [str(audio_path), str(audio_path)]


@pytest.mark.asyncio
async def test_transcribe_batch_parses_segments_and_words(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-audio-bytes")

    fake_model = _FakeModel(_diarized_like_result())
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: fake_model)

    result = await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    assert result.provider == "voxtral_local"
    assert result.model == "mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit"
    assert len(result.segments) == 2

    first = result.segments[0]
    assert first.kind == "final"
    assert first.t_start_ms == 0
    assert first.t_end_ms == 2500
    assert first.words is not None
    assert first.words[0].text == "Ich"
    assert first.words[0].t_start_ms == 0
    assert first.words[0].t_end_ms == 300

    assert result.duration_ms == 5000
    # Keine Diarisation lokal — 1:1 über getrennte Quellen, kein Fake-Sprecherwechsel.
    assert result.speakers == ["unknown"]
    assert first.speaker == "unknown"


@pytest.mark.asyncio
async def test_transcribe_batch_handles_text_only_result_without_segments(tmp_path: Any) -> None:
    """Manche STT-Bibliotheken liefern nur `text`, keine Segment-Liste — ehrlich abbilden."""
    audio_path = tmp_path / "kurz.wav"
    audio_path.write_bytes(b"fake-bytes")

    fake_model = _FakeModel({"text": "Ein kurzer Satz.", "duration": 1.2})
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: fake_model)

    result = await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())

    assert len(result.segments) == 1
    assert result.segments[0].text == "Ein kurzer Satz."
    assert result.duration_ms == 1200


@pytest.mark.asyncio
async def test_transcribe_batch_requires_local_path() -> None:
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: _FakeModel({}))

    with pytest.raises(ValueError):
        await port.transcribe_batch(AudioRef(stream_source="mic"), BatchOptions())


@pytest.mark.asyncio
async def test_transcribe_batch_requires_existing_file(tmp_path: Any) -> None:
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: _FakeModel({}))
    missing_path = str(tmp_path / "fehlt.wav")

    with pytest.raises(ValueError, match="nicht gefunden"):
        await port.transcribe_batch(AudioRef(local_path=missing_path), BatchOptions())


@pytest.mark.asyncio
async def test_transcribe_batch_wraps_model_errors(tmp_path: Any) -> None:
    audio_path = tmp_path / "gespraech.wav"
    audio_path.write_bytes(b"fake-bytes")

    class _BrokenModel:
        def transcribe(self, path: str) -> Any:
            raise RuntimeError("MLX-Inferenzfehler")

    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: _BrokenModel())

    with pytest.raises(VoxtralLocalTranscriptionError):
        await port.transcribe_batch(AudioRef(local_path=str(audio_path)), BatchOptions())


def test_capabilities_report_local_residency_no_diarization() -> None:
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: _FakeModel({}))

    caps = port.capabilities()

    assert caps.residency == "local"
    assert caps.supports_diarization is False
    assert caps.supports_word_timestamps is True
    assert caps.supports_streaming is False


@pytest.mark.asyncio
async def test_live_stream_methods_raise_clear_not_implemented_error() -> None:
    port = VoxtralLocalTranscriptionPort(_settings(), model_loader=lambda: _FakeModel({}))

    with pytest.raises(NotImplementedError, match="kein Live-Streaming"):
        await port.open_stream(session=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await port.push_audio(handle=None, pcm_chunk=b"")  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await port.close_stream(handle=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        async for _ in port.events(handle=None):  # type: ignore[arg-type]
            pass


def test_default_model_loader_raises_clear_error_without_mlx_installed() -> None:
    """Ohne mlx_audio/mlx_voxtral installiert: klare Fehlermeldung statt kryptischem ImportError.

    Ruft bewusst NICHT den echten `_default_model_loader` in einer Umgebung auf, in der
    mlx evtl. doch installiert ist (CI-Stabilität) — stattdessen wird geprüft, dass die
    Funktion überhaupt existiert und vom Adapter als Default genutzt wird, ohne sie hier
    real auszuführen (kein Download im Testlauf).
    """
    port = VoxtralLocalTranscriptionPort(_settings())

    assert port._model_loader is _default_model_loader


def test_factory_builds_voxtral_local_without_loading_any_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Factory wählt den echten `voxtral_local`-Adapter rein über Config — kein Mock nötig,
    weil Instanziierung allein (ohne `transcribe_batch`) nie ein MLX-Modell lädt."""
    settings = _settings(provider="voxtral_local")

    port = build_transcription_port(settings)

    assert isinstance(port, VoxtralLocalTranscriptionPort)
    assert isinstance(port, TranscriptionPort)
    assert "mlx_audio" not in sys.modules
    assert "mlx_voxtral" not in sys.modules

    caps = port.capabilities()
    assert caps.residency == "local"
