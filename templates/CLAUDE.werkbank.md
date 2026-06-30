# Projekt-Leitfaden — BMAD · kiln · WERKBANK als eine Einheit

> Diese Datei macht die drei Schichten zu **einem** Arbeitsmodell. Claude Code liest sie automatisch.
> **Geltung: interner Einsatz, KEINE echten personenbezogenen Kundendaten** (siehe WERKBANK-Freigabe).

## Die drei Schichten — und wie sie zusammenspielen
| Schicht | Quelle | Rolle hier |
|---|---|---|
| **Methode** | **BMAD** (`_bmad/`, via `npx bmad-method`) | Analyst/PM/Architect/SM/Dev — Brief → PRD → Architektur → Stories |
| **Autonomie** | **kiln-Muster** (adaptiert) | `.werkbank/STATE.md` (crash-sicher), Ralph-Loop bis `<promise>GRUEN</promise>`, persistente Reviewer-Minds + frische Builder, 3 Review-Ebenen, Drift-Pausegate |
| **Governance** | **WERKBANK** (`gates/`) | deterministische Block-Gates (E1/E2/E3/E4/E5/D3) — **müssen grün sein vor Push** |

kiln ist ein **Muster**, kein installiertes Tool — es lebt in `.werkbank/STATE.md`, den `agents/`/`workflows/`-Definitionen und diesem Loop.

## Autonomer Durchlauf — ein Kommando (01→04)
```bash
pipeline/run_pipeline.sh --project . --brief "<was gebaut werden soll>" \
  --privacy-dir <artefakte> --privacy-required <liste> [--audit-log <f>] [--apply] [--gh-issues]
```
Fährt **01 Konzipieren (BMAD)** → **02 Bauen (Ralph-Loop)** → **03 Prüfen (alle Gates)** →
**04 Übergeben** autonom; Gates sind das Orakel zwischen den Phasen; rot → feedback (Issues/Backlog) + Halt.
Phasen-Kommandos `--konzipieren-cmd`/`--bauen-cmd` sind pluggbar (real `claude -p`, Test-Fakes). Exit 0/3/2.

## Der Arbeitsloop (BMAD → kiln → WERKBANK)
1. **Konzipieren (BMAD):** Story/PRD/Architektur über die BMAD-Rollen (`workflows/01-konzipieren.md`).
2. **Bauen (kiln/Ralph):** Test zuerst (RED → GREEN → REFACTOR). Pro Chunk **Paar-Review: Reviewer-Modell ≠ Implementer**. `STATE.md` nach jeder Runde. Drift-Pausegate: sinkt Test/Gate ggü. Vorrunde → anhalten.
3. **Prüfen (WERKBANK):** `python3 gates/runner.py --target . --report GATE-REPORT.md`. Rote Block-Gates ⇒ kein Fortschritt.
4. **Übergeben:** CHANGELOG + `.werkbank/BENCHMARK.md` (Vorher/Nachher), Branch pushen, **PR** — **kein Selbst-Merge**, Mensch gibt frei.

## Harte Regeln (nicht verhandelbar)
- Nie direkt auf `main`/Prod — Branch `werkbank-build`. Alles reversibel.
- **Block-Gate rot ⇒ kein Push.** E-Gate (E*) rot ⇒ STOPP, Mensch fragen.
- **Keine Secrets/PII committen** — nur Env-Referenzen. Verstöße in Tests zur Laufzeit synthetisieren.
- Verification-first: kein Lauf ohne Orakel (Akzeptanz + Tests + Gates). Assertions nie aufweichen.
- Selbstverbesserung nur kontrolliert (kleinste Änderung, größter Hebel, messen, Regression prüfen, sonst zurückrollen).

## Modell-Tier-Routing (Kosten) — VERBINDLICH beim Spawnen von Subagenten
Subagenten laufen NICHT automatisch auf dem günstigsten Modell — der Orchestrator muss das Tier
**explizit setzen**. Quelle der Wahrheit ist der Tier-Router (`orchestrator/werkbank.tiers.json`).
```bash
python3 orchestrator/tier_router.py <label>     # z. B. review -> opus, doku -> haiku, impl -> sonnet
python3 orchestrator/tier_router.py --table     # ganze Policy
```
Regel: Beim Agent-Spawn `model=` automatisch bestimmen — **Auto-Labeler** statt manuell:
```bash
python3 orchestrator/autolabel.py "<aufgabentext>"   # -> "label  model" (z. B. review  opus)
python3 orchestrator/autolabel.py --lint agents       # flaggt Agent-Defs ohne model:-Frontmatter
```
`route(task)` mappt Text → Label → Tier-Modell. Labels & Tiers:
| Label | Tier/Modell |
|---|---|
| doku, summary, format, lint | **haiku** (günstig) |
| impl, test, refactor, build | **sonnet** (mittel) |
| plan, architecture, review, security, privacy, judge | **opus** (teuer) |

- **Paar-Review immer mit anderem Modell als der Implementer** (Cross-Model) — Review-Tier = opus.
- `confirm_tier_from: opus`: vor teuren (opus-)Spawns bestätigen lassen, wenn Budget knapp.
- Belegt ist das Routing erst, wenn die **Kosten/Usage je Modell** (z. B. `/cost`) zur Zuweisung passen;
  Selbstauskunft eines Subagenten über sein Modell ist nur indikativ.

## Persistente Minds + frische Worker (kiln)
- **Builder/Impl = frisch** je Chunk (sauberer Kontext, kein Mind).
- **Reviewer/Architekt/Judge = persistent**: vor dem Spawn die Historie injizieren, danach Erkenntnis anhängen.
```bash
python3 orchestrator/mind.py context reviewer            # Historie -> in den Reviewer-Prompt
python3 orchestrator/mind.py append  reviewer "Befund X"  # nach dem Review festhalten
```
`is_persistent(role)` entscheidet (reviewer/architect/judge/privacy-analyst/tribunal/qa = persistent).
Mind-State liegt lokal in `.werkbank/minds/` (gitignored).

## Die Gates (kurz)
- **E1** EU-Routing (kein Non-EU-Endpunkt/Region in Code/Config) · **E2** keine Klartext-PII in Logs/Prompts/Outputs · **D3** keine Secrets · **E3** Mandantentrennung (Audit-Log) · **E4** Audit-Log-Schema · **E5** DSGVO-Artefakt-Vollständigkeit (`--privacy-dir`).
- Nicht-implementierte Gates erscheinen als **SKIP** (ehrlich, nicht „grün"). E1 ist statisch (kein Laufzeit-Zwang); PII-Erkennung ist heuristisch — siehe WERKBANK-Grenzen.

## Ralph-Loop (Autonomie-Motor)
Vollautonom mit frischem Kontext je Runde, bis Gates grün **und** promise erscheint:
```bash
ralph/ralph-loop.sh --build-cmd 'claude -p "<Story abarbeiten; bei fertig <promise>GRUEN</promise> ausgeben>"' \
  --target . --max-iterations 15
```
Stoppt erst bei **GRUEN + `<promise>GRUEN</promise>`**; hält an bei `--max-iterations` oder
**Drift** (mehr rote Gates als in der Vorrunde). In-Session-Variante: `ralph/stop_hook.py` (opt-in).

## Selbstheilende Rückkopplung (feedback)
Rote Gates werden automatisch zu Arbeit: `feedback/feedback.py` parst `GATE-REPORT.md`, hängt
**Gate-ID-deduplizierte** `[ ]`-Aufgaben in `BACKLOG.md` (und optional GitHub-Issues, `--gh-issues`),
und hakt bei PASS wieder ab/schließt (`--close-resolved`). **Egress-Redaction** maskiert Secrets/PII/Pfade
vor jedem Ausgang. Default Dry-Run. So schließt sich der Kreis: rot → Backlog/Issue → Ralph-Loop → grün → erledigt.

## Befehle
```bash
python3 gates/runner.py --target . --report GATE-REPORT.md   # Gate-Lauf
python3 gates/runner.py --target . --ci                       # CI (Exit 1 bei ROT)
ralph/ralph-loop.sh --build-cmd '<worker>' --max-iterations 15  # Ralph-Loop
python3 orchestrator/tier_router.py --table                   # Tier-Routing
npx bmad-method status                                        # BMAD-Status
```

## Erste Aktion für den Agenten
Lies `.werkbank/STATE.md`, führe den Gate-Lauf aus, melde rote Gates + Plan in ≤ 8 Zeilen, **warte auf „GO"**.
