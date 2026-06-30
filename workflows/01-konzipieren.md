# Workflow 01 — Konzipieren (BMAD als Methode)

> Nutzt **BMAD** (installiert unter `_bmad/`, Skills in `.claude/skills/`) — WERKBANK baut die
> Methode nicht nach, sondern ruft sie. Ergebnis ist ein SPEC, der die **A-Gates** besteht.

## Ablauf (vom Agenten auszuführen)
1. **Brief → PRD:** BMAD-Skill `bmad-prd` aufrufen (Analyst/PM-Rolle). Eingabe: Projektangaben/Story.
2. **Architektur:** Skill `bmad-create-architecture` (Architect, Winston). Handoff PM→Architect dokumentieren.
3. **Stories:** Skill `bmad-create-epics-and-stories` (Scrum-Master) → umsetzbare Stories mit Akzeptanz.
   (Unsicher, welcher Skill? `bmad-help` aufrufen.)
4. **SPEC ableiten:** aus PRD/Architektur `templates/SPEC.md` befüllen — alle 6 Pflichtfelder
   (Ziel, Scope, Datenarten, Akzeptanzkriterien, Nicht-Ziele, Handoff), **keine Platzhalter**,
   Akzeptanzkriterien als testbare `- [ ]`-Liste, Handoff-Checkliste `- [x]`.

## Gate-Vorbedingung (vor dem Bau, hart)
```bash
python3 gates/runner.py --target . --spec-file templates/SPEC.md --report GATE-REPORT.md
```
**A1** (Pflichtfelder), **A2** (Akzeptanz testbar), **A3** (Handoff) müssen grün sein, sonst zurück zu BMAD.

## Übergabe an
`workflows/02-bauen.md` (Ralph-Loop).
