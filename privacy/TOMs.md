# TOMs — Souffleur AI (Technisch-organisatorische Maßnahmen, Art. 32 DSGVO)

## Vertraulichkeit

- Zugriffsbeschränkung auf das Backend und die Audit-Daten; nur autorisierte Coaches.
- Transportverschlüsselung (TLS) für alle Verbindungen zu Mistral und zum optionalen Gladia-Fallback.
- Keine Klartext-PII in Logs, Prompts oder Outputs (Gate E2 durchgesetzt).
- Coaching-MCP-Server und Display-Schicht laufen lokal ohne externen Datenabfluss.

## Integrität

- Audit-Log nach festem Schema, append-only als JSONL, validiert über Gate E4.
- Gepinnte Modellversionen verhindern unkontrollierte Modell-Drift (Gate F1).
- Geteilte Typen und Schemas im Paket shared sichern konsistente Datenstrukturen.

## Verfügbarkeit und Belastbarkeit

- Containerisierte Dienste über docker-compose, reproduzierbar startbar.
- STT als austauschbarer Port mit definiertem Fallback (Gladia) bei Latenzproblemen.
- Lokaler MLX-Worker als Ausweichpfad ohne Cloud-Abhängigkeit.

## EU-Souveränität und Routing

- EU-Routing erzwungen; kein Non-EU-Endpunkt in Code oder Konfiguration (Gate E1).
- Alle Auftragsverarbeiter in der EU; keine Drittlandübermittlung.

## Einwilligung und Transparenz

- ConsentGate erzwingt dokumentierte Einwilligung vor jeder Verarbeitung (§ 201 StGB).
- Transparente Positionierung: das Overlay verbirgt nur den privaten Hinweis-Layer des Coaches beim Screen-Sharing, nicht die Tatsache der KI-Nutzung.

## Überprüfung

- Deterministische Gates laufen vor jedem Push; rote Block-Gates verhindern Fortschritt.
- Die Maßnahmen werden bei wesentlichen Änderungen überprüft und aktualisiert.
