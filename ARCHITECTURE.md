# ARCHITECTURE — Souffleur AI

> Vier entkoppelte Schichten (Capture, Transcribe, Reasoning, Display). Single-Provider Mistral (Paris, EU).
> STT als austauschbarer Port. Transkript-Event-Bus als Modul-Schnittstelle (Phase 3). Monorepo.

## Überblick

Souffleur AI folgt der Referenzarchitektur des Konzepts: vier entkoppelte Schichten, deren Schnittstelle ein Transkript-/Event-Stream ist. Genau dieser Event-Bus macht die Schichten 2 bis 4 später (Phase 3) zu einem einbettbaren Modul. Phase 1 nutzt Schicht 1, 2 und 3 im Batch-Modus (Async-Protokoll), Phase 2 ergänzt Live-Capture, den Trigger-Router und die Display-Schicht (Overlay).

Grenzen: Audio-Capture ist lokal (Overlay bzw. Browser). Transkription und Reasoning laufen in der EU-Cloud (Mistral, Paris) oder optional lokal (MLX). Das Display ist lokal. Es verlässt nichts die EU.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SOUFFLEUR AI — 4 Schichten                                                │
│                                                                            │
│  1. CAPTURE            2. TRANSCRIBE          3. REASONING                  │
│  ┌──────────────┐      ┌────────────────┐     ┌────────────────────────┐   │
│  │ Phase1: Web  │      │ TranscriptionPort│   │ TriggerRouter           │   │
│  │  Upload /    │      │  (austauschbar)  │   │  Regeln + ministral-3b  │   │
│  │  Mic-Record  │─PCM─▶│ ┌──────────────┐ │──▶│   "Karte ja/nein?"      │   │
│  │ Phase2: Tauri│ JSON │ │ voxtral_api  │ │   │          │              │   │
│  │  Dual-Source │◀────▶│ │ voxtral_local│ │   │          ▼              │   │
│  │  (Sys + Mic) │      │ │ gladia (FB)  │ │   │ ReasoningEngine         │   │
│  └──────────────┘      │ └──────────────┘ │   │  magistral-medium-2509  │   │
│        │               └────────┬─────────┘   │   + Coaching-MCP        │   │
│        │                        │             │  (Wissen zur Laufzeit)  │   │
│        │                        ▼             └────────────┬────────────┘   │
│        │              ┌───────────────────────┐            │                │
│        └─────────────▶│  TRANSKRIPT-EVENT-BUS │◀───────────┘                │
│                       │  (async pub/sub)       │                            │
│                       └───────────┬───────────┘                            │
│                                   ▼                                         │
│  4. DISPLAY                 ┌─────────────────────────────────────────┐    │
│   Phase1: Web-Protokoll     │  Phase2: Tauri-Overlay (semitransparent) │   │
│   (Markdown / PDF)          │  sharingType=none → screen-share-unsichtbar│  │
│                             └─────────────────────────────────────────┘    │
│                                                                            │
│  Querschnitt: AuditLog (E4-Schema) · ConsentGate (§201) · Config/Env       │
│      Lokal (Overlay/Web)        EU-Cloud (Mistral Paris)        Lokal       │
└──────────────────────────────────────────────────────────────────────────┘
```

## Komponenten

| Komponente | Verantwortung | Schnittstellen |
|---|---|---|
| `apps/backend` (FastAPI) | Orchestriert Schicht 2 bis 4, Consent-Gate, Audit-Log, Event-Bus | REST + WebSocket; ruft Ports |
| `TranscriptionPort` + Adapter | STT/Diarisation abstrahiert; Wechsel per Env | `adapters/stt/{voxtral_api,voxtral_local,gladia}` |
| `LlmPort` + Adapter | Reasoning und Trigger-Klassifikation über Mistral | `adapters/llm/mistral` |
| `TranscriptEventBus` | Async pub/sub zwischen Schicht 2 und 3/4; Modul-Schnittstelle | in-process asyncio; später Netzwerk-Adapter |
| `TriggerRouter` | Entscheidet wann eine Karte sinnvoll ist (Regeln + ministral-3b) | konsumiert Bus, ruft `LlmPort` |
| `ReasoningEngine` | Erzeugt Coaching-Karten und Protokoll-Zusammenfassung | ruft `LlmPort` + Coaching-MCP |
| `packages/coaching-mcp` | Coaching-Frameworks/Fragetechniken als strukturiertes Wissen (IP) | MCP-Server (stdio/HTTP) |
| `ConsentGate` | Erzwingt dokumentierte Einwilligung vor Verarbeitung (§201) | Middleware; 403 ohne Consent |
| `AuditLog` | Unveränderliche Einträge nach E4-Schema | JSONL; routing_region EU |
| `apps/web` (React+Vite) | Phase 1: Consent, Upload, Protokoll-Anzeige/Export | REST/WS zum Backend; Playwright |
| `apps/overlay` (Tauri) | Phase 2: Dual-Source-Capture + Karten-Overlay | WS zum Backend; macOS sharingType none |
| `packages/shared` | Geteilte Typen/Schemas (Transcript, Event, Card) | TS + JSON-Schema, vom Backend gespiegelt |

## STT-Port-Interface (Methoden-Signaturen)

Das Port-Interface ist so entworfen, dass der Provider-Wechsel reine Konfiguration ist (`SOUFFLEUR_STT_PROVIDER`). Eine Factory wählt den Adapter; kein Aufrufer kennt den konkreten Provider. Signaturen (Python, `apps/backend/src/souffleur/ports/transcription.py`):

```python
class TranscriptionPort(Protocol):
    # Phase 2 — Live-Streaming
    async def open_stream(self, session: SessionContext) -> StreamHandle: ...
    async def push_audio(self, handle: StreamHandle, pcm_chunk: bytes) -> None: ...
    async def events(self, handle: StreamHandle) -> AsyncIterator[TranscriptEvent]: ...
    async def close_stream(self, handle: StreamHandle) -> TranscriptResult: ...

    # Phase 1 — Batch (Protokoll mit Diarisation + Wort-Zeitstempeln)
    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult: ...

    # Metadaten — erlaubt latenz-/feature-bewusstes Routing
    def capabilities(self) -> ProviderCapabilities: ...


def build_transcription_port(settings: Settings) -> TranscriptionPort:
    # liest settings.stt_provider (SOUFFLEUR_STT_PROVIDER); mappt auf Adapter
    ...
```

Hilfstypen (in `ports/types.py`, gespiegelt nach `packages/shared`):
- `SessionContext`: tenant_id, session_id, consent_ref, sample_rate, channels (2 für Dual-Source), language.
- `StreamHandle`: provider-internes Handle plus correlation_id.
- `TranscriptEvent`: kind (partial/final), speaker, text, t_start_ms, t_end_ms, words (optional, Wort-Zeitstempel).
- `TranscriptResult`: segments (Liste TranscriptEvent final), speakers, duration_ms, model, provider.
- `ProviderCapabilities`: supports_streaming, supports_diarization, supports_word_timestamps, typical_final_latency_ms, residency ("EU").
- `AudioRef`: lokaler Pfad oder Stream-Quelle (kein Audio im Log).
- `BatchOptions`: diarization (bool), word_timestamps (bool), language, num_speakers_hint.

Adapter-Verträge:
- `voxtral_api` (Default): nutzt Mistral Transcribe (voxtral-mini-2602 Batch, voxtral-mini-realtime-2602 Live) über api.mistral.ai. Volle Diarisation und Wort-Zeitstempel.
- `voxtral_local`: gleiche Open-Weights via MLX auf Apple Silicon; Kostenspar-Option, residency EU/lokal, Latenz nicht garantiert.
- `gladia`: Drop-in-Fallback, EU-Endpunkt (Frankreich), nur falls Live-Latenz gemessen nicht ausreicht.

## Event-Bus-Schema

`TranscriptEventBus` ist ein async In-Process-Pub/Sub (asyncio Queues pro Session), gekapselt hinter einem schmalen Interface, damit Phase 3 einen Netzwerk-Adapter (z. B. WebSocket/Redis) einsetzen kann, ohne Schicht 3/4 zu ändern.

```python
class TranscriptEventBus(Protocol):
    async def publish(self, session_id: str, event: BusEvent) -> None: ...
    def subscribe(self, session_id: str) -> AsyncIterator[BusEvent]: ...
```

`BusEvent` (JSON-Schema in `packages/shared`):
```json
{
  "type": "transcript.partial | transcript.final | trigger.fired | card.proposed | card.streamed | session.closed",
  "session_id": "uuid",
  "tenant_id": "string",
  "seq": 0,
  "ts_ms": 0,
  "payload": { "speaker": "coach|counterpart", "text": "string", "t_start_ms": 0, "t_end_ms": 0 },
  "correlation_id": "uuid"
}
```
Schicht 2 publiziert `transcript.*`. Der Trigger-Router konsumiert `transcript.final`, publiziert `trigger.fired`. Die Reasoning-Engine konsumiert `trigger.fired`, publiziert `card.proposed`/`card.streamed`. Die Display-Schicht (Overlay/Web) abonniert `card.*` und `transcript.*`.

## Trigger-Router-Logik

Ziel: das teure Reasoning-Modell läuft nicht auf jeder Äußerung. Zweistufig, fail-fast:

1. **Regel-Vorfilter (deterministisch, schnell):** feuert bei erkanntem Einwand-Marker, Fragezeichen, längerer Pause (Stille über Schwellwert) oder konfigurierten Schlüsselbegriffen. Negativ-Filter unterdrückt Backchannel ("mhm", "ja genau") und zu kurze Segmente. Dieser Pfad ist als deterministischer Unit-Test abgedeckt (Akzeptanzkriterium 5).
2. **LLM-Klassifikator (ministral-3b-2512, billig/schnell):** nur wenn der Vorfilter unsicher ist, klassifiziert das kleine Modell das Segment in Karte/keine-Karte plus Karten-Typ (Einwand, vertiefende Frage, Strukturhinweis). Latenzbudget circa 50 bis 150 ms.

Bei `Karte` publiziert der Router `trigger.fired` mit Karten-Typ; die Reasoning-Engine holt passendes Coaching-Wissen aus dem MCP-Server und streamt die Karte. Cooldown verhindert Karten-Spam.

## Daten- und Latenzfluss (Phase 2, Ziel unter zwei Sekunden)

```
Äußerungsende → Capture(lokal, ~0) → Netz→Mistral EU(~20-50ms) → Voxtral final(~270ms)
  → Bus(transcript.final) → TriggerRouter(Regeln 0ms / ministral-3b 50-150ms)
  → ReasoningEngine + Coaching-MCP → magistral-medium erste Tokens(streamed)
  → Bus(card.streamed) → Overlay baut Karte auf
```
Entscheidend: streamen (Karte baut sich auf) und nur bei Trigger feuern. Latenz wird mit einem reproduzierbaren Messskript belegt (Akzeptanzkriterium 10).

## Datenfluss & PII (Gate E1/E2)

PII entsteht in Audio, Transkript und Karten. Schutz: (a) EU-Routing erzwungen — alle Modellaufrufe gehen über api.mistral.ai (Paris); kein Code/Config referenziert einen Non-EU-Endpunkt oder eine Non-EU-Region (Gate E1). (b) Logs, Prompts und Outputs enthalten keine Klartext-PII; Gesprächsinhalte werden nicht ins Audit-Log geschrieben (Audit-Felder sind Metadaten, pii_present gleich false, Gate E2/E4). (c) Audio und Transkripte unterliegen Aufbewahrungs- und Löschregeln (privacy/RETENTION-DELETION.md).

## Mandantentrennung

Phase 1 und 2 sind effektiv single-tenant (eine Coach-Organisation). `tenant_id` wird dennoch durchgängig in SessionContext, BusEvent und Audit-Log geführt, damit die spätere Mehrmandantenfähigkeit (Phase 3, Gate E3) keine Schema-Migration erfordert. Verarbeitung ohne tenant_id wird abgelehnt.

## Modell-Routing & Pinning (Gate E1, F1)

Alle Modelle über die EU-Basis-URL `https://api.mistral.ai`. Gepinnte Versionen, kein bewegliches Tag:

| Rolle | Modell (gepinnt) | Schicht | Env-Variable |
|---|---|---|---|
| Live-STT (Overlay) | voxtral-mini-realtime-2602 | 2 (Phase 2) | SOUFFLEUR_MODEL_STT_LIVE |
| Batch-STT + Diarisation | voxtral-mini-2602 | 2 (Phase 1) | SOUFFLEUR_MODEL_STT_BATCH |
| Reasoning (Coaching-Antwort) | magistral-medium-2509 | 3 | SOUFFLEUR_MODEL_REASONING |
| Trigger-Router | ministral-3b-2512 | 3 | SOUFFLEUR_MODEL_TRIGGER |

Verbote: niemals api.openai.com, niemals us-Cross-Region-Modellpräfixe, niemals eine Non-EU-Region in Code/Config; niemals das bewegliche latest-Tag (Gate F1). Gladia-Endpunkt ist EU (Frankreich) und damit zulässig.

## Config / Env-Variablen

Vollständig dokumentiert in `.env.example`. Kernvariablen: MISTRAL_API_KEY (nur Referenz, nie committet), MISTRAL_BASE_URL gleich https://api.mistral.ai, SOUFFLEUR_STT_PROVIDER (voxtral_api default), die vier gepinnten Modell-IDs, GLADIA_API_KEY und GLADIA_BASE_URL (nur falls Fallback aktiv, EU), Ports (Backend 8000, Web 5173, MCP 8080), SOUFFLEUR_AUDIT_LOG_PATH, SOUFFLEUR_RETENTION_DAYS, SOUFFLEUR_TENANT_ID.

## Docker-Topologie

`docker-compose.yml` (in `docker/`) startet vier Dienste:
- `backend` (FastAPI, Port 8000) — Orchestrierung, Bus, Ports, Audit, Consent.
- `voxtral-worker` (optional, Profil `local-stt`) — lokaler MLX-Voxtral-Adapter auf Apple Silicon; nur aktiv bei SOUFFLEUR_STT_PROVIDER gleich voxtral_local.
- `coaching-mcp` (Port 8080) — MCP-Server mit Coaching-Wissen.
- `web` (Vite Dev/Preview, Port 5173) — Phase-1-UI.

Das Tauri-Overlay (`apps/overlay`) wird nativ als macOS-App gebaut (nicht in Docker, da Screen-Capture und NSWindow native Rechte brauchen) und spricht das Backend über WebSocket an.

## Monorepo-Verzeichnislayout (exakte Pfade für Build-Subagenten)

```
.
├── SPEC.md
├── ARCHITECTURE.md
├── TASKS.md
├── CHANGELOG.md
├── .env.example
├── apps/
│   ├── backend/                    # FastAPI (Python)
│   │   ├── src/souffleur/
│   │   │   ├── api/                # REST + WebSocket Routen
│   │   │   ├── core/              # Settings, ConsentGate, Lifecycle
│   │   │   ├── ports/             # transcription.py, llm.py, types.py
│   │   │   ├── adapters/
│   │   │   │   ├── stt/           # voxtral_api, voxtral_local, gladia, factory
│   │   │   │   ├── llm/           # mistral
│   │   │   │   └── capture/       # dual_source (Phase 2)
│   │   │   ├── bus/               # TranscriptEventBus
│   │   │   ├── trigger/           # Regeln + ministral-3b Klassifikator
│   │   │   └── audit/             # AuditLog (E4-Schema)
│   │   └── tests/
│   ├── web/                        # React + Vite + TS (Phase 1)
│   │   ├── src/
│   │   └── tests/                 # Playwright
│   └── overlay/                    # Tauri (Phase 2, macOS)
│       ├── src/                   # Frontend des Overlays (React)
│       └── src-tauri/             # Rust (Capture, NSWindow sharingType none)
├── packages/
│   ├── coaching-mcp/               # MCP-Server (IP)
│   │   ├── src/
│   │   └── knowledge/             # Coaching-Frameworks/Fragetechniken
│   └── shared/                     # geteilte Typen/Schemas (TS + JSON-Schema)
│       └── src/
├── docker/                         # docker-compose.yml + Dockerfiles
├── privacy/                        # DSGVO-Artefakte
├── tests/
│   ├── e2e/                       # übergreifende E2E
│   └── unit/                      # übergreifende Unit
├── gates/                          # WERKBANK (bestehend, nicht anfassen)
└── templates/                      # WERKBANK (bestehend, nicht anfassen)
```

## Phase-1-vs-Phase-2-Abgrenzung

- **Phase 1 (Async-Protokoll-MVP):** kein Overlay, kein Live-Streaming, kein Trigger-Router. Pipeline ist Web-Upload → ConsentGate → voxtral-mini-2602 Batch (Diarisation, Wort-Zeitstempel) → magistral-medium-2509 Zusammenfassung → Protokoll-Anzeige und Export. Geringes Risiko, sofortiger Nutzen, einfache Einwilligung. Liefert dem Gegenüber das versprochene Protokoll.
- **Phase 2 (Live-Overlay):** ergänzt Tauri-Overlay, Dual-Source-Capture, voxtral-mini-realtime-2602 Streaming, TranscriptEventBus, TriggerRouter (ministral-3b) und gestreamte Karten. Screen-share-unsichtbar. Teilt sich ConsentGate, AuditLog, LlmPort und Coaching-MCP mit Phase 1.
- **Phase 3 (nur Ausblick, out of scope):** Schicht 2 bis 4 als Netzwerk-Modul über den Event-Bus; Cloud-Bot-Capture-Adapter (Variante B); Mehrmandantenfähigkeit (Gate E3).

## Drift-Kontrolle

SPEC.md und ARCHITECTURE.md teilen dieselben Bezeichner (Schichten, Modell-Pinning-Tabelle, STT-Provider-Werte, Akzeptanzkriterien). TASKS.md leitet jede Welle aus genau diesen Komponenten ab. Änderungen an Modell-Pins oder Port-Signaturen sind in beiden Dokumenten und in `.env.example` synchron zu halten (Gate H6).
