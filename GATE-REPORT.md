# GATE-REPORT — target=`.` — 2026-06-30T23:14:15Z

## Zusammenfassung
- **Ergebnis:** ROT
- **Profil (Pflichtenheft):** `pii` — Verarbeitet personenbezogene Daten (DSGVO) — EU-Routing, PII-frei, Audit-Log, Artefakte, DPIA
- **Pflicht-Gates bestanden:** 4/17
- **Pflicht-Gates VERLETZT (FAIL):** 1
- **Pflicht-Gates UNGEDECKT (nicht geprueft):** 12
- **Pflicht-Gates ohne PASS:** 13
- **Optionale Befunde (warn):** 0

> **Hartes Gruen:** GRUEN gilt NUR, wenn alle 17 Pflicht-Gates aktiv bestanden sind. SKIP eines Pflicht-Gates (Tool fehlt / kein Check / kein Kontext) ⇒ UNGEDECKT ⇒ ROT.

## Warum ROT — Pflicht-Gates ohne PASS
- **B2 VERLETZT** — mypy meldet Befunde: There are no .py[i] files in directory '.'
- **B3 UNGEDECKT** (nicht gelaufen) — 
- **D3 UNGEDECKT** (nicht gelaufen) — 
- **F1 UNGEDECKT** (nicht gelaufen) — 
- **H4 UNGEDECKT** (nicht gelaufen) — 
- **C1 UNGEDECKT** (nicht gelaufen) — 
- **C2 UNGEDECKT** (nicht gelaufen) — 
- **D1 UNGEDECKT** (nicht gelaufen) — 
- **E1 UNGEDECKT** (nicht gelaufen) — 
- **E2 UNGEDECKT** (nicht gelaufen) — 
- **E4 UNGEDECKT** (nicht gelaufen) — 
- **E5 UNGEDECKT** (nicht gelaufen) — 
- **E6 UNGEDECKT** (nicht gelaufen) — 

## Detail je Stufe (Flags ★pflicht = Pflicht-Gate dieses Profils)
| Stufe | Gate | Flags | Ergebnis | Notiz |
|---|---|---|---|---|
| 1_spec | A1 | block,deterministic,★pflicht | PASS | alle 6 Spec-Pflichtfelder gefüllt |
| 1_spec | A2 | block,deterministic,★pflicht | PASS | 10 testbare Akzeptanzkriterien |
| 1_spec | A3 | block,deterministic,★pflicht | PASS | Handoff PM→Architect erfüllt |
| 1_spec | A4 | warn,llm | SKIP | kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json) |
| 2_static | B1 | block,deterministic,★pflicht | PASS | ruff sauber |
| 2_static | B2 | block,deterministic,★pflicht | FAIL | mypy meldet Befunde: There are no .py[i] files in directory '.' |
| 2_static | — | — | ABBRUCH | Stufe nach Block-FAIL abgebrochen (fail_fast) |

## Block-Regel
Mind. 1 Block-Gate rot ⇒ kein Push, kein Abhaken. E-Gate rot ⇒ STOPP + Mensch.
