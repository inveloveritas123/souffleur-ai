# GATE-REPORT — <Projekt> — <Lauf/Datum>

> Vom `gates/runner` geschrieben. Gestaffelt; Stufe bricht bei erstem block-FAIL ab.

## Zusammenfassung
- **Ergebnis:** <GRUEN | ROT>
- **Block-Gates rot:** <Anzahl / Liste>
- **Warn-Gates:** <Anzahl>

## Detail je Stufe
| Stufe | Gate | Flags | Ergebnis | Notiz |
|---|---|---|---|---|
| 1_spec | A1 | block,deterministic | <PASS/FAIL> | |
| ... | ... | ... | ... | |

## Block-Regel
Mind. 1 Block-Gate rot ⇒ kein Push, kein Abhaken. E-Gate rot ⇒ STOPP + Mensch.
