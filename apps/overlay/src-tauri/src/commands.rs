//! commands.rs — Tauri-Commands, die das Frontend per `invoke()` aufruft.
//!
//! Bewusst schmale API: das Frontend kennt keine Audio-/WS-Details, nur `start_session`/
//! `stop_session`/`session_status`. Alle Capture- und Netzwerk-Details bleiben in Rust
//! (`capture`/`network`) — das Frontend bekommt eingehende Bus-Events ausschließlich über
//! Tauri-Events (`souffleur://bus-event`, siehe `network/mod.rs`).

use serde::{Deserialize, Serialize};
use tauri::{command, AppHandle, State};

use crate::capture::mic::MicCapture;
use crate::capture::system_audio::SystemAudioCapture;
use crate::capture::CaptureSource;
use crate::network::{self, StartSessionArgs};
use crate::state::{ActiveSession, AppState};

fn default_sample_rate() -> u32 {
    16_000
}

/// Payload aus dem Frontend — spiegelt den Backend-Start-Handshake (`api/live.py`), plus
/// `ws_url` (Env-konfigurierbar im Frontend, niemals hartkodiert Non-EU, siehe Gate E1).
#[derive(Deserialize)]
pub struct StartSessionRequest {
    pub ws_url: String,
    pub tenant_id: String,
    pub session_id: String,
    pub consent_ref: String,
    #[serde(default = "default_sample_rate")]
    pub sample_rate: u32,
    pub language: Option<String>,
}

#[derive(Serialize, Clone, Copy)]
pub struct SessionStatus {
    pub active: bool,
}

#[command]
pub async fn start_session(
    app: AppHandle,
    state: State<'_, AppState>,
    request: StartSessionRequest,
) -> Result<(), String> {
    {
        let guard = state
            .session
            .lock()
            .map_err(|_| "Session-Lock beschädigt".to_string())?;
        if guard.is_some() {
            return Err("Es läuft bereits eine Session".to_string());
        }
    }

    let mut mic = MicCapture::new();
    let mut system_audio = SystemAudioCapture::new();

    // Kein Klartext-/PII-Log (Gate E2) — nur die Kanal-Zuordnung zur Diagnose.
    eprintln!(
        "[commands] Starte Dual-Source-Capture: Kanal {:?} = Mikrofon (echt), Kanal {:?} = System-Audio (Stub/Stille)",
        mic.channel(),
        system_audio.channel()
    );

    let coach_rx = mic.start().map_err(|e| e.to_string())?;
    let counterpart_rx = match system_audio.start() {
        Ok(rx) => rx,
        Err(err) => {
            mic.stop();
            return Err(err.to_string());
        }
    };

    let args = StartSessionArgs {
        ws_url: request.ws_url,
        tenant_id: request.tenant_id,
        session_id: request.session_id,
        consent_ref: request.consent_ref,
        sample_rate: request.sample_rate,
        language: request.language,
    };

    let network_handle = match network::start_session(app, args, coach_rx, counterpart_rx).await {
        Ok(handle) => handle,
        Err(err) => {
            mic.stop();
            system_audio.stop();
            return Err(err);
        }
    };

    let mut guard = state
        .session
        .lock()
        .map_err(|_| "Session-Lock beschädigt".to_string())?;
    *guard = Some(ActiveSession { mic, system_audio, network: network_handle });
    Ok(())
}

#[command]
pub fn stop_session(state: State<'_, AppState>) -> Result<(), String> {
    let mut guard = state
        .session
        .lock()
        .map_err(|_| "Session-Lock beschädigt".to_string())?;
    if let Some(mut session) = guard.take() {
        session.mic.stop();
        session.system_audio.stop();
        session.network.stop();
    }
    Ok(())
}

#[command]
pub fn session_status(state: State<'_, AppState>) -> Result<SessionStatus, String> {
    let guard = state
        .session
        .lock()
        .map_err(|_| "Session-Lock beschädigt".to_string())?;
    Ok(SessionStatus { active: guard.is_some() })
}
