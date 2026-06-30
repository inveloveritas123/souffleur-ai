# PROCESSORS-SUBPROCESSORS — Souffleur AI

Auftragsverarbeiter und Unterauftragsverarbeiter nach Art. 28 DSGVO.

## Auftragsverarbeiter

| Verarbeiter | Leistung | Sitz / Region | Rechtsgrundlage | AV-Vertrag |
|---|---|---|---|---|
| Mistral SAS | Transkription, Diarisation, Reasoning (Voxtral, Magistral, Ministral) | Paris, Frankreich (EU) | Art. 28 | erforderlich vor Echtbetrieb |
| Gladia (optional) | Live-Transkription als Latenz-Fallback | Frankreich (EU) | Art. 28 | erforderlich falls aktiviert |

## Unterauftragsverarbeiter

Zum Zeitpunkt der Erstellung sind keine weiteren Unterauftragsverarbeiter mit Zugriff auf personenbezogene Daten vorgesehen. Coaching-MCP-Server und Display-Schicht laufen lokal ohne externen Datenabfluss. Vor Echtbetrieb ist die jeweils aktuelle Unterauftragsverarbeiter-Liste der eingesetzten Dienste zu prüfen und vertraglich zu erfassen.

## Pflichten

- Abschluss eines Auftragsverarbeitungsvertrags (Art. 28) mit jedem Verarbeiter vor produktivem Einsatz.
- Sicherstellung der EU-Region und vertraglicher Zero-Retention bzw. kein Modelltraining auf den übermittelten Inhalten.
- Dokumentation jeder Änderung der Verarbeiter-Liste.

## Region

Alle eingesetzten Verarbeiter sitzen in der EU. Drittlandübermittlung: nein. Siehe THIRD-COUNTRY-TRANSFERS.md.
