//! mic.rs — Mikrofon-Erfassung (Kanal 0 / Coach). **Echt, funktionsfähig** (cpal).
//!
//! Öffnet das Standard-Eingabegerät des Betriebssystems, mischt bei Bedarf auf Mono und
//! resampled linear auf 16 kHz (`resample::LinearResampler`). Der cpal-`Stream` lebt bewusst
//! auf einem dedizierten OS-Thread (nicht in Tokio) — cpal-Streams sind auf manchen Backends
//! nicht `Send`, und der Audio-Callback läuft ohnehin auf einem Echtzeit-Thread von cpal
//! selbst; der dedizierte Thread hält nur die Lebensdauer offen und wartet auf das
//! Stop-Signal.
//!
//! Benötigt zur Laufzeit die macOS-Mikrofon-Berechtigung (`NSMicrophoneUsageDescription`,
//! siehe `src-tauri/Info.plist` und `README.md` "Permission-Setup"). Ohne erteilte
//! Berechtigung liefert `default_input_device()`/`build_input_stream` einen Fehler statt
//! Audiodaten — sauber als `CaptureError::DeviceUnavailable` weitergereicht, kein Absturz.

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use tokio::sync::mpsc;

use super::resample::LinearResampler;
use super::{CaptureError, CaptureSource, ChannelId};

pub struct MicCapture {
    stop_tx: Option<std::sync::mpsc::Sender<()>>,
    join: Option<std::thread::JoinHandle<()>>,
}

impl MicCapture {
    pub fn new() -> Self {
        Self { stop_tx: None, join: None }
    }
}

impl Default for MicCapture {
    fn default() -> Self {
        Self::new()
    }
}

impl CaptureSource for MicCapture {
    fn channel(&self) -> ChannelId {
        ChannelId::Coach
    }

    fn start(&mut self) -> Result<mpsc::Receiver<Vec<i16>>, CaptureError> {
        let (tx, rx) = mpsc::channel::<Vec<i16>>(64);
        let (stop_tx, stop_rx) = std::sync::mpsc::channel::<()>();
        self.stop_tx = Some(stop_tx);

        let handle = std::thread::Builder::new()
            .name("souffleur-mic-capture".into())
            .spawn(move || {
                if let Err(err) = run_capture_thread(tx, stop_rx) {
                    // Kein PII (Gate E2) — nur Fehlerklasse, kein Audioinhalt.
                    eprintln!("[capture:mic] Abbruch: {err}");
                }
            })
            .map_err(|e| CaptureError::DeviceUnavailable(e.to_string()))?;
        self.join = Some(handle);
        Ok(rx)
    }

    fn stop(&mut self) {
        if let Some(tx) = self.stop_tx.take() {
            let _ = tx.send(());
        }
        if let Some(handle) = self.join.take() {
            let _ = handle.join();
        }
    }
}

fn run_capture_thread(
    tx: mpsc::Sender<Vec<i16>>,
    stop_rx: std::sync::mpsc::Receiver<()>,
) -> Result<(), CaptureError> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| CaptureError::DeviceUnavailable("kein Standard-Mikrofon gefunden".into()))?;
    let supported_config = device
        .default_input_config()
        .map_err(|e| CaptureError::DeviceUnavailable(e.to_string()))?;

    let sample_format = supported_config.sample_format();
    let channels = supported_config.channels() as usize;
    // cpal 0.18: `SampleRate` ist ein Typalias für `u32` (kein Tupel-Struct mehr).
    let input_rate: u32 = supported_config.sample_rate();
    let stream_config: cpal::StreamConfig = supported_config.into();

    let mut resampler = LinearResampler::new(input_rate, super::SAMPLE_RATE_HZ, channels);
    let err_fn = |err: cpal::Error| eprintln!("[capture:mic] Stream-Fehler: {err}");

    let stream = match sample_format {
        cpal::SampleFormat::F32 => device.build_input_stream(
            stream_config,
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                let mono_16k = resampler.push_f32(data);
                if !mono_16k.is_empty() {
                    let _ = tx.blocking_send(mono_16k);
                }
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::I16 => device.build_input_stream(
            stream_config,
            move |data: &[i16], _: &cpal::InputCallbackInfo| {
                let as_f32: Vec<f32> = data.iter().map(|s| *s as f32 / i16::MAX as f32).collect();
                let mono_16k = resampler.push_f32(&as_f32);
                if !mono_16k.is_empty() {
                    let _ = tx.blocking_send(mono_16k);
                }
            },
            err_fn,
            None,
        ),
        other => {
            return Err(CaptureError::DeviceUnavailable(format!(
                "nicht unterstütztes Sample-Format: {other:?}"
            )))
        }
    }
    .map_err(|e| CaptureError::DeviceUnavailable(e.to_string()))?;

    stream
        .play()
        .map_err(|e| CaptureError::DeviceUnavailable(e.to_string()))?;

    // Thread lebt, bis `stop()` das Signal schickt — der `Stream` bleibt dadurch auf diesem
    // Thread (kein Send über Thread-Grenzen nötig) und wird beim Verlassen des Scopes gestoppt.
    let _ = stop_rx.recv();
    drop(stream);
    Ok(())
}
