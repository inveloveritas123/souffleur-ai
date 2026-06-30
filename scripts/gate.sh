#!/usr/bin/env bash
# Kanonischer WERKBANK-Gate-Lauf für Souffleur AI (Zielprofil: pii).
cd "$(dirname "$0")/.."
REQ="DATA-FLOW.md,PROCESSING-REGISTER.md,LAWFUL-BASIS.md,DPIA-SCREENING.md,DPIA.md,PROCESSORS-SUBPROCESSORS.md,THIRD-COUNTRY-TRANSFERS.md,RETENTION-DELETION.md,TOMs.md,DSAR-RIGHTS.md,BREACH-RUNBOOK.md"
exec python3 gates/runner.py --target . --report GATE-REPORT.md --profile "${1:-pii}" \
  --spec-file SPEC.md --privacy-dir privacy --privacy-required "$REQ" \
  --audit-schema templates/AUDIT-LOG.schema.json "${@:2}"
