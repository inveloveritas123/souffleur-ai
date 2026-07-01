# Souffleur AI

**EU-souveräner Echtzeit-Coaching-Copilot.** Semitransparentes, screen-share-unsichtbares Overlay + Async-Protokoll — auf einer EU-Kette (Mistral/Voxtral, Paris), einwilligungsbasiert und DSGVO-/§201-konform. Der bewusste Gegenentwurf zu Cluely: transparent, EU-souverän, mit Einwilligung.

Gebaut mit **WERKBANK** (BMAD-Methode · kiln-Autonomie · WERKBANK-Governance/Gates). Details der Vision: `docs/concept/`.

> **Geltung: intern, OHNE echte personenbezogene Kundendaten.** Vor Echtbetrieb: §201 StGB + Art. 9 DSGVO + EU-AI-Act über Carsten Lexa (siehe `privacy/` + Konzept Kap. 7). Die menschliche Security-/Datenschutz-Abnahme (Gates J1/J2) ist bewusst NICHT vom Agenten signierbar.

## Architektur (4 Schichten)
1. **Capture** — lokal: System-Audio (Gegenüber) + Mic (Coach) getrennt (Overlay) · Phase-1: Datei-Upload
2. **Transcribe** — austauschbarer STT-Port: `voxtral_api` (Cloud, default) · `voxtral_local` (MLX, on-device, kostenfrei) · `gladia` (EU-Drop-in)
3. **Reasoning** — Trigger-Router (`ministral-3b`, „Karte ja/nein?") + Coaching-Wissensschicht als MCP + Antwort-Streaming (`magistral-medium`)
4. **Display** — Phase 1: Web-Protokoll · Phase 2: Tauri-Overlay (transparent, always-on-top, `NSWindow.sharingType=.none` → nicht in Screen-Share)

Gepinnte Modelle (Gate F1): Live-STT `voxtral-mini-transcribe-realtime-2602` · Batch+Diarisation `voxtral-mini-2602` · Reasoning `magistral-medium-2509` · Trigger `ministral-3b-2512`. EU-Endpunkt `https://api.mistral.ai`.

## Monorepo
```
apps/backend      FastAPI: STT-Port + Adapter, LlmPort, ConsentGate, AuditLog, Phase-1-REST, Phase-2-WebSocket, Event-Bus, Trigger-Router, Reasoning
apps/web          React+Vite+TS: Consent → Upload → Protokoll (Phase 1)
apps/overlay      Tauri (macOS): screen-share-unsichtbares Live-Overlay (Phase 2)
packages/coaching-mcp   MCP-Wissensschicht (Coaching-IP: Einwand/Frage/Struktur)
packages/shared   geteilte Typen + Modell-Pins
docker/           docker-compose (backend/coaching-mcp/web)
privacy/          DSGVO-Artefakte (DATA-FLOW, DPIA, PROCESSING-REGISTER, TOMs, …)
gates/            WERKBANK-Quality-Gates  ·  scripts/gate.sh = kanonischer pii-Lauf
```

## Schnellstart (morgen früh)

### 0. Secret (einmalig)
Der Mistral-Key liegt **außerhalb** des Repos unter `~/.config/souffleur/souffleur.env` (nie committen). `.env.example` zeigt alle Variablen.

### A. Backend + Coaching-MCP + Web via Docker (Cloud-Kette)
```bash
docker compose -f docker/docker-compose.yml up --build
# Backend :8000  ·  Coaching-MCP :8080  ·  Web :5173
```

### B. Backend lokal (nötig für die lokale MLX-STT-Option — MLX läuft nicht in Docker)
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
source scripts/load-env.sh                    # lädt den Key von außerhalb des Repos
export SOUFFLEUR_STT_PROVIDER=voxtral_api      # oder: voxtral_local (MLX, kostenfrei) | gladia
uvicorn souffleur.core.app:app --app-dir apps/backend/src --port 8000
```

### C. Web-UI (Phase 1) separat
```bash
cd apps/web && npm install && npm run dev      # http://localhost:5173
```

### D. Overlay (Phase 2, macOS)
```bash
source $HOME/.cargo/env
cd apps/overlay && npm install && npm run tauri dev
# Beim ersten Start Mikrofon- + Bildschirmaufnahme-Berechtigung erteilen (siehe apps/overlay/README.md)
```

### Kostenspar-Option (lokal, ohne API-Kosten)
`SOUFFLEUR_STT_PROVIDER=voxtral_local` → dasselbe Voxtral-Modell on-device via MLX (Apple Silicon, ~2,5 GB Q4, Lazy-Download beim ersten Lauf). Backend dafür lokal starten (B), nicht in Docker.

## Tests & Gates
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
python3 -m pytest apps/backend/tests packages/coaching-mcp/tests -q   # Backend + MCP
cd apps/web && npx playwright test                                    # Web-E2E
bash scripts/gate.sh pii                                              # WERKBANK-Gates (Zielprofil pii)
```
**Hartes Grün:** jedes Pflicht-Gate des Profils muss PASS sein (SKIP ⇒ ROT).

## Status
Phase 1 (Async-Protokoll) + Phase 2 (Live-Overlay) implementiert, test-first, WERKBANK-Gates `pii`. Live-Streaming-WS-Wireformat ist gegen die dokumentierte Mistral-Realtime-API gebaut und braucht eine finale Verifikation am Live-Endpunkt (Batch-Transkription ist real verifiziert, HTTP 200).
