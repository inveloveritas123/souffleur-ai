# apps/web — Phase-1-Web-UI (React + Vite + TypeScript)

Schlanke Web-Oberfläche für den Async-Protokoll-MVP. Begründung des Stacks: React + Vite ist Playwright-testbar, hat das größte Ökosystem und Tauri (Phase 2) scaffoldet nativ mit React + Vite, sodass Komponenten zwischen Web und Overlay wiederverwendbar sind.

## Was hier hineingehört

- `src/` — Views: Einwilligung erteilen, Audio hochladen bzw. aufnehmen, Protokoll-Anzeige mit Sprecher-Labels, Export (Markdown, PDF).
- `tests/` — Playwright-E2E: Pfad Einwilligung, Upload, Protokoll-Anzeige (Akzeptanzkriterium 9).

## Anbindung

REST und WebSocket zum Backend (Port aus SOUFFLEUR_BACKEND_PORT). Kein direkter Modellzugriff; alles über das Backend.
