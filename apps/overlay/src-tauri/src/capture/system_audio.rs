//! system_audio.rs — Kanal 1 / Gegenüber. **STUB — nicht implementiert, ehrlich dokumentiert.**
//!
//! ## Ziel-API (macOS)
//! - **ScreenCaptureKit** (ab macOS 13): `SCStream` mit `SCStreamConfiguration.capturesAudio =
//!   true` + `SCContentFilter` liefert System-weites (oder per-App) Audio als `CMSampleBuffer`.
//! - **CoreAudio-Process-Taps** (ab macOS 14.4): `AudioHardwareCreateProcessTap` erlaubt das
//!   gezielte Abgreifen einzelner Prozesse (z. B. nur Zoom/Teams/Meet statt System-weit) — für
//!   "nur das Gegenüber, nicht den eigenen Kartenaufbau-Ton" die konzeptionell sauberere Quelle.
//!
//! ## Warum Stub statt Vollimplementierung (in dieser Welle)
//! Beide APIs sind Objective-C/Swift-first. Es gibt (Stand dieser Welle) kein ausgereiftes,
//! gepflegtes Rust-Crate dafür. Eine echte Implementierung bräuchte zusätzlich:
//! 1. Eigenes Objective-C-Bridging (`objc2`/`objc2-foundation` + ein Block-Trampolin für den
//!    `SCStreamOutput`-Delegate-Callback) — nicht trivial, weil `SCStream` asynchron über
//!    einen Delegate liefert, dessen `CMSampleBuffer` erst per
//!    `CMSampleBufferGetAudioBufferList` in PCM extrahiert werden muss.
//! 2. Eigenes Berechtigungs-Handling (`CGPreflightScreenCaptureAccess`/
//!    `CGRequestScreenCaptureAccess` — dieselbe Systemeinstellung wie für Video-Screen-Capture,
//!    auch wenn hier nur Audio erfasst wird; siehe README "Permission-Setup").
//! 3. Denselben Mono/16-kHz-Schliff wie `mic.rs` (wiederverwendbar über `resample`).
//!
//! Die Task-Vorgabe akzeptiert für diesen Fall explizit einen dokumentierten Stub mit klarer
//! Schnittstelle statt einer riskanten Teil-Integration. Die Schnittstelle (`CaptureSource`)
//! ist bereits final — eine echte Implementierung ändert weder Mixer noch WebSocket-Protokoll.
//!
//! ## Was dieses Modul stattdessen tut
//! Liefert Stille (Null-Samples) im selben Chunk-Takt wie `mic.rs`, damit Kanal 1 im
//! gesendeten Stereo-Stream strukturell vorhanden ist (der Backend-Vertrag erwartet
//! `SessionContext.channels == 2`) — transparent als Stille, keine erfundenen Inhalte.
//!
//! ## TODO (nächster Schritt für eine echte Implementierung)
//! - [ ] `objc2-screen-capture-kit`-Bindings prüfen, sobald ein gepflegtes Crate existiert,
//!   ODER: kleines Swift-Helper-Package mit C-ABI-Export, das Rust per FFI aufruft (geringeres
//!   Risiko als rohes `SCStream`-Bridging direkt aus Rust).
//! - [ ] Downsampling auf 16 kHz über `capture::resample::LinearResampler` wiederverwenden.
//! - [ ] Berechtigungsprüfung VOR Session-Start (`CGPreflightScreenCaptureAccess`), damit das
//!   Overlay-UI dem Coach vor Gesprächsbeginn einen klaren Hinweis zeigt, statt eines stillen
//!   Kanal-1-Ausfalls.

use tokio::sync::{mpsc, oneshot};

use super::{CaptureError, CaptureSource, ChannelId, CHUNK_SAMPLES};

pub struct SystemAudioCapture {
    stop_tx: Option<oneshot::Sender<()>>,
}

impl SystemAudioCapture {
    pub fn new() -> Self {
        Self { stop_tx: None }
    }
}

impl Default for SystemAudioCapture {
    fn default() -> Self {
        Self::new()
    }
}

impl CaptureSource for SystemAudioCapture {
    fn channel(&self) -> ChannelId {
        ChannelId::Counterpart
    }

    fn start(&mut self) -> Result<mpsc::Receiver<Vec<i16>>, CaptureError> {
        let (tx, rx) = mpsc::channel::<Vec<i16>>(64);
        let (stop_tx, mut stop_rx) = oneshot::channel::<()>();
        self.stop_tx = Some(stop_tx);

        // Selber Takt wie mic.rs (20ms-Chunks @ 16kHz) — Stille statt echtem System-Audio,
        // siehe Moduldoku oben. Kein echter Geräte-/Berechtigungszugriff hier.
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(std::time::Duration::from_millis(20));
            loop {
                tokio::select! {
                    _ = interval.tick() => {
                        if tx.send(vec![0i16; CHUNK_SAMPLES]).await.is_err() {
                            break;
                        }
                    }
                    _ = &mut stop_rx => break,
                }
            }
        });

        Ok(rx)
    }

    fn stop(&mut self) {
        if let Some(tx) = self.stop_tx.take() {
            let _ = tx.send(());
        }
    }
}
