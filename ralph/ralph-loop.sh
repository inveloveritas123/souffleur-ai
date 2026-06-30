#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ralph-loop.sh — Ralph-Loop-Motor (Fresh-Context-Variante, Blueprint §2).
#
# Iteriert: Worker laufen lassen -> Gates prüfen -> completion-promise prüfen
# -> Entscheidung (ralph_decide.py): fertig / weiter / anhalten (Drift, max-iter).
#
#   --build-cmd "<cmd>"   der Worker je Runde (z. B. 'claude -p "<task>"' mit frischem Kontext).
#                         Muss bei „fertig" den promise-Marker ausgeben.
#   --target <dir>        Projekt für den Gate-Lauf (default .)
#   --max-iterations <n>  Sicherheitsnetz (default 15)
#   --promise <marker>    completion-promise (default "<promise>GRUEN</promise>")
#   --report <datei>      GATE-REPORT (default GATE-REPORT.md)
#
# Exit: 0 = fertig (GRUEN+promise) · 3 = angehalten (Drift/max-iter) · 2 = Fehler.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET="."; MAXIT=15; PROMISE="<promise>GRUEN</promise>"; REPORT="GATE-REPORT.md"; BUILD_CMD=""
PROFILE="${WERKBANK_PROFILE:-}"; PFLICHT="${WERKBANK_PFLICHTENHEFT:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --build-cmd) BUILD_CMD="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --max-iterations) MAXIT="$2"; shift 2 ;;
    --promise) PROMISE="$2"; shift 2 ;;
    --report) REPORT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --pflichtenheft) PFLICHT="$2"; shift 2 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
[ -n "$BUILD_CMD" ] || { echo "✗ --build-cmd fehlt" >&2; exit 2; }

prev_red=-1; iter=0
echo "▶ Ralph-Loop: target=$TARGET max-iterations=$MAXIT promise=\"$PROMISE\""
while :; do
  iter=$((iter+1))
  echo "── Runde $iter ─────────────────────────────"

  # 0) Budget/Kill-Switch — stoppt den autonomen Lauf hart, bevor weiter gearbeitet wird.
  budget_state="$TARGET/.werkbank/budget.json"
  if [ -f "$budget_state" ]; then
    if ! python3 "$SELF/../orchestrator/budget.py" check "$budget_state" >/dev/null 2>&1; then
      echo "⛔ Budget/Kill-Switch erreicht — Lauf angehalten."; exit 3
    fi
  fi

  # 1) Worker (frischer Kontext je Aufruf, wenn build-cmd = 'claude -p ...')
  build_out="$( ( cd "$TARGET" && eval "$BUILD_CMD" ) 2>&1)"; echo "$build_out" | tail -3
  if printf '%s' "$build_out" | grep -qF "$PROMISE"; then promise=1; else promise=0; fi

  # 2) Gates
  gate_args=(--target "$TARGET" --report "$REPORT" --ci)
  [ -n "$PROFILE" ] && gate_args+=(--profile "$PROFILE")
  [ -n "$PFLICHT" ] && gate_args+=(--pflichtenheft "$PFLICHT")
  if python3 "$SELF/../gates/runner.py" "${gate_args[@]}" >/dev/null 2>&1; then
    gates_ok=1; else gates_ok=0; fi
  cur_red="$(grep -m1 'Pflicht-Gates ohne PASS:' "$REPORT" 2>/dev/null | grep -oE '[0-9]+' | head -1)"; cur_red="${cur_red:-0}"

  # 3) Entscheidung (eine Quelle der Wahrheit)
  dec="$(python3 "$SELF/ralph_decide.py" "$gates_ok" "$promise" "$iter" "$MAXIT" "$prev_red" "$cur_red")"
  action="$(printf '%s' "$dec" | cut -f1)"; reason="$(printf '%s' "$dec" | cut -f2-)"
  echo "   gates_ok=$gates_ok promise=$promise rot=$cur_red -> $action ($reason)"

  case "$action" in
    stop)     echo "✅ $reason"; exit 0 ;;
    halt)     echo "⛔ $reason"; exit 3 ;;
    continue) prev_red="$cur_red" ;;
  esac
done
