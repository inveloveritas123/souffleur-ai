"""Welle 3 — TranscriptionPort-Factory: Provider-Wechsel allein über SOUFFLEUR_STT_PROVIDER.

Die echten Adapter-Implementierungen (voxtral_api, voxtral_local, gladia) folgen erst in
späteren Wellen (W4/W12/...). Dieser Test fälscht die drei Adapter-Module über `sys.modules`,
damit `build_transcription_port` schon jetzt — ohne Codeänderung an der Factory — gegen alle
drei Provider-Werte grün läuft (Akzeptanzkriterium Welle 3).
"""
from __future__ import annotations

import sys
import types
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest
from souffleur.adapters.stt.factory import UnknownSttProviderError, build_transcription_port
from souffleur.core.settings import Settings
from souffleur.ports.transcription import TranscriptionPort
from souffleur.ports.types import (
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    StreamHandle,
    TranscriptEvent,
    TranscriptResult,
)


def _base_settings(provider: str) -> Settings:
    return Settings(
        mistral_api_key="test-key",
        mistral_base_url="https://api.mistral.ai",
        stt_provider=provider,
        model_stt_live="voxtral-mini-realtime-2602",
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


def _make_fake_adapter_class(label: str, class_name: str) -> type:
    """Baut eine Klasse, die das TranscriptionPort-Protocol vollständig erfüllt."""

    class _FakeAdapter:
        label_ = label

        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def open_stream(self, session: object) -> StreamHandle:
            return StreamHandle(provider_handle="fake", correlation_id="fake-corr")

        async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None:
            return None

        async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]:
            return
            yield  # pragma: no cover - macht die Methode zum Async-Generator

        async def close_stream(self, handle: StreamHandle) -> TranscriptResult:
            return TranscriptResult(segments=[], speakers=[], duration_ms=0, model="fake", provider=label)

        async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
            return TranscriptResult(segments=[], speakers=[], duration_ms=0, model="fake", provider=label)

        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(
                supports_streaming=True, supports_diarization=True,
                supports_word_timestamps=True, typical_final_latency_ms=300, residency="EU",
            )

    _FakeAdapter.__name__ = class_name
    return _FakeAdapter


def _install_fake_adapter_module(
    monkeypatch: pytest.MonkeyPatch, module_path: str, class_name: str, label: str
) -> None:
    """Setzt ein Fake-Modul in sys.modules — importlib.import_module nutzt den Cache."""
    module = types.ModuleType(module_path)
    setattr(module, class_name, _make_fake_adapter_class(label, class_name))
    monkeypatch.setitem(sys.modules, module_path, module)


@pytest.mark.parametrize(
    ("provider", "module_path", "class_name"),
    [
        ("voxtral_api", "souffleur.adapters.stt.voxtral_api", "VoxtralApiTranscriptionPort"),
        ("voxtral_local", "souffleur.adapters.stt.voxtral_local", "VoxtralLocalTranscriptionPort"),
        ("gladia", "souffleur.adapters.stt.gladia", "GladiaTranscriptionPort"),
    ],
)
def test_factory_instantiates_adapter_purely_via_provider_config(
    monkeypatch: pytest.MonkeyPatch, provider: str, module_path: str, class_name: str
) -> None:
    """build_transcription_port wählt den Adapter ausschließlich über SOUFFLEUR_STT_PROVIDER."""
    _install_fake_adapter_module(monkeypatch, module_path, class_name, provider)

    settings = _base_settings(provider)
    port = build_transcription_port(settings)

    assert isinstance(port, TranscriptionPort)
    assert type(port).__name__ == class_name
    assert port.settings is settings  # type: ignore[attr-defined]
    caps = port.capabilities()
    assert caps.residency == "EU"


def test_factory_switching_provider_requires_no_code_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """Derselbe Factory-Aufruf liefert je nach Config einen anderen Adapter-Typ."""
    _install_fake_adapter_module(
        monkeypatch, "souffleur.adapters.stt.voxtral_api", "VoxtralApiTranscriptionPort", "voxtral_api"
    )
    _install_fake_adapter_module(
        monkeypatch, "souffleur.adapters.stt.gladia", "GladiaTranscriptionPort", "gladia"
    )

    port_a = build_transcription_port(_base_settings("voxtral_api"))
    port_b = build_transcription_port(_base_settings("gladia"))

    assert type(port_a) is not type(port_b)


def test_factory_rejects_unknown_provider_with_clear_error() -> None:
    """Ein unbekannter SOUFFLEUR_STT_PROVIDER-Wert führt zu einem eindeutigen Fehler."""
    settings = replace(_base_settings("voxtral_api"), stt_provider="azure_whisper")

    with pytest.raises(UnknownSttProviderError, match="azure_whisper"):
        build_transcription_port(settings)
