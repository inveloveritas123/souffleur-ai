# apps/backend — Souffleur Backend (FastAPI, Python)

Orchestriert Schicht 2 bis 4 (Transcribe, Reasoning, Display-Anbindung) und die Querschnitts-Komponenten Consent, Audit und Event-Bus. Single-Provider Mistral (Paris, EU).

## Was hier hineingehört

- `src/souffleur/api/` — REST-Endpunkte (Phase 1: Upload, Protokoll) und WebSocket (Phase 2: Live-Stream, Karten).
- `src/souffleur/core/` — Settings (Env-Laden), ConsentGate (§201, HTTP 403 ohne Einwilligung), App-Lifecycle.
- `src/souffleur/ports/` — `transcription.py` (TranscriptionPort), `llm.py` (LlmPort), `types.py` (SessionContext, TranscriptEvent, BusEvent, Card). Signaturen siehe ARCHITECTURE.md.
- `src/souffleur/adapters/stt/` — `voxtral_api` (Default), `voxtral_local` (MLX), `gladia` (Fallback), plus `factory` (Wahl über SOUFFLEUR_STT_PROVIDER).
- `src/souffleur/adapters/llm/` — Mistral-Adapter für magistral-medium-2509 und ministral-3b-2512.
- `src/souffleur/adapters/capture/` — Dual-Source-Capture-Anbindung (Phase 2).
- `src/souffleur/bus/` — TranscriptEventBus (async pub/sub).
- `src/souffleur/trigger/` — Regel-Vorfilter plus ministral-3b-Klassifikator.
- `src/souffleur/audit/` — AuditLog nach templates/AUDIT-LOG.schema.json (routing_region EU, pii_present false).
- `tests/` — pytest (Unit), inkl. Adapter-Factory-Test und Consent-Gate-Test.

## Gates

EU-Routing (E1), kein latest-Tag (F1), keine Klartext-PII in Logs (E2), Audit-Schema (E4), ruff (B1), mypy (B2), Coverage (C2).
