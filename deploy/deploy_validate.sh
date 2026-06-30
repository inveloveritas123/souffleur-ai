#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_validate.sh — I3 Deployment-Validierung gegen echte User-Flows (Argus-Stil).
#
# Je kritischem User-Flow ein Validator (idealerweise gegen die deployte App / E2E),
# der "VERDICT: pass|fail|uncertain" ausgibt. ALLE müssen pass sein (deploy_validate.py).
#
#   --flow "<name>=<cmd>"   wiederholbar. real z. B.:
#       'buchen=claude -p "Validiere Flow: Termin buchen gegen die App; letzte Zeile VERDICT: pass|fail"'
#
# Exit: 0 = deploy-ready (alle Flows pass) · 3 = block · 2 = Fehler.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FLOWS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --flow) FLOWS+=("$2"); shift 2 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
[ "${#FLOWS[@]}" -ge 1 ] || { echo "✗ mindestens ein --flow nötig" >&2; exit 2; }

verdicts=()
for spec in "${FLOWS[@]}"; do
  name="${spec%%=*}"; cmd="${spec#*=}"
  out="$(eval "$cmd" 2>&1)"
  v="$(printf '%s' "$out" | grep -oiE 'VERDICT:[[:space:]]*(pass|fail|uncertain)' | head -1 | grep -oiE '(pass|fail|uncertain)$' | tr 'A-Z' 'a-z')"
  v="${v:-uncertain}"
  echo "   Flow '$name' -> $v"
  verdicts+=("$v")
done

python3 "$SELF/deploy_validate.py" "${verdicts[@]}"
exit $?
