# BREACH-RUNBOOK — Souffleur AI (Verletzung des Schutzes personenbezogener Daten)

Reaktionsplan nach Art. 33 und 34 DSGVO.

## Erkennung

- Hinweise aus Audit-Log-Auffälligkeiten, Zugriffsfehlern, gemeldeten Vorfällen oder Dienst-Störungen.
- Jeder Verdacht wird unverzüglich an die organisationsinterne Datenschutz-Stelle gemeldet.

## Sofortmaßnahmen

1. Eindämmung: betroffene Sitzungen beenden, Zugang sperren, betroffene Komponente isolieren.
2. Bewertung: Art der Daten (auch besondere Kategorien Art. 9), Umfang, betroffene Personen, Ursache.
3. Beweissicherung: relevante Audit-Einträge sichern (Metadaten, keine zusätzlichen Klartext-Inhalte erzeugen).

## Meldung

- Meldung an die Aufsichtsbehörde nach Art. 33 binnen 72 Stunden, sofern ein Risiko für die Rechte und Freiheiten besteht.
- Benachrichtigung der betroffenen Personen nach Art. 34 bei voraussichtlich hohem Risiko, insbesondere wegen der besonderen Kategorien.

## Nachbereitung

- Ursachenanalyse und Behebung.
- Aktualisierung der TOMs und gegebenenfalls der DPIA.
- Dokumentation des Vorfalls und der getroffenen Maßnahmen.

## Verantwortliche Rollen

- Meldende Stelle: jede Person, die einen Vorfall bemerkt.
- Koordination: organisationsinterne Datenschutz-Stelle.
- Technische Behebung: Backend-Verantwortliche.
