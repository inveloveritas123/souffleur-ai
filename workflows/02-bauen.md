# Workflow 02 — Bauen (Ralph-Loop)

> Verification-first. Story → RED → GREEN → REFACTOR → Chunk-Review.
> `completion-promise = <promise>GRUEN</promise>`, `--max-iterations 15` als Sicherheitsnetz.

## Ablauf
1. Tests zuerst (RED). Implementierung bis grün (GREEN). Aufräumen (REFACTOR).
2. Pro Chunk Paar-Review: **Reviewer-Modell ≠ Implementer-Modell** (Cross-Model, Gate I1).
   Modellwahl über den Tier-Router: Implementer `model=$(tier_router.py impl)` (sonnet),
   Reviewer `model=$(tier_router.py review)` (opus). Doku-Tasks → haiku. So greift die Tier-Verteilung.
3. Frischer Worker pro Chunk (Kontext-Isolation); **persistente Reviewer/Architekt-Minds**:
   `orchestrator/mind.py context reviewer` vor dem Spawn injizieren, danach `mind.py append reviewer "<Befund>"`.
4. **Drift-Pausegate:** sinkt Test/Gate ggü. Vorrunde → anhalten, Ursache nennen, eskalieren.
5. `.werkbank/STATE.md` nach jeder Runde aktualisieren.

## Motor (verdrahtet)
```bash
ralph/ralph-loop.sh --build-cmd 'claude -p "<Story bauen; bei fertig <promise>GRUEN</promise>>"' \
  --target . --max-iterations 15
```
Stoppt erst bei **GRUEN + promise**; HALT bei max-iterations oder **Drift** (`ralph/ralph_decide.py`).
Modellwahl je Schritt über `orchestrator/tier_router.py` (impl→sonnet, review→opus, doku→haiku).

## Abbruch / Stopp
- max-iterations / Drift ⇒ Loop hält an, Lage melden, Mensch entscheidet.
- Block-Gate rot ⇒ kein Fortschritt.

## Übergabe an
`workflows/03-pruefen.md`
