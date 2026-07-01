//! capture — Dual-Source-Audio-Erfassung (Welle 15).
//!
//! Zwei getrennte logische Quellen, passend zum Backend-Vertrag
//! (`apps/backend/src/souffleur/adapters/capture/dual_source.py`): Kanal 0 = Mikrofon/Coach,
//! Kanal 1 = System-Audio/Gegenüber. Beide liefern Mono-PCM (`i16`, 16 kHz); das
//! `network`-Modul mischt sie zu einem interleaved Stereo-Frame und sendet sie als binäre
//! WebSocket-Frames an `/ws/v1/live` (Mistral erhält `channels=2` im Query-String und trennt
//! serverseitig wieder nach Kanal, siehe `voxtral_api.py`-Docstring im Backend).
//!
//! ## Ehrlichkeitsbilanz (was läuft echt, was ist Stub)
//! - `mic` (Kanal 0): **ECHT, funktionsfähig.** cpal-basiert, Standard-Eingabegerät, Mono-
//!   Downmix + einfacher linearer Resampler auf 16 kHz (siehe `resample.rs`).
//! - `system_audio` (Kanal 1): **STUB, dokumentiert.** Liefert Stille im selben Chunk-Takt.
//!   Grund + TODO für eine echte ScreenCaptureKit/CoreAudio-Implementierung stehen in
//!   `system_audio.rs`. Die Schnittstelle (`CaptureSource`) ist bereits final, sodass eine
//!   spätere echte Implementierung ohne Protokolländerung nachgezogen werden kann.

pub mod mic;
pub mod resample;
pub mod system_audio;

use tokio::sync::mpsc;

/// Zielrate für den WebSocket-Stream — muss mit `sample_rate` im Start-Handshake
/// (`{"type":"start", ..., "sample_rate":16000}`, Backend-Vertrag `api/live.py`) übereinstimmen.
pub const SAMPLE_RATE_HZ: u32 = 16_000;

/// Chunk-Größe für Capture -> Mixer: 20 ms bei 16 kHz = 320 Samples. Üblicher Frame für
/// Echtzeit-STT/VAD — klein genug für niedrige Latenz, groß genug um IPC-/Netz-Overhead
/// klein zu halten.
pub const CHUNK_SAMPLES: usize = 320;

/// Kanal-Zuordnung — muss exakt der Backend-Konvention entsprechen (`CHANNEL_TO_SPEAKER`
/// in `adapters/capture/dual_source.py`: 0 = coach, 1 = counterpart).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChannelId {
    /// Kanal 0 — Mikrofon des Coaches.
    Coach = 0,
    /// Kanal 1 — System-Audio, d. h. das Gegenüber im Call.
    Counterpart = 1,
}

#[derive(Debug)]
pub enum CaptureError {
    DeviceUnavailable(String),
}

impl std::fmt::Display for CaptureError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CaptureError::DeviceUnavailable(msg) => write!(f, "Audio-Gerät nicht verfügbar: {msg}"),
        }
    }
}

impl std::error::Error for CaptureError {}

/// Gemeinsame Schnittstelle für eine Audio-Quelle — bewusst minimal, damit `system_audio`
/// später durch eine echte ScreenCaptureKit-Implementierung ersetzt werden kann, ohne dass
/// `network`/`commands` sich ändern müssen.
pub trait CaptureSource: Send {
    fn channel(&self) -> ChannelId;

    /// Startet die Erfassung; liefert einen Receiver für Mono-i16-PCM-Chunks @ 16 kHz.
    fn start(&mut self) -> Result<mpsc::Receiver<Vec<i16>>, CaptureError>;

    /// Beendet die Erfassung. Muss idempotent sein (mehrfacher Aufruf ist ein No-op).
    fn stop(&mut self);
}
