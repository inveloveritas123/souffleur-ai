# TASKS — <Projektname>

> Aus Stories abgeleitet. **Self-contained Wellen** (Doktrin: docs/DOKTRIN-Self-Contained-Wellen.md):
> Jede OFFENE Welle traegt inline alles, was ein frisch gestarteter Worker (Ralph-Loop) oder ein
> Resume nach Kompaktierung braucht — ohne nachzulesen. Gate H5 prueft die Vollstaendigkeit.
> Test zuerst (RED) → GREEN → REFACTOR. Erledigte Welle mit `[x]` markieren.

## Wellen

### Welle 1 — <kurzer Titel>
- Dateien:   <exakte Pfade, die angefasst werden duerfen — nur diese>
- Verbote:   <was NICHT angefasst werden darf (z. B. gates/*, Schema, Public-API)>
- Smoke:     <der EXAKTE Verifikationsbefehl, z. B. `python3 -m pytest tests/test_x.py -q`>
- Akzeptanz: <das Orakel — wann ist die Welle fertig, beobachtbar formuliert>
- Entscheide: <optional: die 1-3 Entscheidungen aus frueheren Wellen, die diese Welle binden>

### Welle 2 — <kurzer Titel>   [x]
- Dateien:   ...
- Verbote:   ...
- Smoke:     ...
- Akzeptanz: ...

## Definition of Done (pro Welle)
- [ ] Test gruen (Smoke) · [ ] Chunk-Review (Cross-Model) · [ ] keine Drift ggue. Vorrunde
- [ ] Welle war self-contained (H5 gruen) — kein Nachlesen noetig
