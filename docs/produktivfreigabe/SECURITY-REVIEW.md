# WERKBANK — Security-Review-Report (Vorbereitung)

> Stand: 2026-06-08 · Umfang: T0–T8 (Gate-Tooling + 6 Golden Projects) · Branch `werkbank-build`.
> **Dies ist eine strukturierte Self-Assessment-Vorbereitung, keine externe Penetrationstest-Freigabe.**
> Die finale Security-Freigabe trifft ein menschlicher Prüfer (§7).

## 1 · Scope & Methodik
- Geprüft: `gates/` (Runner + Checks), die 6 Golden-Project-Apps, die Testsuite (84 Tests).
- Methodik: Verification-first (RED→GREEN), je Golden Project ein **unabhängiger Cross-Model-Paar-Review**
  (Reviewer ≠ Implementer) mit adversarialem Fokus; alle Verstöße zur Laufzeit synthetisiert (keine
  echten Secrets/PII im Repo); Repo-Self-Gate-Lauf nach jeder Aufgabe GRUEN.

## 2 · Abgedeckte Sicherheits-/DSGVO-Eigenschaften (mit Gate)
| Eigenschaft | Mechanismus | Gate |
|---|---|---|
| Keine Klartext-Secrets im Tree/Diff | Built-in-Regex + optional gitleaks, Redaction | **D3** |
| Keine Klartext-PII in Logs/Prompts/Outputs | Heuristik (Mail/Tel/IBAN/Karte/Name) | **E2** |
| Non-EU-Routing-Marker in Code/Config | statischer Marker-Scan | **E1** |
| Mandantentrennung (kein Cross-Tenant-Erfolg) | Audit-Log-Auswertung | **E3** |
| Audit-Log-Integrität (Schema/Typen) | Schema-Validierung gegen `AUDIT-LOG.schema.json` | **E4** |
| DSGVO-Artefakt-Vollständigkeit | Pflichtfeld-/Platzhalter-/EU-Prüfung | **E5** |
| Fail-closed Zugriffskontrolle (DSAR) | Token-Hash-Vergleich, AccessDenied-Default | GP02-Tests |
| Anti-Halluzination / Quellenzwang | Token-Anteil-Schwelle, wörtliche Antworten | GP06-Tests |

## 3 · NICHT abgedeckt (ehrliche Lücken — SKIP im GATE-REPORT)
- **Statische Sicherheit:** D1 (SAST), D2 (SCA/CVE-Scan), D4 (Lizenz) — nicht implementiert.
- **Funktional/Build:** A1–A3 (Spec), B1–B3 (Lint/Typecheck/Build), C1–C4 (Unit/Coverage/Integration/E2E) — nicht als Gate.
- **DSGVO:** E6 (DPIA-Erzwingung), E7/E8 (Drittland/Datenminimierung-LLM) — nicht implementiert.
- **Modell-Integrität:** F1 (Pinning), F2 (Eval-on-Bump) — nicht implementiert.
- **Urteils-Gates:** I1–I3 (LLM-Vier-Augen/QA-Tribunal/Deployment-Validierung) — nur als Bau-Review, nicht verdrahtet.
- **Laufzeit:** E1 ist statisch (kein Routing-Proxy); Audit-Log ist append-only-Datei (nicht WORM/manipulationssicher);
  keine Verschlüsselung at-rest; keine echte AuthN/AuthZ-Infrastruktur; CHANGELOG-Gate (H4) nicht erzwungen.

## 4 · Im Review gefundene & behobene Befunde (Beleg für Wirksamkeit des Prozesses)
| GP | Schweregrad | Befund | Fix |
|---|---|---|---|
| T1 | mittel | E1-Marker zu eng (Azure-US, `us.anthropic.*` übersehen) | Marker erweitert |
| GP02 | hoch | Autorisierung warf `KeyError` statt `AccessDenied` | fail-closed |
| GP02 | hoch | Retention-Job crashte (naive/aware datetime) → PII würde nie gelöscht | UTC-Normalisierung |
| GP03 | hoch | E3-Regex-Evasion (verkürzte Ressource / `*`) | Regex + Exemption gehärtet |
| GP03 | mittel | E4 ohne Typprüfung (`pii_present:0` passierte) | strikte Typprüfung |
| GP04 | kritisch | Redactor/E2 übersahen `+49 (0)…`, Namen ohne Anrede, Auslands-IBAN | Redactor+E2 gehärtet |
| GP05 | hoch | Linter übersah kahle Meldeaussagen („nicht meldepflichtig") | hedge-bewusst |
| GP06 | kritisch | PII-Filter übersah Namen ohne Anrede; Quelle nicht redigiert; 1-Token-Halluzination | alle drei gefixt |

> Jeder Befund wurde mit einem RED-Test fixiert, gefixt (GREEN) und gegen alle bisherigen Golden
> Projects regressionsgeprüft. Details: `.werkbank/BENCHMARK.md`.

## 5 · Restrisiken (für die menschliche Bewertung)
- PII-/Secret-Erkennung ist heuristisch → Restrisiko nicht erkannter Sonderformate.
- Keine Laufzeit-Garantie für EU-Routing und keine Manipulationssicherheit des Audit-Logs.
- Golden-Project-Apps sind nicht produktionsgehärtet (s. `GRENZEN-UND-HAFTUNG.md`).

## 6 · Empfehlungen vor Produktivbetrieb mit echten Daten
1. D1/D2 (SAST/SCA) als Block-Gates ergänzen. 2. EU-Routing per Proxy erzwingen (E1 zur Laufzeit).
3. Audit-Log manipulationssicher (Append-Only-Store/Signatur). 4. Verschlüsselung at-rest + Secrets-Manager.
5. I1–I3 (LLM-Urteils-Gates) verdrahten. 6. PII-Korpus erweitern (mehr Sprachen/Formate).

## 7 · Freigabe (menschlich)
- Security-Verantwortlicher: **Robert Hargesheimer** (robert@totokaa.de)  Datum: **2026-06-08**
- Restrisiken zur Kenntnis genommen und akzeptiert: **☑ — für internen Einsatz OHNE echte Kundendaten.**
- Auflagen vor Produktivbetrieb mit echten Kundendaten: **D1/D2 (SAST/SCA) als Block-Gates,
  EU-Routing zur Laufzeit erzwingen (Proxy), manipulationssicheres Audit-Log (WORM/Signatur),
  Verschlüsselung at-rest + Secrets-Manager — vor Einsatz mit echten Kundendaten umzusetzen.**
