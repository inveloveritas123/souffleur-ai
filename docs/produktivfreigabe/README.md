# Produktivfreigabe — Dokumentenpaket

Vorbereitung der Reifegrad-Stufe **„echte Kundendaten"** (`BACKLOG.md` Reifegrad-Tor).
Die Golden-Project-Bedingung (≥ 5 grün) ist erfüllt (6/6); die folgenden Dokumente bereiten die
verbleibenden, **menschlich zu erteilenden** Freigaben vor:

- **GRENZEN-UND-HAFTUNG.md** — was WERKBANK leistet und NICHT garantiert (Scope, Disclaimer).
- **SECURITY-REVIEW.md** — Gate-Abdeckung, gefundene/gefixte Befunde, Restrisiken, Security-Freigabefeld.
- **DATENSCHUTZ-REVIEW.md** — DSGVO-Artikel-Abdeckung, Restlücken, DSB-Freigabefeld.

> Alle drei sind **Self-Assessments mit menschlichen Freigabefeldern** — keine Selbst-Zertifizierung.
> Kein Rechtsrat. Die finale Merge-/Produktivfreigabe trifft der Mensch (kein Selbst-Merge).

## Hart erzwungen: Gates J1/J2 + Profil `produktiv`

Die menschliche Abnahme ist **als Gate verdrahtet**, nicht nur als Doku:

- **`FREIGABE.template.yaml`** → kopieren nach **`FREIGABE.yaml`** und ausfüllen/signieren (Mensch).
- **Gate J1** (Security-Abnahme) und **Gate J2** (Datenschutz-/DSB-Abnahme) lesen diese Datei
  (`gates/checks/freigabe.py`): `freigegeben: true` mit `von` + `datum` ⇒ PASS; nicht erteilt
  oder unvollständig ⇒ FAIL; fehlt ⇒ SKIP (unter `produktiv` ⇒ UNGEDECKT ⇒ ROT).
- **Profil `produktiv`** (`gates/pflichtenheft.yaml`) = `produktion` **+ J1 + J2**. Es wird **nur
  GRÜN, wenn beide Abnahmen signiert vorliegen** — also nie ohne menschliche Unterschrift.

```bash
# Abnahme prüfen (höchste Latte, mit echtem Daten-/Privacy-Kontext):
python3 gates/runner.py --target . --report GATE-REPORT.md --profile produktiv \
  --privacy-dir artefakte --privacy-required "<...>" --audit-log evidence/audit.log --ci
```

**Kein Self-Sign:** Der Agent darf `FREIGABE.yaml` nicht selbst setzen — das ist eine menschliche
Handlung. So ist „darf mit echten Daten live" auditierbar an eine Unterschrift gebunden.
