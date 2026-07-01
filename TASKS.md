# TASKS — Souffleur AI

> Self-contained Wellen. Jede OFFENE Welle trägt inline alles, was ein frisch gestarteter Worker braucht.
> Test zuerst (RED) → GREEN → REFACTOR. Erledigte Welle mit `[x]` markieren.
> Bindende Specs: SPEC.md, ARCHITECTURE.md. Modell-Pins und Env: ARCHITECTURE.md Tabelle und .env.example.
> Reihenfolge: Fundament (W1-W2) → Backend Phase 1 (W3-W6) → Coaching-MCP (W7) → Web Phase 1 (W8-W9)
> → Docker (W10) → Backend Phase 2 (W11-W14) → Overlay Phase 2 (W15-W16) → Tests/Latenz (W17).

## Wellen

### Welle 1 — Fundament: Settings, geteilte Typen, Modell-Pins
- Dateien: apps/backend/src/souffleur/core/settings.py, packages/shared/src/, apps/backend/tests/test_settings.py
- Verbote: gates/*, templates/*, privacy/*, SPEC.md, ARCHITECTURE.md
- Smoke: `python3 -m pytest apps/backend/tests/test_settings.py -q`
- Akzeptanz: Settings liest alle Variablen aus .env.example; die vier Modell-IDs sind als Konstanten gepinnt (kein latest); ein Test prüft, dass jede Modell-ID exakt dem Wert aus der ARCHITECTURE-Tabelle entspricht und SOUFFLEUR_STT_PROVIDER auf voxtral_api defaultet.
- Entscheide: Single-Provider Mistral, Basis-URL api.mistral.ai; vier gepinnte Modelle.

### Welle 2 — Querschnitt: AuditLog (E4-Schema) und ConsentGate
- Dateien: apps/backend/src/souffleur/audit/, apps/backend/src/souffleur/core/consent.py, apps/backend/tests/test_audit.py, apps/backend/tests/test_consent.py
- Verbote: gates/*, templates/AUDIT-LOG.schema.json (nur lesen, nicht ändern)
- Smoke: `python3 -m pytest apps/backend/tests/test_audit.py apps/backend/tests/test_consent.py -q`
- Akzeptanz: AuditLog schreibt JSONL-Einträge mit routing_region EU und pii_present false; ein über AuditLog erzeugtes Log läuft durch e4_audit_log grün. ConsentGate lehnt Verarbeitung ohne dokumentierte Einwilligung mit HTTP 403 ab und lässt sie mit gültiger Consent-Referenz zu (beide Fälle getestet).
- Entscheide: Audit enthält nie Gesprächsinhalt; tenant_id durchgängig geführt.

### Welle 3 — Ports und STT-Adapter-Factory
- Dateien: apps/backend/src/souffleur/ports/, apps/backend/src/souffleur/adapters/stt/factory.py, apps/backend/tests/test_stt_factory.py
- Verbote: andere adapters/* Implementierungen (folgen in W4/W12)
- Smoke: `python3 -m pytest apps/backend/tests/test_stt_factory.py -q`
- Akzeptanz: TranscriptionPort-Protocol und Typen (SessionContext, TranscriptEvent, TranscriptResult, ProviderCapabilities, AudioRef, BatchOptions) gemäß ARCHITECTURE.md. build_transcription_port instanziiert alle drei Adapter (voxtral_api, voxtral_local, gladia) allein über SOUFFLEUR_STT_PROVIDER ohne Codeänderung; ein unbekannter Wert führt zu klarem Fehler.
- Entscheide: Provider-Wechsel ist reine Config.

### Welle 4 — STT-Adapter voxtral_api (Batch, Phase 1)
- Dateien: apps/backend/src/souffleur/adapters/stt/voxtral_api.py, apps/backend/tests/test_voxtral_api.py
- Verbote: keine echten Netzaufrufe im Test (Mistral-Client mocken); kein Non-EU-Endpunkt
- Smoke: `python3 -m pytest apps/backend/tests/test_voxtral_api.py -q`
- Akzeptanz: transcribe_batch nutzt voxtral-mini-2602 über api.mistral.ai und liefert TranscriptResult mit mindestens zwei Sprecher-Labels und Wort-Zeitstempeln (gegen gemockte Antwort getestet). capabilities meldet residency EU, supports_diarization und supports_word_timestamps true.
- Entscheide: EU-Routing erzwungen; kein latest-Tag.

### Welle 5 — LlmPort und Mistral-Reasoning-Adapter
- Dateien: apps/backend/src/souffleur/ports/llm.py, apps/backend/src/souffleur/adapters/llm/mistral.py, apps/backend/tests/test_llm_mistral.py
- Verbote: kein Non-EU-Endpunkt; kein latest-Tag
- Smoke: `python3 -m pytest apps/backend/tests/test_llm_mistral.py -q`
- Akzeptanz: LlmPort bietet eine streamende Reasoning-Methode (magistral-medium-2509) und eine schnelle Klassifikationsmethode (ministral-3b-2512) über api.mistral.ai; gegen gemockten Client getestet, Modelle aus Settings gepinnt.
- Entscheide: Reasoning streamt; Trigger-Klassifikation billig.

### Welle 6 — Phase-1-Pipeline und REST-API (Protokoll)
- Dateien: apps/backend/src/souffleur/api/protocol.py, apps/backend/src/souffleur/core/app.py, apps/backend/tests/test_protocol_api.py
- Verbote: WebSocket/Live (Phase 2, W11+)
- Smoke: `python3 -m pytest apps/backend/tests/test_protocol_api.py -q`
- Akzeptanz: REST-Endpunkt nimmt Audio plus Consent-Referenz, läuft durch ConsentGate (403 ohne Consent), ruft voxtral_api Batch und magistral-Zusammenfassung, gibt diarisiertes Protokoll als JSON zurück und schreibt je Modellaufruf einen Audit-Eintrag. End-to-End gegen gemockte Adapter getestet.
- Entscheide: Phase 1 ohne Overlay, ohne Trigger-Router.

### Welle 7 — Coaching-MCP-Server
- Dateien: packages/coaching-mcp/src/, packages/coaching-mcp/knowledge/, packages/coaching-mcp/tests/
- Verbote: apps/backend/* (Anbindung erst in W13)
- Smoke: `python3 -m pytest packages/coaching-mcp/tests/ -q`
- Akzeptanz: MCP-Server stellt mindestens ein Tool bereit, das zu einem Karten-Typ (Einwand, vertiefende Frage, Strukturhinweis) passendes Coaching-Wissen aus knowledge/ liefert; ein Test ruft das Tool und prüft eine nicht-leere, typgerechte Antwort. Läuft lokal, kein externer Datenabfluss.
- Entscheide: Wissen als Daten, kein Fine-Tuning.

### Welle 8 — Web-UI Gerüst (React + Vite + TS)
- Dateien: apps/web/src/, apps/web/package.json, apps/web/vite.config.ts
- Verbote: Overlay (apps/overlay), Backend
- Smoke: `cd apps/web && npm run build`
- Akzeptanz: React-Vite-TS-Projekt baut fehlerfrei; Views für Einwilligung, Upload und Protokoll-Anzeige sind als Routen vorhanden; spricht das Backend über die Basis-URL aus der Env an.
- Entscheide: React+Vite, weil Playwright-testbar und mit Tauri Phase 2 teilbar.

### Welle 9 — Web-UI Phase-1-Flow und Playwright-E2E
- Dateien: apps/web/src/, apps/web/tests/
- Verbote: Backend-Code
- Smoke: `cd apps/web && npx playwright test`
- Akzeptanz: Playwright-E2E durchläuft Einwilligung erteilen, Audio hochladen, Protokoll anzeigen ohne Fehler (gegen Mock-Backend); Protokoll-Export als Markdown und PDF ist auslösbar.
- Entscheide: Einwilligung ist Pflicht-Schritt vor Upload.

### Welle 10 — Docker und docker-compose
- Dateien: docker/, apps/backend/Dockerfile, apps/web/Dockerfile, packages/coaching-mcp/Dockerfile
- Verbote: apps/overlay (nicht containerisiert)
- Smoke: `docker compose -f docker/docker-compose.yml config`
- Akzeptanz: compose definiert backend (8000), coaching-mcp (8080), web (5173) und optional voxtral-worker (Profil local-stt); keine Secrets im Image, nur Env-Referenzen; config validiert fehlerfrei; kein Non-EU-Endpunkt in der Compose-Datei.
- Entscheide: voxtral-worker nur bei voxtral_local; Overlay nativ.

### Welle 11 — TranscriptEventBus
- Dateien: apps/backend/src/souffleur/bus/, apps/backend/tests/test_bus.py
- Verbote: Trigger/Reasoning-Logik (W12/W13)
- Smoke: `python3 -m pytest apps/backend/tests/test_bus.py -q`
- Akzeptanz: async pub/sub pro session_id; publish und subscribe gemäß BusEvent-Schema aus packages/shared; ein Test publiziert transcript.final und empfängt es beim Abonnenten in Reihenfolge (seq).
- Entscheide: In-Process asyncio, hinter schmalem Interface für Phase-3-Netzwerk-Adapter.

### Welle 12 — STT-Adapter voxtral_api Live-Streaming (Phase 2)
- Dateien: apps/backend/src/souffleur/adapters/stt/voxtral_api.py, apps/backend/adapters/capture/, apps/backend/tests/test_voxtral_stream.py
- Verbote: kein Non-EU-Endpunkt; kein latest-Tag
- Smoke: `python3 -m pytest apps/backend/tests/test_voxtral_stream.py -q`
- Akzeptanz: open_stream/push_audio/events/close_stream nutzen voxtral-mini-realtime-2602; events liefert partial- und final-Events; gegen gemockten Stream getestet; publiziert transcript-Events auf den Bus.
- Entscheide: Dual-Source (zwei Kanäle) als SessionContext.channels gleich 2.

### Welle 13 — TriggerRouter und ReasoningEngine plus MCP-Anbindung
- Dateien: apps/backend/src/souffleur/trigger/, apps/backend/src/souffleur/core/reasoning.py, apps/backend/tests/test_trigger.py
- Verbote: Web/Overlay
- Smoke: `python3 -m pytest apps/backend/tests/test_trigger.py -q`
- Akzeptanz: Regel-Vorfilter gibt für eine neutrale Aussage keine Karte und für Einwand/Frage Karte zurück (deterministischer Unit-Test); unsichere Fälle gehen an ministral-3b-2512 (gemockt). Bei Karte holt die ReasoningEngine Wissen vom Coaching-MCP und streamt eine Karte über magistral-medium-2509 auf den Bus. Cooldown verhindert Karten-Spam.
- Entscheide: nicht auf jeder Äußerung feuern.

### Welle 14 — WebSocket-API für Live (Phase 2)
- Dateien: apps/backend/src/souffleur/api/live.py, apps/backend/tests/test_live_api.py
- Verbote: Phase-1-REST nicht brechen
- Smoke: `python3 -m pytest apps/backend/tests/test_live_api.py -q`
- Akzeptanz: WebSocket nimmt Audio-Chunks (nach Consent), leitet sie an den Live-STT-Adapter, abonniert card- und transcript-Events und sendet sie an den Client; Verarbeitung ohne Consent wird abgelehnt; je Modellaufruf ein Audit-Eintrag.
- Entscheide: derselbe ConsentGate und AuditLog wie Phase 1.

### Welle 15 — Tauri-Overlay Gerüst und Dual-Source-Capture
- Dateien: apps/overlay/src/, apps/overlay/src-tauri/
- Verbote: Backend-Code
- Smoke: `cd apps/overlay && npm run tauri build`
- Akzeptanz: Tauri-App (React-Frontend, Rust-Backend) baut für macOS; erfasst System-Audio und Mikrofon als getrennte Quellen und streamt sie per WebSocket an das Backend.
- Entscheide: Apple Silicon; Pluely nur als Referenz.

### Welle 16 — Overlay screen-share-unsichtbar und Karten-Anzeige
- Dateien: apps/overlay/src/, apps/overlay/src-tauri/, apps/overlay/README.md
- Verbote: Backend-Code
- Smoke: `cd apps/overlay && npm run tauri build`
- Akzeptanz: Fenster setzt unter macOS NSWindow sharingType none und erscheint nachweislich nicht in einer Bildschirmaufnahme (manuell dokumentierter Verifikationsschritt im README); Karten bauen sich gestreamt auf und respektieren den Cooldown.
- Entscheide: Overlay verbirgt nur den privaten Hinweis-Layer, nicht die KI-Nutzung.

### Welle 17 — End-to-End-Tests und Latenzmessung
- Dateien: tests/e2e/, tests/unit/, apps/backend/tests/
- Verbote: Produktivcode nur lesen
- Smoke: `python3 -m pytest tests/ -q`
- Akzeptanz: E2E für die Phase-1-Pipeline (Upload bis Protokoll) läuft grün; ein reproduzierbares Latenz-Messskript misst die Phase-2-Spanne vom Äußerungsende bis zum Kartenbeginn und gibt einen Wert aus, Zielmarke unter zwei Sekunden dokumentiert.
- Entscheide: Latenz wird gemessen, nicht angenommen (entscheidet über Gladia-Fallback).

## Definition of Done (pro Welle)
- [ ] Test grün (Smoke) · [ ] Chunk-Review (Cross-Model) · [ ] keine Drift ggü. Vorrunde
- [ ] Welle war self-contained (H5 grün) — kein Nachlesen nötig
- [ ] EU-Routing sauber (E1) · keine Klartext-PII (E2) · Modelle gepinnt (F1)

## Gruppierung der Stories
- Backend Fundament/Querschnitt: W1, W2, W3
- Backend Phase 1: W4, W5, W6
- Coaching-MCP: W7
- Web-UI Phase 1: W8, W9
- Docker: W10
- Backend Phase 2: W11, W12, W13, W14
- Tauri-Overlay Phase 2: W15, W16
- Tests/Latenz: W17
