# Workflow 03 — Prüfen

> `gates/runner` über alle Block-Gates (gestaffelt) + QA-Tribunal (Meilenstein, Cross-Model).
> Danach gegen Golden-Project-Soll messen und `.werkbank/BENCHMARK.md` schreiben (100-Punkte-Matrix).

## Ablauf
1. Deterministische Block-Gates zuerst (fail_fast). LLM-Gates nur auf grünem Rest.
2. `GATE-REPORT.md` schreiben (aus `templates/GATE-REPORT.md`).
3. Gegen `golden-projects/<n>/EXPECTED_OUTPUTS.md` + `SECURITY_SEEDS.md` messen (Catch-Rate = 100 %).
4. Score nach `SCORING-MATRIX.md`; Zeile in `.werkbank/BENCHMARK.md` (append, neuster oben).

## Done-Vorbedingung
Score ≥ 85, 0 rote Block-Gates, 0 Secrets, 0 kritische Security-/DSGVO-Funde, keine Regression.

## Lauf (verdrahtet)
```bash
python3 gates/runner.py --target . --report GATE-REPORT.md \
  --spec-file templates/SPEC.md \
  --privacy-dir <artefakte> --privacy-required <liste> \
  --audit-log <evidence/audit.log>     # E3/E4 falls Multi-Tenant
```
Implementiert: A1/A2/A3 · C1 · D3 · E1/E2/E3/E4/E5/E6/E7 · F1 · H4. Rest SKIP (ehrlich).

## QA-Tribunal (I2, Meilenstein — Cross-Model, LLM)
Nach grünen deterministischen Gates auf grünem Rest:
```bash
tribunal/tribunal.sh \
  --reviewer 'claude -p --model opus  "Review <ziel> adversarial; letzte Zeile VERDICT: pass|fail|uncertain"' \
  --reviewer 'claude -p --model sonnet "..."' \
  --reviewer 'claude -p --model haiku  "..."'
```
Anonymisierte Reconciliation (`tribunal/reconcile.py`): nur klare Pass-Mehrheit besteht. Exit 0/3.
LLM-Urteile sind nicht deterministisch (ehrlich); die Reconciliation ist es.

## Selbstheilende Rückkopplung (feedback)
Nach dem Gate-Lauf rote Befunde automatisch als Arbeit zurückspeisen (Egress-redigiert, Gate-ID-dedupliziert):
```bash
python3 feedback/feedback.py --report GATE-REPORT.md --backlog BACKLOG.md            # Dry-Run
python3 feedback/feedback.py --report GATE-REPORT.md --backlog BACKLOG.md \
        --apply --close-resolved [--gh-issues]   # Backlog/Issues anlegen + grüne abhaken/schließen
```
Damit schließt sich der Kreis: rote Gates → Backlog/Issue → Ralph-Loop arbeitet sie ab → grün → abgehakt/geschlossen.

## Übergabe an
`workflows/04-uebergeben.md`
