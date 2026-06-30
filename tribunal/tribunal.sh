#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tribunal.sh — I2 QA-Tribunal (Fresh-Context-Fan-out, Cross-Model).
#
# Ruft mehrere Reviewer (idealerweise verschiedene Modelle) auf denselben Gegenstand,
# sammelt je ein "VERDICT: pass|fail|uncertain" und entscheidet anonymisiert via reconcile.py.
#
#   --reviewer "<cmd>"   wiederholbar; jeder Reviewer-Cmd MUSS eine Zeile "VERDICT: x" ausgeben.
#                        real z. B.: 'claude -p --model opus  "Review <ziel>; letzte Zeile VERDICT: pass|fail"'
#                                    'claude -p --model sonnet "..."'
#
# Exit: 0 = bestanden (klare Pass-Mehrheit) · 3 = block · 2 = Fehler.
# Hinweis: Die Urteile selbst sind LLM-generiert -> nicht deterministisch; die Reconciliation ist es.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REVIEWERS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --reviewer) REVIEWERS+=("$2"); shift 2 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
[ "${#REVIEWERS[@]}" -ge 1 ] || { echo "✗ mindestens ein --reviewer nötig" >&2; exit 2; }

verdicts=()
i=0
for cmd in "${REVIEWERS[@]}"; do
  i=$((i+1))
  out="$(eval "$cmd" 2>&1)"
  v="$(printf '%s' "$out" | grep -oiE 'VERDICT:[[:space:]]*(pass|fail|uncertain)' | head -1 | grep -oiE '(pass|fail|uncertain)$' | tr 'A-Z' 'a-z')"
  v="${v:-uncertain}"
  echo "   Reviewer $i -> $v"
  verdicts+=("$v")
done

python3 "$SELF/reconcile.py" "${verdicts[@]}"
exit $?
