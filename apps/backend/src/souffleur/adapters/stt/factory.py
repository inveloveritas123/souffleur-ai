"""Factory für `TranscriptionPort`-Adapter — Provider-Wahl allein über Config.

`build_transcription_port` liest ausschließlich `settings.stt_provider`
(`SOUFFLEUR_STT_PROVIDER`) und lädt den passenden Adapter **lazy per Import-String**.
Dadurch kennt kein Aufrufer den konkreten Provider, und ein Adapter-Modul muss erst zur
Laufzeit existieren, in der sein Provider-Wert tatsächlich gewählt wird (voxtral_api folgt
in Welle 4, voxtral_local/gladia in späteren Wellen) — diese Welle deckt nur Port + Factory
ab und rührt die Adapter-Implementierungen selbst nicht an.
"""
from __future__ import annotations

import importlib

from souffleur.core.settings import (
    STT_PROVIDER_GLADIA,
    STT_PROVIDER_VOXTRAL_API,
    STT_PROVIDER_VOXTRAL_LOCAL,
    Settings,
)
from souffleur.ports.transcription import TranscriptionPort

# Provider-Wert -> (Modulpfad, Klassenname). Reine Daten: ein neuer Provider braucht nur
# einen neuen Eintrag hier, niemals eine Änderung an Aufrufer-Code.
_ADAPTER_REGISTRY: dict[str, tuple[str, str]] = {
    STT_PROVIDER_VOXTRAL_API: ("souffleur.adapters.stt.voxtral_api", "VoxtralApiTranscriptionPort"),
    STT_PROVIDER_VOXTRAL_LOCAL: ("souffleur.adapters.stt.voxtral_local", "VoxtralLocalTranscriptionPort"),
    STT_PROVIDER_GLADIA: ("souffleur.adapters.stt.gladia", "GladiaTranscriptionPort"),
}


class UnknownSttProviderError(ValueError):
    """`SOUFFLEUR_STT_PROVIDER` verweist auf keinen registrierten Adapter."""


def build_transcription_port(settings: Settings) -> TranscriptionPort:
    """Instanziiert den STT-Adapter, der zu `settings.stt_provider` passt.

    Wirft `UnknownSttProviderError`, wenn der Provider-Wert nicht registriert ist.
    """
    entry = _ADAPTER_REGISTRY.get(settings.stt_provider)
    if entry is None:
        raise UnknownSttProviderError(
            f"SOUFFLEUR_STT_PROVIDER={settings.stt_provider!r} unbekannt — erlaubt: "
            f"{', '.join(_ADAPTER_REGISTRY)}"
        )
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    port: TranscriptionPort = adapter_cls(settings)
    return port
