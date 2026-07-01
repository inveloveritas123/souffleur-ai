//! macos_window.rs — `NSWindow.sharingType = .none` (Screen-Share-Unsichtbarkeit, Welle 16).
//!
//! Kernmechanik (Konzept-Dok Abschnitt 2.4): Ein `NSWindow` mit
//! `sharingType = NSWindowSharingNone` wird vom Compositor aus jedem Screen-Capture-Pfad
//! ausgeschlossen (`CGWindowListCreateImage`, ScreenCaptureKit — und darüber auch Zoom/Teams/
//! Meet/OBS, die alle einen dieser Systempfade nutzen), bleibt aber für den Nutzer selbst
//! normal sichtbar. Zusätzlich `hasShadow = false`: ein Fenster-Schatten wird vom Compositor
//! separat gezeichnet und kann sonst als Artefakt "durchscheinen".
//!
//! Tauri v2 exponiert `WebviewWindow::ns_window()` (nur macOS) als `*mut c_void` auf das
//! zugrunde liegende `NSWindow*`. Hier wird darauf per objc-Runtime (`objc`/`cocoa`-Crate,
//! kein zusätzlicher Swift/ObjC-Build-Schritt nötig) `setSharingType:`/`setHasShadow:`
//! gesendet.
//!
//! Zwei bewusst zugelassene Lint-Ausnahmen unten:
//! - `deprecated`: `cocoa::base::id` ist als Typalias markiert ("use objc2 crate instead"),
//!   funktioniert aber unverändert; ein Wechsel auf `objc2`/`objc2-app-kit` wäre ein größerer
//!   Umbau ohne funktionalen Gewinn für diese eine Fenster-Einstellung.
//! - `unexpected_cfgs`: kommt aus der `sel_impl!`-Makro-Expansion der `objc`-Crate selbst
//!   (prüft intern auf `feature = "cargo-clippy"`, ein veralteter Clippy-Erkennungs-Trick) —
//!   nicht in unserem Code behebbar, siehe `cargo build`-Hinweis "may come from an old
//!   version of the `objc` crate".

#![allow(deprecated)]
#![allow(unexpected_cfgs)]

use cocoa::base::{id, NO};
use objc::{msg_send, sel, sel_impl};

/// `NSWindowSharingType.none` (AppKit: `NSWindowSharingNone = 0`).
const NS_WINDOW_SHARING_NONE: i64 = 0;

// Siehe Moduldoku oben: `unexpected_cfgs` kommt aus der `objc`-Crate-Makro-Expansion selbst,
// die modulweite `#![allow]` griff nicht (rustc prüft `check-cfg` am Makro-Nutzungsort mit
// eigener Diagnose-Zuordnung) — deshalb hier direkt auf der Funktion.
#[allow(unexpected_cfgs)]
pub fn apply_screen_share_invisible(window: &tauri::WebviewWindow) -> Result<(), String> {
    let ns_window_ptr = window
        .ns_window()
        .map_err(|e| format!("ns_window() nicht verfügbar: {e}"))?;

    if ns_window_ptr.is_null() {
        return Err("ns_window() lieferte einen Null-Pointer".to_string());
    }

    // SAFETY: `ns_window_ptr` kommt direkt von Tauri (`WebviewWindow::ns_window`) und zeigt auf
    // ein lebendes `NSWindow*` der aktuellen Fensterinstanz. Es werden ausschließlich
    // dokumentierte AppKit-Setter aufgerufen (`setSharingType:`, `setHasShadow:`), die keine
    // Ownership übernehmen und keinen Zustand außerhalb des Fensters selbst ändern. Der Aufruf
    // passiert im Tauri-`setup`-Hook, der auf dem Main-Thread läuft (AppKit-Objekte sind nicht
    // thread-safe, das ist hier garantiert).
    unsafe {
        let ns_window = ns_window_ptr as id;
        let _: () = msg_send![ns_window, setSharingType: NS_WINDOW_SHARING_NONE];
        let _: () = msg_send![ns_window, setHasShadow: NO];
    }

    Ok(())
}
