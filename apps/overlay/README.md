# apps/overlay — Phase-2-Live-Overlay (Tauri, macOS)

Semitransparentes, immer-oben-Overlay für die Live-Coaching-Karten. Tauri (Rust-Backend, circa 10 MB). Ziel-Hardware Apple Silicon (M5).

## Was hier hineingehört

- `src/` — React-Frontend des Overlays (Karten-Anzeige, gestreamter Aufbau, Cooldown).
- `src-tauri/` — Rust: lokale Dual-Source-Capture (System-Audio gleich Gegenüber, Mikrofon gleich Coach), WebSocket-Anbindung an das Backend, und das entscheidende Detail: macOS NSWindow sharingType none, damit das Overlay in Screen-Sharing-Aufnahmen nicht erscheint.

## Verifikation der Screen-Share-Unsichtbarkeit

Manuell dokumentierter Nachweis (Akzeptanzkriterium 8): Bildschirmaufnahme starten, Overlay einblenden, Aufnahme prüfen — das Overlay darf nicht erscheinen.

## Hinweise

Nicht in Docker (native Screen-Capture- und Fenster-Rechte erforderlich). Wird als macOS-App gebaut. Die OSS-Vorlage Pluely dient nur als Architektur-Referenz; Lizenz vor Übernahme prüfen.
