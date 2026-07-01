// Souffleur AI — Overlay (Tauri v2, macOS/Apple Silicon, Phase 2 / Welle 15+16).
//
// Kein Windows-Konsolenfenster nötig (macOS-only App), daher keine
// `windows_subsystem`-Annotation.

mod capture;
mod commands;
mod network;
mod state;

#[cfg(target_os = "macos")]
mod macos_window;

use tauri::{Manager, PhysicalPosition, Position};

fn main() {
    tauri::Builder::default()
        .manage(state::AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::start_session,
            commands::stop_session,
            commands::session_status,
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("overlay") {
                position_bottom_center(&window);

                #[cfg(target_os = "macos")]
                {
                    if let Err(err) = macos_window::apply_screen_share_invisible(&window) {
                        // Kein Hard-Fail: das Fenster bleibt nutzbar, nur die Screen-Share-
                        // Unsichtbarkeit fehlt dann — klar sichtbar im Log, siehe README
                        // "Abweichungen".
                        eprintln!("[window] sharingType=None fehlgeschlagen: {err}");
                    }
                }

                let _ = window.show();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Souffleur AI Overlay konnte nicht gestartet werden");
}

/// Positioniert das Overlay unten mittig auf dem aktuellen Monitor ("unten eingeblendet",
/// Task-Vorgabe Welle 16) statt der Bildschirmmitte, die Tauri sonst standardmäßig wählt.
fn position_bottom_center(window: &tauri::WebviewWindow) {
    let Ok(Some(monitor)) = window.current_monitor() else { return };
    let Ok(win_size) = window.outer_size() else { return };

    let screen = monitor.size();
    const MARGIN_BOTTOM_PX: i32 = 56;
    let x = (screen.width as i32 - win_size.width as i32) / 2;
    let y = screen.height as i32 - win_size.height as i32 - MARGIN_BOTTOM_PX;
    let _ = window.set_position(Position::Physical(PhysicalPosition::new(x.max(0), y.max(0))));
}
