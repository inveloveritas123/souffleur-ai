# GATE-REPORT — target=`.` — 2026-07-01T00:20:32Z

## Zusammenfassung
- **Ergebnis:** ROT
- **Profil (Pflichtenheft):** `pii` — Verarbeitet personenbezogene Daten (DSGVO) — EU-Routing, PII-frei, Audit-Log, Artefakte, DPIA
- **Pflicht-Gates bestanden:** 16/17
- **Pflicht-Gates VERLETZT (FAIL):** 0
- **Pflicht-Gates UNGEDECKT (nicht geprueft):** 1
- **Pflicht-Gates ohne PASS:** 1
- **Optionale Befunde (warn):** 3
- **Hinweis — Block-Gates rot ausserhalb des Profils (nicht blockend):** 1

> **Hartes Gruen:** GRUEN gilt NUR, wenn alle 17 Pflicht-Gates aktiv bestanden sind. SKIP eines Pflicht-Gates (Tool fehlt / kein Check / kein Kontext) ⇒ UNGEDECKT ⇒ ROT.

## Warum ROT — Pflicht-Gates ohne PASS
- **C2 UNGEDECKT** (skip) — coverage-Report nicht lesbar

## Hinweis — rote Block-Gates ausserhalb des Profils (beratend, nicht verdikt-relevant)
> Diese Gates sind nicht Teil von `pii`. Fuer harte Pflicht ins Profil aufnehmen.
- **C4 ROT** — E2E rot (Playwright, apps/web/playwright.config.ts)

## Detail je Stufe (Flags ★pflicht = Pflicht-Gate dieses Profils)
| Stufe | Gate | Flags | Ergebnis | Notiz |
|---|---|---|---|---|
| 1_spec | A1 | block,deterministic,★pflicht | PASS | alle 6 Spec-Pflichtfelder gefüllt |
| 1_spec | A2 | block,deterministic,★pflicht | PASS | 10 testbare Akzeptanzkriterien |
| 1_spec | A3 | block,deterministic,★pflicht | PASS | Handoff PM→Architect erfüllt |
| 1_spec | A4 | warn,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 2_static | B1 | block,deterministic,★pflicht | PASS | ruff sauber |
| 2_static | B2 | block,deterministic,★pflicht | PASS | mypy sauber |
| 2_static | B3 | block,deterministic,★pflicht | PASS | Build/Compile sauber (60 .py) |
| 2_static | D1 | block,deterministic,★pflicht | PASS | kein High/Medium (382 Low, beraten) |
| 2_static | D2 | block,deterministic | SKIP | pip-audit/safety nicht installiert |
| 2_static | D3 | block,deterministic,★pflicht | PASS | kein Secret gefunden |
| 2_static | D4 | warn,deterministic | SKIP | pip-licenses nicht installiert |
| 3_tests | C1 | block,deterministic,★pflicht | PASS | Tests grün (0 Tests in tests) |
| 3_tests | C2 | block,deterministic,★pflicht | SKIP | coverage-Report nicht lesbar |
| 3_tests | C3 | block,deterministic | SKIP | keine Integrationstests |
| 3_tests | C4 | block,deterministic | FAIL | E2E rot (Playwright, apps/web/playwright.config.ts) |
| 3_tests | C5 | warn,deterministic | SKIP | keine Concurrency-/Race-Tests |
| 3_tests | C6 | warn,deterministic | SKIP | kein a11y/axe-Setup |
| 4_sovereignty_dsgvo | E1 | block,deterministic,★pflicht | PASS | kein Non-EU-Endpunkt/Region referenziert |
| 4_sovereignty_dsgvo | E2 | block,deterministic,★pflicht | PASS | keine Klartext-PII in Logs/Prompts/Outputs |
| 4_sovereignty_dsgvo | E3 | block,deterministic | PASS | keine Tenant-übergreifenden Zugriffe (Audit-Log) |
| 4_sovereignty_dsgvo | E4 | block,deterministic,★pflicht | PASS | Audit-Log schema-konform (3 Einträge) |
| 4_sovereignty_dsgvo | E5 | block,deterministic,★pflicht | PASS | alle 11 Soll-Artefakte vorhanden, gefuellt, platzhalterfrei, EU |
| 4_sovereignty_dsgvo | E6 | block,deterministic,★pflicht | PASS | hohes Risiko — DPIA.md vorhanden und gefüllt |
| 4_sovereignty_dsgvo | E7 | warn,deterministic | PASS | keine Drittlandübermittlung (EU/EWR-only) |
| 4_sovereignty_dsgvo | E8 | warn,llm | PASS | Datenminimierung dokumentiert; Art-9-Disziplin ok |
| 5_integrity | F1 | block,deterministic,★pflicht | PASS | kein 'latest' — Modelle gepinnt |
| 5_integrity | F2 | block,deterministic | SKIP | kein Modell gepinnt |
| 5_integrity | F3 | warn,deterministic | SKIP | kein Snapshot-Verzeichnis |
| 6_perf | G1 | warn,deterministic | SKIP | kein Lasttest konfiguriert |
| 6_perf | G2 | warn,deterministic | SKIP | kein Build-Output (dist/ oder build/) |
| 6_perf | G3 | warn,deterministic | WARN | 15 Query-in-Loop-Verdacht (N+1) |
| 7_maintainability | H1 | warn,deterministic | PASS | alle TODO/FIXME getrackt (oder keine) |
| 7_maintainability | H2 | warn,deterministic | WARN | 5 Funktion(en) ueber Komplexitaet 12 |
| 7_maintainability | H3 | warn,deterministic | WARN | keine README (README.md/README.rst) |
| 7_maintainability | H4 | block,deterministic,★pflicht | PASS | CHANGELOG vorhanden, 1 Einträge, newest-top |
| 7_maintainability | H5 | warn,deterministic | PASS | 17 offene Welle(n) self-contained (Dateien/Verbote/Smoke/Akzeptanz) |
| 7_maintainability | H6 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I1 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I2 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I3 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 9_freigabe | J1 | block,deterministic | SKIP | keine Produktivfreigabe (docs/produktivfreigabe/FREIGABE.yaml) |
| 9_freigabe | J2 | block,deterministic | SKIP | keine Produktivfreigabe (docs/produktivfreigabe/FREIGABE.yaml) |
| 10_branche | K1 | block,deterministic,branch | SKIP | keine Branche aktiviert (--branch / .werkbank/branch.txt) |
| 10_branche | K2 | block,deterministic,branch | SKIP | keine Branche aktiviert |

## Funde (redigiert — keine Klartext-Secrets/PII)
- **C4** — FAIL — E2E rot (Playwright, apps/web/playwright.config.ts)
    - `apps/web/playwright.config.ts:0` [e2e-failure] *********************************************************
********
> 19 | test.describe("Phase-1-Flow (Consent → Upload → Protokoll…> 19 | test.describe("Phase-1-Flow (Consent → Upload → Protokoll)", () => {
********
*****************************************************
****************************************
*****************************************
at _TestTypeImpl._currentSuite (/Users/roberthargesheimer/Docume…at _TestTypeImpl._currentSuite (/Users/roberthargesheimer/Documents/Claude/Projects/Souffleur AI/apps/web/node_modules/playwright/lib/common/index.js:2257:13)
at _TestTypeImpl._describe (/Users/roberthargesheimer/Documents/…at _TestTypeImpl._describe (/Users/roberthargesheimer/Documents/Claude/Projects/Souffleur AI/apps/web/node_modules/playwright/lib/common/index.js:2298:24)
at Function.describe (/Users/roberthargesheimer/Documents/Claude…at Function.describe (/Users/roberthargesheimer/Documents/Claude/Projects/Souffleur AI/apps/web/node_modules/playwright/lib/common/index.js:1220:12)
at /Users/roberthargesheimer/Documents/Claude/Projects/Souffleur…at /Users/roberthargesheimer/Documents/Claude/Projects/Souffleur AI/apps/web/tests/e2e/phase1-flow.spec.ts:19:6
*********************
- **G3** — WARN — 15 Query-in-Loop-Verdacht (N+1)
    - `apps/backend/src/souffleur/bus/event_bus.py:115` [n+1-query] *********
    - `apps/backend/src/souffleur/adapters/llm/mistral.py:58` [n+1-query] *********
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:168` [n+1-query] ***********
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:170` [n+1-query] ***********
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:323` [n+1-query] ***************
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:328` [n+1-query] ***************
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:329` [n+1-query] ***************
    - `apps/backend/src/souffleur/adapters/stt/voxtral_api.py:330` [n+1-query] ***************
    - `apps/backend/src/souffleur/adapters/stt/gladia.py:222` [n+1-query] ****************
    - `apps/backend/src/souffleur/adapters/stt/gladia.py:225` [n+1-query] ********
    - `apps/backend/src/souffleur/adapters/stt/gladia.py:231` [n+1-query] ********
    - `apps/backend/src/souffleur/api/live.py:148` [n+1-query] ***********
    - `apps/backend/src/souffleur/api/live.py:150` [n+1-query] ***********
    - `apps/backend/src/souffleur/api/live.py:154` [n+1-query] ***********
    - `apps/backend/src/souffleur/api/live.py:161` [n+1-query] ***********
- **H2** — WARN — 5 Funktion(en) ueber Komplexitaet 12
    - `apps/backend/tests/test_voxtral_api.py:102` [complexity] test_transcribe_batch_returns_diarized_result_with_word_timestamps() = 16
    - `apps/backend/tests/test_voxtral_local.py:131` [complexity] test_transcribe_batch_parses_segments_and_words() = 14
    - `apps/backend/tests/test_gladia.py:156` [complexity] test_transcribe_batch_happy_path_parses_diarized_result() = 19
    - `apps/backend/tests/test_protocol_api.py:184` [complexity] test_post_protocol_with_valid_consent_returns_diarized_protocol() = 29
    - `apps/backend/tests/test_live_api.py:182` [complexity] test_live_ws_accepts_audio_after_consent_and_forwards_transcript_and_card_events() = 21
- **H3** — WARN — keine README (README.md/README.rst)
    - `(root):0` [docs-missing] keine README gefunden

## Block-Regel
Mind. 1 Block-Gate rot ⇒ kein Push, kein Abhaken. E-Gate rot ⇒ STOPP + Mensch.
