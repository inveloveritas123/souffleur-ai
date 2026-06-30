# apps/web — Phase-1-Web-UI (React + Vite + TypeScript)

Schlanke Web-Oberfläche für den Async-Protokoll-MVP. Begründung des Stacks: React + Vite ist Playwright-testbar, hat das größte Ökosystem und Tauri (Phase 2) scaffoldet nativ mit React + Vite, sodass Komponenten zwischen Web und Overlay wiederverwendbar sind.

## Was hier hineingehört

- `src/` — Views: Einwilligung erteilen, Audio hochladen bzw. aufnehmen, Protokoll-Anzeige mit Sprecher-Labels, Export (Markdown, PDF).
- `tests/` — Playwright-E2E: Pfad Einwilligung, Upload, Protokoll-Anzeige (Akzeptanzkriterium 9).

## Anbindung

REST und WebSocket zum Backend (Port aus SOUFFLEUR_BACKEND_PORT). Kein direkter Modellzugriff; alles über das Backend.

## Welle 8 — Stand

- Stack: React 19 + Vite 8 + TypeScript 6 (strict), React Router 7. Kein UI-Framework (schlank gehalten).
- Routen: `/consent` (Einwilligung), `/upload` (Upload/Aufnahme, nur mit Einwilligung erreichbar via `RequireConsent`), `/protocol` bzw. `/protocol/:protocolId` (Protokoll-Anzeige + Export).
- API-Client (`src/api/client.ts`): spricht ausschließlich das eigene Backend über `VITE_SOUFFLEUR_API_BASE` an (Default `http://localhost:8000`); Endpunkte `/api/v1/consent`, `/api/v1/protocol` (POST), `/api/v1/protocol/:id` (GET). Backend existiert zum Zeitpunkt von Welle 8 noch nicht — der Client tippt gegen einen definierten Vertrag (`src/api/wire.ts`).
- Setup: `cp .env.example .env.local` (optional, Default reicht lokal), dann `npm install && npm run build`.
- Skripte: `npm run dev`, `npm run build` (tsc --noEmit + vite build), `npm run typecheck`, `npm run preview`.

## Welle 9 — Stand

- Playwright-E2E (`tests/e2e/`) deckt den Phase-1-Flow ab: Einwilligung erteilen → Audio hochladen → Protokoll anzeigen, jeweils gegen ein per `page.route()` gemocktes Backend (`tests/e2e/mocks.ts`, realistische Fixtures inkl. diarisiertem Transkript und Zusammenfassung). apps/backend läuft im Test **nicht**.
- Testfälle: `phase1-flow.spec.ts` (Happy Path inkl. Markdown- und PDF-Export-Trigger), `consent-gate.spec.ts` (Einwilligung als Pflicht-Schritt: Redirect ohne Consent, Backend-403 bei fehlender Einwilligung, Freischaltung der Navigation nach Bestätigung).
- Setup: `npx playwright install chromium` (einmalig). Lauf: `npx playwright test` bzw. `npm run test:e2e`. Die Config (`playwright.config.ts`) startet automatisch `npm run dev` als Webserver auf `SOUFFLEUR_WEB_PORT`/5173.
- Export: Markdown per Blob-Download (`<a download>`, Test prüft `page.waitForEvent("download")`); PDF per Druckansicht in eigenem Fenster (`window.open` + `window.print()`), Test prüft das Popup-Event und stubbt `window.print` zur deterministischen Prüfung des Auslösens.
- Artefakte (`playwright-report/`, `test-results/`) sind gitignored.
