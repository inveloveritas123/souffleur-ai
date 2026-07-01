# DPIA — Souffleur AI (Datenschutz-Folgenabschätzung, Art. 35 DSGVO)

## 1. Beschreibung der Verarbeitung

Souffleur AI erfasst Audio von 1:1-Coaching-Gesprächen, transkribiert und diarisiert es über Mistral Voxtral in Paris (EU) und erzeugt mit magistral-medium-2509 Coaching-Hinweise (Phase 2, Live-Overlay) bzw. ein strukturiertes Protokoll (Phase 1, Async). Zweck ist die methodische Unterstützung des Coaches und die Bereitstellung eines Protokolls für das Gegenüber. Betroffene sind Coach und Gegenüber.

## 2. Notwendigkeit und Verhältnismäßigkeit

Die Verarbeitung ist auf den Zweck begrenzt. Datenminimierung: das Audit-Log enthält nur Metadaten, keine Gesprächsinhalte. Phase 1 liefert den unmittelbaren Nutzen (Protokoll als Gegenleistung) bei geringem Risiko. Die Live-Verarbeitung in Phase 2 ist auf Trigger beschränkt, sodass nicht jede Äußerung das Reasoning-Modell erreicht. Es findet keine Emotionserkennung statt; Ableitungen sind rein inhaltlich.

## 3. Identifizierte Risiken

- Verarbeitung besonderer Kategorien (Art. 9): Gesprächsinhalte berühren psychische und gesundheitliche Themen.
- Vertraulichkeitsverletzung bei fehlender Einwilligung (§ 201 StGB).
- Unbefugte Kenntnisnahme von Audio oder Transkript.
- Übermäßige Aufbewahrung von Inhalten.
- Fehlleitung von Daten an einen Non-EU-Dienst.

## 4. Abhilfemaßnahmen

| Risiko | Maßnahme | Nachweis |
|---|---|---|
| Fehlende Einwilligung | ConsentGate erzwingt dokumentierte Einwilligung vor Verarbeitung; Ablehnung mit HTTP 403 | Akzeptanzkriterium Consent; Audit-Log |
| Non-EU-Datenabfluss | EU-Routing erzwungen, nur api.mistral.ai bzw. EU-Gladia; Gate E1 | Gate E1 grün |
| Klartext-PII in Logs | nur Metadaten im Audit-Log, pii_present gleich false; Gate E2 und E4 | Gate E2 und E4 grün |
| Übermäßige Aufbewahrung | feste Aufbewahrungsfrist und Löschroutine | RETENTION-DELETION.md |
| Modell-Drift durch bewegliche Tags | gepinnte Modellversionen; Gate F1 | Gate F1 grün |
| Unbefugter Zugriff | Zugriffsbeschränkung, lokale Verarbeitung von Display und MCP, Transportverschlüsselung | TOMs.md |

## 5. Restrisiko und Ergebnis

Nach Umsetzung der Maßnahmen ist das Restrisiko tragbar für den internen Einsatz ohne echte Klientendaten. Vor produktivem Echtbetrieb mit echten Daten ist die juristische Freigabe (Einwilligungstext, AI-Act-Einordnung, OSS-Lizenzprüfung durch Carsten Lexa) erforderlich. Die DSFA wird bei wesentlichen Änderungen der Verarbeitung aktualisiert.

## 6. Beteiligte und Freigabe

Erstellt durch die Architektur-Rolle. Fachliche und juristische Abnahme erfolgt vor Live-Schaltung. Die Datenschutz-Stelle der Organisation ist einzubinden.
