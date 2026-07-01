"""adapters/capture — Dual-Source-Capture-Konvention (Phase 2, Welle 12).

Die eigentliche Audio-Erfassung (System-Audio + Mikrofon, zwei getrennte Quellen) passiert
nativ im Tauri-Overlay (Welle 15/16, `apps/overlay`, außerhalb dieses Scopes — dort auch
außerhalb der Backend-Verbote). Dieses Modul modelliert die Backend-seitige Dual-Source-
Konvention aus ARCHITECTURE.md ("Daten- und Latenzfluss", Welle-12-Entscheid):

- `SessionContext.channels == 2` kennzeichnet eine Dual-Source-Session.
- System-Audio ist das Gegenüber (`counterpart`, Kanal 1), Mikrofon ist der Coach
  (`coach`, Kanal 0) — dieselbe Kanal->Sprecher-Zuordnung, die `adapters/stt/voxtral_api.py`
  beim Parsen von Live-Transkript-Events verwendet (`CHANNEL_TO_SPEAKER`).
- `CaptureChunk` markiert einen eingehenden PCM-Chunk mit seiner Quelle, BEVOR er an
  `TranscriptionPort.push_audio` weitergereicht wird (Welle 14 Live-WS-API nutzt das, um
  Client-Frames einer Quelle zuzuordnen — das Port-Interface selbst kennt aus
  ARCHITECTURE.md kein Kanal-Argument in `push_audio`).

Reine Datenstrukturen/Funktionen, kein I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CaptureSource = Literal["microphone", "system_audio"]

DUAL_SOURCE_CHANNELS = 2

# Kanonische Kanal->Sprecher-Zuordnung für Dual-Source-Live-Events (Kanal 0/1).
CHANNEL_TO_SPEAKER: dict[int, str] = {0: "coach", 1: "counterpart"}

# Kanonische Quelle->Sprecher-Zuordnung (Capture-Seite, vor dem Senden an push_audio).
SOURCE_TO_SPEAKER: dict[CaptureSource, str] = {
    "microphone": "coach",
    "system_audio": "counterpart",
}

SOURCE_TO_CHANNEL: dict[CaptureSource, int] = {"microphone": 0, "system_audio": 1}


class UnknownCaptureSourceError(ValueError):
    """`CaptureSource` trägt keinen der bekannten Werte (`microphone`/`system_audio`)."""


@dataclass(frozen=True)
class CaptureChunk:
    """Ein PCM-Chunk einer bestimmten Quelle — Kanal-Zuordnung, bevor push_audio ihn sieht."""

    source: CaptureSource
    pcm: bytes


def speaker_for_source(source: CaptureSource) -> str:
    """Sprecher-Label für eine Capture-Quelle (`coach` für Mikrofon, `counterpart` für System-Audio)."""
    try:
        return SOURCE_TO_SPEAKER[source]
    except KeyError as exc:
        raise UnknownCaptureSourceError(
            f"Unbekannte CaptureSource {source!r} — erlaubt: {', '.join(SOURCE_TO_SPEAKER)}"
        ) from exc


def channel_for_source(source: CaptureSource) -> int:
    """Kanal-Index (0/1) für eine Capture-Quelle — spiegelt `CHANNEL_TO_SPEAKER`."""
    try:
        return SOURCE_TO_CHANNEL[source]
    except KeyError as exc:
        raise UnknownCaptureSourceError(
            f"Unbekannte CaptureSource {source!r} — erlaubt: {', '.join(SOURCE_TO_CHANNEL)}"
        ) from exc
