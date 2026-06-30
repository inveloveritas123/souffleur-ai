# GATE-REPORT — target=`.` — 2026-06-30T22:54:30Z

## Zusammenfassung
- **Ergebnis:** ROT
- **Profil (Pflichtenheft):** `basis` — Jedes Projekt — Mindestpflicht (Lint, Typen, Build, Tests, Coverage, Secrets, Pinning, Changelog)
- **Pflicht-Gates bestanden:** 3/8
- **Pflicht-Gates VERLETZT (FAIL):** 0
- **Pflicht-Gates UNGEDECKT (nicht geprueft):** 5
- **Pflicht-Gates ohne PASS:** 5
- **Optionale Befunde (warn):** 1

> **Hartes Gruen:** GRUEN gilt NUR, wenn alle 8 Pflicht-Gates aktiv bestanden sind. SKIP eines Pflicht-Gates (Tool fehlt / kein Check / kein Kontext) ⇒ UNGEDECKT ⇒ ROT.

## Warum ROT — Pflicht-Gates ohne PASS
- **B3 UNGEDECKT** (nicht anwendbar (Kontext fehlt)) — kein Python-Code
- **B1 UNGEDECKT** (Pflicht-Tool nicht installiert) — ruff nicht installiert
- **B2 UNGEDECKT** (Pflicht-Tool nicht installiert) — mypy nicht installiert
- **C1 UNGEDECKT** (nicht anwendbar (Kontext fehlt)) — kein Testverzeichnis gefunden
- **C2 UNGEDECKT** (Pflicht-Tool nicht installiert) — coverage nicht installiert

## Detail je Stufe (Flags ★pflicht = Pflicht-Gate dieses Profils)
| Stufe | Gate | Flags | Ergebnis | Notiz |
|---|---|---|---|---|
| 1_spec | A1 | block,deterministic | SKIP | kein SPEC (nicht anwendbar) |
| 1_spec | A2 | block,deterministic | SKIP | kein SPEC (nicht anwendbar) |
| 1_spec | A3 | block,deterministic | SKIP | kein SPEC (nicht anwendbar) |
| 1_spec | A4 | warn,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 2_static | B1 | block,deterministic,★pflicht | SKIP | ruff nicht installiert |
| 2_static | B2 | block,deterministic,★pflicht | SKIP | mypy nicht installiert |
| 2_static | B3 | block,deterministic,★pflicht | SKIP | kein Python-Code |
| 2_static | D1 | block,deterministic | SKIP | kein Python-Code |
| 2_static | D2 | block,deterministic | SKIP | kein Dependency-Manifest |
| 2_static | D3 | block,deterministic,★pflicht | PASS | kein Secret gefunden |
| 2_static | D4 | warn,deterministic | SKIP | pip-licenses nicht installiert |
| 3_tests | C1 | block,deterministic,★pflicht | SKIP | kein Testverzeichnis gefunden |
| 3_tests | C2 | block,deterministic,★pflicht | SKIP | coverage nicht installiert |
| 3_tests | C3 | block,deterministic | SKIP | keine Integrationstests |
| 3_tests | C4 | block,deterministic | SKIP | kein E2E konfiguriert |
| 3_tests | C5 | warn,deterministic | SKIP | keine Concurrency-/Race-Tests |
| 3_tests | C6 | warn,deterministic | SKIP | kein a11y/axe-Setup |
| 4_sovereignty_dsgvo | E1 | block,deterministic | PASS | kein Non-EU-Endpunkt/Region referenziert |
| 4_sovereignty_dsgvo | E2 | block,deterministic | PASS | keine Klartext-PII in Logs/Prompts/Outputs |
| 4_sovereignty_dsgvo | E3 | block,deterministic | SKIP | kein Audit-Log (nicht anwendbar) |
| 4_sovereignty_dsgvo | E4 | block,deterministic | SKIP | kein Audit-Log (nicht anwendbar) |
| 4_sovereignty_dsgvo | E5 | block,deterministic | SKIP | kein Privacy-Kontext (nicht anwendbar) |
| 4_sovereignty_dsgvo | E6 | block,deterministic | SKIP | kein Privacy-Kontext (nicht anwendbar) |
| 4_sovereignty_dsgvo | E7 | warn,deterministic | SKIP | kein Privacy-Kontext (nicht anwendbar) |
| 4_sovereignty_dsgvo | E8 | warn,llm | SKIP | kein Privacy-Kontext (nicht anwendbar) |
| 5_integrity | F1 | block,deterministic,★pflicht | PASS | kein 'latest' — Modelle gepinnt |
| 5_integrity | F2 | block,deterministic | SKIP | kein Modell gepinnt |
| 5_integrity | F3 | warn,deterministic | SKIP | kein Snapshot-Verzeichnis |
| 6_perf | G1 | warn,deterministic | SKIP | kein Lasttest konfiguriert |
| 6_perf | G2 | warn,deterministic | SKIP | kein Build-Output (dist/ oder build/) |
| 6_perf | G3 | warn,deterministic | SKIP | kein Python-Code |
| 7_maintainability | H1 | warn,deterministic | SKIP | kein Code-File (.py/.js/.ts/.go/.java) |
| 7_maintainability | H2 | warn,deterministic | SKIP | kein Python-Code |
| 7_maintainability | H3 | warn,deterministic | WARN | keine README (README.md/README.rst) |
| 7_maintainability | H4 | block,deterministic,★pflicht | PASS | CHANGELOG vorhanden, 1 Einträge, newest-top |
| 7_maintainability | H5 | warn,deterministic | SKIP | keine TASKS.md (nicht anwendbar) |
| 7_maintainability | H6 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I1 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I2 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 8_judgement | I3 | block,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 9_freigabe | J1 | block,deterministic | SKIP | keine Produktivfreigabe (docs/produktivfreigabe/FREIGABE.yaml) |
| 9_freigabe | J2 | block,deterministic | SKIP | keine Produktivfreigabe (docs/produktivfreigabe/FREIGABE.yaml) |
| 10_branche | K1 | block,deterministic,branch | SKIP | keine Branche aktiviert (--branch / .werkbank/branch.txt) |
| 10_branche | K2 | block,deterministic,branch | SKIP | keine Branche aktiviert |

## Funde (redigiert — keine Klartext-Secrets/PII)
- **H3** — WARN — keine README (README.md/README.rst)
    - `(root):0` [docs-missing] keine README gefunden

## Block-Regel
Mind. 1 Block-Gate rot ⇒ kein Push, kein Abhaken. E-Gate rot ⇒ STOPP + Mensch.
