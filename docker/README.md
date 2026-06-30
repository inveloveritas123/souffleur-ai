# docker — Container-Topologie

`docker-compose.yml` startet die Dienste des Monorepos. Apple-Silicon-kompatibel.

## Dienste

- `backend` — FastAPI, Port 8000. Orchestrierung, Bus, Ports, Audit, Consent.
- `coaching-mcp` — MCP-Server mit Coaching-Wissen, Port 8080.
- `web` — Vite (Phase-1-UI), Port 5173.
- `voxtral-worker` — optional, Compose-Profil local-stt; lokaler MLX-Voxtral-Adapter; nur aktiv bei SOUFFLEUR_STT_PROVIDER gleich voxtral_local.

## Nicht enthalten

Das Tauri-Overlay (apps/overlay) wird nativ als macOS-App gebaut (native Screen-Capture- und Fenster-Rechte) und nicht containerisiert.

## Konfiguration

Alle Variablen aus .env.example. Kein Secret im Image; nur Env-Referenzen.
