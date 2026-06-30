# WERKBANK — Grenzen & Haftung (Scope-/Disclaimer-Dokument)

> Stand: 2026-06-08 · Branch `werkbank-build` · gilt für den in diesem Repo gebauten Stand (T0–T8).
> **Kein Rechtsrat.** Dieses Dokument beschreibt ehrlich, was WERKBANK leistet und was **nicht**.

## 1 · Was WERKBANK ist
WERKBANK ist die **Governance-Schicht** über BMAD (Methode) und einem Ralph-/Verification-first-Muster
(Autonomie). Es liefert:
- einen **deterministischen Gate-Runner** (`gates/runner.py`) mit gestaffelter, fail-fast-Ausführung;
- sechs implementierte deterministische Checks: **E1** (EU-Routing-Marker), **E2** (PII in
  Logs/Prompts/Outputs), **D3** (Secret-Scan), **E3** (Mandantentrennung via Audit-Log),
  **E4** (Audit-Log-Schema), **E5** (DSGVO-Artefakt-Vollständigkeit);
- sechs **Golden Projects** als standardisierte Prüfprojekte (Scores 97–99);
- befüllbare **DSGVO-Artefakt-Vorlagen** und einen Benchmark-/State-Mechanismus.

## 2 · Was WERKBANK ausdrücklich NICHT ist / NICHT garantiert
- **Keine Rechtsberatung.** Meldeentscheidungen, DSFA-Notwendigkeit, Rechtsgrundlagen u. Ä. sind
  strukturierte **Einschätzungen**, kein Ersatz für DSB/Anwalt.
- **Keine Garantie der DSGVO-Konformität.** Grüne Gates bedeuten „die geprüften Kriterien sind erfüllt",
  nicht „rechtssicher konform". Viele Pflichten sind organisatorisch und nicht automatisch prüfbar.
- **Kein Laufzeit-Enforcement von EU-Routing.** E1 ist ein **statischer Scan** auf Non-EU-Marker in
  Code/Config — er garantiert nicht, dass jeder LLM-Call zur Laufzeit über einen EU-Endpunkt lief.
  Ein echter EU-Routing-Zwang erfordert einen Proxy/Gateway (nicht Teil dieses Stands).
- **PII-Erkennung ist heuristisch.** E2/Redactor fangen E-Mail/Telefon/IBAN/Kreditkarte und
  **kontextverankerte** Namen mit hoher Präzision, aber **nicht erschöpfend** (besonders freie
  Namen, seltene Formate, OCR-Text, Bilder). Keine Erkennung in Binärdateien/PDF-Inhalten.
- **Die Golden-Project-Apps sind Referenz-/Demo-Implementierungen** (stdlib), **keine** gehärteten
  Produktionsdienste: keine echte AuthN/AuthZ-Infrastruktur, keine Verschlüsselung at-rest, kein
  manipulationssicheres Audit-Log, keine Lasthärtung, keine Secrets-Verwaltung.
- **Viele Gates sind noch nicht implementiert** (Stufen A/B/C, D1/D2, E6/E7/E8, F, G, H, I) — siehe
  `SECURITY-REVIEW.md` §3. Ihr SKIP-Status wird im GATE-REPORT ehrlich ausgewiesen, ist aber **kein**
  Beleg für Erfüllung.
- **Die LLM-Urteils-Gates (I1–I3) fehlen.** Die „Vier-Augen"-Prüfung erfolgte hier durch
  Cross-Model-Paar-Reviews während des Baus, ist aber **nicht** als laufendes Gate verdrahtet.

## 3 · Voraussetzungen für den produktiven Einsatz mit echten personenbezogenen Daten
Aus `BACKLOG.md` (Reifegrad-Tor) — **alle** Punkte nötig, nicht nur die Golden Projects:
1. ≥ 5 Golden Projects grün — **erfüllt (6/6)**.
2. Security-Review — Vorbereitung: `SECURITY-REVIEW.md`; **menschliche Freigabe ausstehend**.
3. Datenschutz-Review (DSB) — Vorbereitung: `DATENSCHUTZ-REVIEW.md`; **DSB-Freigabe ausstehend**.
4. Menschliche Merge-Freigabe des PR — **ausstehend** (kein Selbst-Merge).
5. Diese Grenzen-/Haftungsdoku — **dieses Dokument**.

## 4 · Nutzungsempfehlung nach Reifegrad
- **Interne Spielprojekte:** ab 1 GP grün — freigegeben.
- **Interne Projekte ohne echte Kundendaten:** ab 3 GP grün — freigegeben.
- **Echte Kundendaten mit Personenbezug:** erst nach **vollständigem** §3 (inkl. menschlicher Freigaben).

## 5 · Haftung
Dieses Repository ist Werkzeug und Vorlage. Die Verantwortung für die DSGVO-Konformität, die
Richtigkeit der Meldeentscheidungen und die Sicherheit der produktiven Systeme verbleibt beim
**Verantwortlichen** (Art. 4 Nr. 7 DSGVO) und wird durch WERKBANK weder übernommen noch ersetzt.
Lizenz: siehe `LICENSE`.

---
**Freigabe (menschlich):**
- Verantwortlicher / GF: **Robert Hargesheimer** (robert@totokaa.de)  Datum: **2026-06-08**
- Zur Kenntnis genommen, Grenzen akzeptiert: **☑**
- **Freigegebener Einsatzzweck: intern, OHNE echte personenbezogene Kundendaten.**
  Einsatz mit echten Kundendaten erst nach Umsetzung der Auflagen (s. SECURITY-/DATENSCHUTZ-REVIEW).
