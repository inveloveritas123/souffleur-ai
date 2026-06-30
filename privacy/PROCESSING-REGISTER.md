# PROCESSING-REGISTER — Souffleur AI

Verzeichnis von Verarbeitungstätigkeiten nach Art. 30 DSGVO.

## Verantwortlicher

ZUKUNFTSBUND (interner Einsatz). Datenschutz-Kontakt über die organisationsinterne Datenschutz-Stelle.

## Verarbeitungstätigkeiten

| Tätigkeit | Zweck | Datenarten | Betroffene | Rechtsgrundlage | Empfänger | Region | Aufbewahrung |
|---|---|---|---|---|---|---|---|
| Audio-Capture | Erfassung des Gesprächs zur Transkription | Audio (Stimme) | Coach, Gegenüber | Art. 6 a, Art. 9 a | lokal | EU | bis Transkriptionsende |
| Transkription und Diarisation | Protokoll mit Sprecher-Trennung | Audio, Transkript, Sprecher-Label | Coach, Gegenüber | Art. 6 a, Art. 9 a | Mistral SAS Paris | EU | siehe Retention |
| Trigger-Klassifikation (Phase 2) | Entscheidung wann Karte | Transkript-Segment | Coach, Gegenüber | Art. 6 a, Art. 9 a | Mistral SAS Paris | EU | flüchtig |
| Reasoning und Zusammenfassung | Coaching-Hinweise, Protokoll | Transkript, abgeleitete Hinweise | Coach, Gegenüber | Art. 6 a, Art. 9 a | Mistral SAS Paris | EU | siehe Retention |
| Audit-Protokollierung | Nachweis der Verarbeitung | Metadaten (pseudonym) | Coach | Art. 6 c, Art. 6 f | lokal | EU | siehe Retention |

## Besondere Kategorien (Art. 9)

Gesprächsinhalte berühren psychische und gesundheitliche Themen und gelten als besondere Kategorien. Verarbeitung nur auf Basis ausdrücklicher Einwilligung (Art. 9 Abs. 2 lit. a).

## Technisch-organisatorische Maßnahmen

Siehe TOMs.md. EU-Routing erzwungen, keine Klartext-PII in Logs, dokumentierte Einwilligung vor Verarbeitung.
