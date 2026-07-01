//! state.rs — geteilter Tauri-App-State: höchstens eine aktive Live-Session gleichzeitig.

use std::sync::Mutex;

use crate::capture::mic::MicCapture;
use crate::capture::system_audio::SystemAudioCapture;
use crate::network::SessionHandle;

pub struct ActiveSession {
    pub mic: MicCapture,
    pub system_audio: SystemAudioCapture,
    pub network: SessionHandle,
}

#[derive(Default)]
pub struct AppState {
    pub session: Mutex<Option<ActiveSession>>,
}
