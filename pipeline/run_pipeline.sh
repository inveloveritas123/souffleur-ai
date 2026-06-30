#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_pipeline.sh — autonomer 01->04-Durchlauf (Fresh-Context, Blueprint §2/§5).
#
#   01 Konzipieren (BMAD)  -> SPEC.md ; A-Gates müssen grün
#   02 Bauen (Ralph-Loop)  -> bis alle Block-Gates grün UND <promise>GRUEN</promise>
#   03 Prüfen              -> voller Gate-Lauf (alle Kontexte)
#   04 Übergeben           -> Bündel/Report (mit --apply: Commit/PR)
# Gates sind das Orakel zwischen den Phasen; rot -> feedback (Issues/Backlog) + Halt.
#
# Phasen-Kommandos sind pluggbar (real: 'claude -p ...'; Test: Fakes):
#   --konzipieren-cmd "<cmd>"   muss <project>/SPEC.md erzeugen (Default: BMAD via claude -p)
#   --bauen-cmd "<cmd>"         Worker je Ralph-Runde (Default: claude -p, gibt promise aus)
#   --project <dir> --brief "<text>" --max-iterations N --apply --gh-issues
#   --privacy-dir <d> --privacy-required <liste> --audit-log <f>
# Exit: 0 = fertig (GRUEN) · 3 = angehalten (Gate rot / Ralph-Halt) · 2 = Fehler.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$SELF/.." && pwd)"

PROJECT="."; BRIEF=""; MAXIT=15; APPLY=0; GH=0
PRIV_DIR=""; PRIV_REQ=""; AUDIT=""
# PROFILE = Abnahme-Profil (Phase-3-Gate, voller Kontext). BUILD_PROFILE = Bau-Loop-Profil
# (Phase 2, Code-Qualitaet ohne Projekt-/Privacy-Kontext). Trennung: der Bau-Loop iteriert
# Code gruen, die volle DSGVO-/Spec-Pflicht prueft erst die Abnahme mit allen Artefakten.
PROFILE="${WERKBANK_PROFILE:-}"; PFLICHT="${WERKBANK_PFLICHTENHEFT:-}"
BUILD_PROFILE="${WERKBANK_BUILD_PROFILE:-basis}"
# QA-Hook: schreibt .werkbank/qa-evidence.json (BMADs QA-Agent -> Nachweis fuer A4/H6/I1/I2/I3).
QA="${WERKBANK_QA_CMD:-}"
# WICHTIG: die autonomen Worker brauchen --dangerously-skip-permissions, damit claude -p im
# Headless-Betrieb Dateien schreiben UND Werkzeuge (ruff/mypy/Tests) ausfuehren darf. Ohne das
# werden Bash-Befehle automatisch abgelehnt -> der Worker kann sich nicht selbst verifizieren und
# der Bau-Loop konvergiert NIE. Nur in isolierten/sandboxed Projektverzeichnissen verwenden.
KONZ='claude -p --dangerously-skip-permissions "Konzipiere mit BMAD (Skills bmad-prd, bmad-create-architecture, bmad-create-epics-and-stories) aus dem Brief und schreibe einen vollständigen, A-Gate-tauglichen templates/SPEC.md-konformen SPEC.md ins Projekt: 6 Pflichtfelder, >=2 testbare Akzeptanzkriterien, Handoff [x]."'
BAUEN='claude -p --dangerously-skip-permissions "Arbeite die oberste offene Story/Welle test-first (RED->GREEN->REFACTOR). SELBST-VERIFIKATION vor dem Fertigmelden: lies GATE-REPORT.md und BACKLOG.md und behebe die dort gelisteten roten Gate-Befunde gezielt (genannte Dateien/Fehler); fuehre dann selbst aus: ruff check ., mypy ., python3 -m unittest discover (oder pytest) und behebe ALLE Befunde, bis diese Tools sauber durchlaufen. Gib NUR DANN exakt <promise>GRUEN</promise> aus, wenn ruff+mypy+Tests lokal sauber sind; sonst arbeite weiter."'
while [ $# -gt 0 ]; do case "$1" in
  --project) PROJECT="$2"; shift 2;; --brief) BRIEF="$2"; shift 2;;
  --konzipieren-cmd) KONZ="$2"; shift 2;; --bauen-cmd) BAUEN="$2"; shift 2;;
  --max-iterations) MAXIT="$2"; shift 2;; --apply) APPLY=1; shift;; --gh-issues) GH=1; shift;;
  --privacy-dir) PRIV_DIR="$2"; shift 2;; --privacy-required) PRIV_REQ="$2"; shift 2;;
  --audit-log) AUDIT="$2"; shift 2;;
  --profile) PROFILE="$2"; shift 2;; --build-profile) BUILD_PROFILE="$2"; shift 2;; --pflichtenheft) PFLICHT="$2"; shift 2;;
  --qa-cmd) QA="$2"; shift 2;;
  *) echo "Unbekannt: $1" >&2; exit 2;; esac; done

REPORT="$PROJECT/GATE-REPORT.md"; mkdir -p "$PROJECT/.werkbank"
log(){ echo "$@"; printf '%s\n' "$@" >> "$PROJECT/.werkbank/STATE.md" 2>/dev/null || true; }
gate(){ # nie-leeres Array -> bash-3.2-sicher
  local args=(--target "$PROJECT" --report "$REPORT" --ci)
  [ -f "$PROJECT/SPEC.md" ] && args+=(--spec-file "$PROJECT/SPEC.md")
  [ -n "$PRIV_DIR" ] && args+=(--privacy-dir "$PRIV_DIR")
  [ -n "$PRIV_REQ" ] && args+=(--privacy-required "$PRIV_REQ")
  [ -n "$AUDIT" ] && args+=(--audit-log "$AUDIT")
  [ -n "$PROFILE" ] && args+=(--profile "$PROFILE")
  [ -n "$PFLICHT" ] && args+=(--pflichtenheft "$PFLICHT")
  python3 "$ROOT/gates/runner.py" "${args[@]}"; }
status(){ grep -E "\| $1 \|" "$REPORT" 2>/dev/null | grep -oE "PASS|FAIL|SKIP|WARN" | head -1; }
heal(){ local f="--apply"; [ "$GH" -eq 1 ] && f="$f --gh-issues"
  # In $PROJECT laufen: gh-Issues landen so im PROJEKT-Repo (nicht im cwd-Repo der Pipeline).
  ( cd "$PROJECT" && python3 "$ROOT/feedback/feedback.py" --report "$REPORT" \
      --backlog "$PROJECT/BACKLOG.md" $f --close-resolved ) || true; }

# 01 KONZIPIEREN (BMAD)
log "▶ 01 Konzipieren (BMAD)"
( cd "$PROJECT" && eval "$KONZ" ) >/dev/null 2>&1 || true
gate >/dev/null 2>&1 || true
for g in A1 A2 A3; do
  if [ "$(status "$g")" != "PASS" ]; then log "⛔ 01 Halt: Spec-Gate $g nicht grün ($(status "$g"))"; heal; exit 3; fi
done
log "   A1/A2/A3 grün."

# 02 BAUEN (Ralph-Loop)
log "▶ 02 Bauen (Ralph-Loop)"
ralph_args=(--target "$PROJECT" --build-cmd "$BAUEN" --max-iterations "$MAXIT" --report "$REPORT")
[ -n "$BUILD_PROFILE" ] && ralph_args+=(--profile "$BUILD_PROFILE")
[ -n "$PFLICHT" ] && ralph_args+=(--pflichtenheft "$PFLICHT")
if ! bash "$ROOT/ralph/ralph-loop.sh" "${ralph_args[@]}" >/dev/null 2>&1; then
  log "⛔ 02 Halt: Ralph-Loop nicht grün (Drift/max-iterations)"; heal; exit 3; fi
log "   Bau grün + promise."

# 02b QA (BMAD-QA-Agent -> Evidence fuer die LLM-Urteils-Gates A4/H6/I1/I2/I3)
if [ -n "$QA" ]; then
  log "▶ 02b QA (BMAD-Urteil -> .werkbank/qa-evidence.json)"
  ( cd "$PROJECT" && eval "$QA" ) >/dev/null 2>&1 || true
  [ -f "$PROJECT/.werkbank/qa-evidence.json" ] && log "   QA-Evidence geschrieben." \
    || log "   ! keine QA-Evidence — LLM-Gates bleiben UNGEDECKT (ehrlich)."
fi

# 03 PRÜFEN (voller Gate-Lauf)
log "▶ 03 Prüfen (alle Gates)"
if ! gate >/dev/null 2>&1; then
  log "⛔ 03 Halt: Block-Gates rot — Befunde -> Backlog/Issues"; heal; exit 3; fi
log "   Alle Block-Gates grün."

# 04 ÜBERGEBEN
log "▶ 04 Übergeben"
heal   # schließt ggf. zuvor offene Issues/Backlog (close-resolved)
if [ "$APPLY" -eq 1 ]; then
  ( cd "$PROJECT" && git add -A && git commit -q -m "WERKBANK-Pipeline: 01-04 grün" && \
    git push -q origin "$(git rev-parse --abbrev-ref HEAD)" 2>/dev/null ) && log "   committed/pushed." || log "   (Commit/Push übersprungen)"
else
  log "   Report-Bündel bereit (kein --apply): $REPORT"
fi
log "✅ Pipeline GRUEN (01-04)."; exit 0
