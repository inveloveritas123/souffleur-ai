# apps/overlay — Phase-2-Live-Overlay (Tauri, macOS)

Semitransparentes, immer-oben-Overlay für die Live-Coaching-Karten. Tauri v2 (Rust-Backend
+ React-Frontend). Ziel-Hardware Apple Silicon.

**Anti-Cluely-Positionierung (wichtig, Konzept-Dok Kap. 7):** Die Screen-Share-
Unsichtbarkeit (`sharingType=none`) verbirgt NUR den privaten Hinweis-Layer des Coaches
beim Screen-Sharing — NICHT die Tatsache, dass eine KI-Verarbeitung stattfindet. Das
Overlay selbst zeigt dem Coach jederzeit sichtbar den Hinweis „KI-Assistenz aktiv (mit
Einwilligung)“ (`src/components/ConsentBanner.tsx`). Das Gegenüber wird separat und
dokumentiert im Consent-Schritt der Web-UI (Phase 1) informiert — das gehört dorthin, nicht
ins Overlay-Versteckspiel.

## Struktur

- `src/` — React-Frontend: Consent-Banner, Transkript-Kontext, gestreamt aufgebaute
  Coaching-Karte, Start/Stop-Formular (`src/components/`, `src/lib/`).
- `src-tauri/` — Rust:
  - `src/capture/` — Dual-Source-Audio-Erfassung (siehe "Capture" unten).
  - `src/network/` — WebSocket-Client gegen das Backend (`/ws/v1/live`), mischt beide
    Kanäle zu interleaved Stereo-PCM, reicht eingehende Bus-Events 1:1 als Tauri-Event ans
    Frontend weiter.
  - `src/macos_window.rs` — `NSWindow.sharingType = .none` (Screen-Share-Unsichtbarkeit).
  - `src/commands.rs` / `src/state.rs` — Tauri-Commands (`start_session`/`stop_session`),
    App-State (höchstens eine aktive Session).
  - `Info.plist` — `NSMicrophoneUsageDescription` / `NSScreenCaptureUsageDescription`.

## Capture — was echt läuft, was Stub ist

| Kanal | Quelle | Status |
|---|---|---|
| 0 (Coach) | Mikrofon (`src-tauri/src/capture/mic.rs`) | **Echt, funktionsfähig.** cpal, Standard-Eingabegerät, Mono-Downmix + linearer Resampler auf 16 kHz. |
| 1 (Gegenüber) | System-Audio (`src-tauri/src/capture/system_audio.rs`) | **Stub, dokumentiert.** Liefert Stille im selben 20-ms-Takt. Grund: keine ausgereifte Rust-ScreenCaptureKit-Anbindung verfügbar; volle Objective-C-Bridging-Arbeit sprengt diese Welle. TODO + Zielarchitektur stehen ausführlich im Modul-Kommentar. Die Schnittstelle (`CaptureSource`-Trait) ist bereits final. |

Beide Kanäle sind im WebSocket-Protokoll strukturell vorhanden (interleaved Stereo-PCM
s16le, 16 kHz, Kanal 0 = Coach, Kanal 1 = Gegenüber) — Kanal 1 trägt heute nur Stille statt
echtem System-Audio.

## Permission-Setup (macOS)

Beide Berechtigungen werden zur LAUFZEIT vom Betriebssystem abgefragt — sie sind zum
Build-Zeitpunkt nicht grantbar.

1. **Mikrofon** (`NSMicrophoneUsageDescription`, echt genutzt): beim ersten Start zeigt
   macOS automatisch den System-Dialog "Souffleur AI Overlay möchte auf das Mikrofon
   zugreifen". Bestätigen. Falls verpasst/abgelehnt: **Systemeinstellungen → Datenschutz &
   Sicherheit → Mikrofon → Souffleur AI Overlay aktivieren**, App neu starten.
2. **Bildschirmaufnahme** (`NSScreenCaptureUsageDescription`, für die künftige
   System-Audio-Implementierung deklariert, aktuell nicht aktiv genutzt, da Stub):
   **Systemeinstellungen → Datenschutz & Sicherheit → Bildschirmaufnahme → Souffleur AI
   Overlay aktivieren**, sobald `system_audio.rs` echt implementiert ist.

Ohne erteilte Mikrofon-Berechtigung liefert `cpal::default_input_device()` einen Fehler
statt Audiodaten — das Overlay startet trotzdem (kein Absturz), Kanal 0 bleibt aber leer.

## Verifikation der Screen-Share-Unsichtbarkeit (Akzeptanzkriterium, manuell)

Das ist der geforderte manuelle Nachweis — automatisiert nicht sinnvoll prüfbar, weil er
eine echte Bildschirmaufnahme-Pipeline eines Drittsystems (macOS-Compositor) voraussetzt.

1. Overlay im Debug- oder Release-Build starten (`npm run tauri dev` bzw. die gebaute
   `.app`), Fenster ist sichtbar (unten mittig auf dem Bildschirm).
2. Eine Bildschirmaufnahme des GESAMTEN Bildschirms starten, z. B.:
   - **QuickTime Player** → Ablage → Neue Bildschirmaufnahme → Aufnahme starten, oder
   - **Systemsteuerung/Control Center → Bildschirmaufnahme**, oder
   - eine echte Meeting-App (Zoom/Teams/Meet) mit aktivierter Bildschirmfreigabe.
3. Während die Aufnahme/Freigabe läuft: das Overlay-Fenster bewegen, den Fokus wechseln,
   eine Karte anzeigen lassen — es bleibt für DICH (den Coach, am eigenen Bildschirm) normal
   sichtbar.
4. Aufnahme beenden bzw. Bildschirmfreigabe stoppen und das Ergebnis prüfen:
   - **QuickTime:** die fertige `.mov`-Datei abspielen.
   - **Zoom/Teams/Meet:** aus Sicht eines zweiten Teilnehmers (zweites Gerät oder Aufzeichnung)
     prüfen.
5. **Erwartung:** An der Stelle, an der das Overlay auf dem echten Bildschirm sichtbar war,
   zeigt die Aufnahme entweder den unveränderten Hintergrund oder (je nach macOS-Version/
   Aufnahmepfad) einen leeren/schwarzen Bereich — das Overlay selbst erscheint NICHT.
6. Gegenprobe (damit der Test aussagekräftig ist): `sharingType`-Aufruf in
   `src-tauri/src/main.rs`/`macos_window.rs` temporär auskommentieren, neu bauen, Schritt 2–5
   wiederholen — jetzt MUSS das Overlay in der Aufnahme sichtbar sein. Danach die
   Auskommentierung wieder entfernen.

Dieser Schritt ist bewusst nicht automatisiert (siehe SPEC.md Akzeptanzkriterium: "ein
manuell dokumentierter Verifikationsschritt"). Robert: bitte Schritt 1–6 einmal auf dem
Zielgerät (Apple Silicon) durchführen und das Ergebnis (screenshot/kurze Notiz) festhalten.

## Build

```bash
source $HOME/.cargo/env
cd apps/overlay
npm install
npm run build            # tsc --noEmit + vite build (Frontend)
npm run tauri build --debug   # Rust + Bundling, Debug (kein Code-Signing nötig)
# npm run tauri build          # Release — scheitert ohne Apple-Signing-Identität an der
#                                 Notarization/Codesign-Stufe; Debug-Build ist der Nachweis
#                                 für "kompiliert und startet", siehe Task-Vorgabe.
```

`cargo clippy` (aus `src-tauri/`) sollte sauber laufen; siehe Kommentare im Code für
bewusste, dokumentierte Vereinfachungen (linearer Resampler, System-Audio-Stub).

## EU-Routing (Gate E1)

Das Overlay verbindet sich ausschließlich mit der konfigurierten Backend-WS-URL (Default
`ws://localhost:8000/ws/v1/live`, überschreibbar über `VITE_SOUFFLEUR_WS_URL` bzw. das
Start-Formular). Es enthält keinen Mistral-Endpunkt, keinen API-Key — Modellaufrufe und
Secrets bleiben ausschließlich im Backend.

## Hinweise

Nicht in Docker (native Screen-Capture- und Fenster-Rechte erforderlich). Wird als
macOS-App gebaut. Die OSS-Vorlage Pluely dient nur als Architektur-Referenz, Open-Cluely
nur als Referenz für die Dual-Source-Capture-Logik; Lizenzen vor produktiver Übernahme
prüfen (bisher: kein Code aus diesen Repos übernommen, nur konzeptionelle Referenz).
