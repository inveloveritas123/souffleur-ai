#!/usr/bin/env bash
# Kanonischer WERKBANK-Gate-Lauf für Souffleur AI (Zielprofil: pii).
# --exclude: Build-Artefakt-Verzeichnisse (nicht im Repo, aber lokal auf Platte) vom Scan ausnehmen.
cd "$(dirname "$0")/.."
REQ="DATA-FLOW.md,PROCESSING-REGISTER.md,LAWFUL-BASIS.md,DPIA-SCREENING.md,DPIA.md,PROCESSORS-SUBPROCESSORS.md,THIRD-COUNTRY-TRANSFERS.md,RETENTION-DELETION.md,TOMs.md,DSAR-RIGHTS.md,BREACH-RUNBOOK.md"
exec python3 gates/runner.py --target . --report GATE-REPORT.md --profile "${1:-pii}" \
  --spec-file SPEC.md --privacy-dir privacy --privacy-required "$REQ" \
  --audit-log tests/fixtures/audit-log.sample.jsonl --audit-schema templates/AUDIT-LOG.schema.json \
  --exclude "target,dist,.vite,gen,playwright-report,test-results,build,.pytest_cache,htmlcov" "${@:2}"
