# WERKBANK — Datenschutz-Review-Report (Vorbereitung für DSB)

> Stand: 2026-06-08 · Umfang: T0–T8 · Branch `werkbank-build`.
> **Kein Rechtsrat.** Strukturiertes Self-Assessment zur Vorbereitung der DSB-Prüfung; die
> datenschutzrechtliche Freigabe trifft der/die Datenschutzbeauftragte (§5).

## 1 · Artikel-Abdeckung (Soll-Ist)
| DSGVO | Anforderung | In WERKBANK adressiert durch | Status |
|---|---|---|---|
| Art. 5/25 | Datenminimierung, Privacy by Design | PII-Minimierung in Logs/Prompts (E2); Redaction (GP04); PII-Filter (GP06) | teilweise |
| Art. 6 | Rechtsgrundlage | Vorlage `LAWFUL-BASIS.md`, GP01 ausgefüllt | Vorlage + Beispiel |
| Art. 12–22 | Betroffenenrechte | GP02 (Auskunft/Export/Löschung), Vorlage `DSAR-RIGHTS.md` | implementiert (Demo) |
| Art. 17 | Löschung | GP02 (Datensatz), GP06 (Index-Löschung), Retention-Jobs | implementiert (Demo) |
| Art. 25 | Mandantentrennung / Zugriffskontrolle | GP03 (tenant aus Principal), E3 | implementiert (Demo) |
| Art. 28 | Auftragsverarbeitung | Vorlage `PROCESSORS-SUBPROCESSORS.md`, GP01 | Vorlage + Beispiel |
| Art. 30 | Verzeichnis Verarbeitungstätigkeiten | Vorlage `PROCESSING-REGISTER.md`, GP01 | Vorlage + Beispiel |
| Art. 32 | TOMs | Vorlage `TOMs.md`, GP01/GP03 | Vorlage + Beispiel |
| Art. 33/34 | Meldepflicht bei Datenpanne | GP05 (72h-Frist, begründete Einschätzung, Linter) | implementiert (Demo) |
| Art. 35 | DSFA / Screening | Vorlage `DPIA-SCREENING.md`, GP01 | Vorlage; **E6-Erzwingung fehlt** |
| Kap. V | Drittlandtransfer | Vorlage `THIRD-COUNTRY-TRANSFERS.md`; EU-Routing-Marker (E1) | Vorlage; **E7 fehlt** |

## 2 · Was die Gates datenschutzseitig prüfen
- **E1** flaggt Non-EU-Marker in Code/Config (statisch; **kein** Laufzeit-Routing-Zwang).
- **E2** verhindert Klartext-PII in Logs/Prompts/Outputs (heuristisch, hohe Präzision).
- **E5** erzwingt Vorhandensein + Befüllung + EU-Bezug der Soll-Artefakte (keine Platzhalter).
- **E3/E4** belegen Mandantentrennung und Nachvollziehbarkeit (Audit-Log).

## 3 · Restlücken (für die DSB-Bewertung)
- **E6 (DSFA-Erzwingung) und E7 (Drittland) nicht implementiert** — Screening/Transfer nur als
  Vorlage; die Erzwingung bei hohem Risiko ist organisatorisch sicherzustellen.
- **EU-Routing nicht zur Laufzeit erzwungen** (s. `GRENZEN-UND-HAFTUNG.md` §2).
- **PII-Erkennung heuristisch** → kein Garantieanspruch auf Vollständigkeit (freie Namen, PDF/OCR).
- **Verschlüsselung at-rest / Backups / Restore-Tests** sind Deployment-/Betriebsmaßnahmen, nicht im Code.
- **Artefakte sind Vorlagen + Beispiele**, keine ausgefüllten Verzeichnisse für ein reales Produktivsystem.

## 4 · Belege
- 6 Golden Projects grün (E-Gates PASS), 84 Tests grün, Repo-Self-Lauf GRUEN.
- DSGVO-Artefakte je GP unter `golden-projects/*/artefakte/`; Gate-Ergebnisse in `golden-projects/*/GATE-REPORT.md`.
- Anti-Overclaim: Restrisiken (z. B. Klartext-PII at-rest, Selbsteinschätzung der TOMs) sind in den
  Artefakten ausdrücklich vermerkt; keine erfundenen Rechtsaussagen (GP05-Linter).

## 5 · Freigabe (DSB)
- DSB / Datenschutz-Kontakt: **Robert Hargesheimer** (robert@totokaa.de)  Datum: **2026-06-08**
- Bewertung: ☐ freigegeben  **☑ freigegeben mit Auflagen**  ☐ nicht freigegeben
- **Geltungsbereich der Freigabe: interner Einsatz OHNE echte personenbezogene Kundendaten.**
- Auflagen / offene Punkte: **E6 (DSFA-Erzwingung) und E7 (Drittland) sind vor Einsatz mit echten
  Kundendaten als Gates zu implementieren; die heuristische, nicht erschöpfende PII-Erkennung ist
  organisatorisch abzusichern.** E6/E7 bis dahin als Vorlage akzeptiert.
- Hinweis: Diese Vorbereitung ersetzt nicht die eigenständige rechtliche Würdigung durch DSB/Anwalt.
