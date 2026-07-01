# DATA-FLOW — Souffleur AI

Datenflussbeschreibung der Verarbeitung. Alle Verarbeitungsschritte verbleiben in der EU.

## Datenquellen

- Audio des Coaching-Gesprächs (Phase 1: Upload bzw. lokale Aufnahme; Phase 2: lokale Dual-Source-Capture, System-Audio gleich Gegenüber und Mikrofon gleich Coach).
- Einwilligungs-Metadaten (Zeitpunkt, Form, Referenz-ID der dokumentierten Einwilligung).

## Verarbeitungsschritte (Fluss)

1. Capture (lokal, Browser bzw. Tauri-Overlay) erfasst Audio. Es findet keine lokale dauerhafte Speicherung des Rohaudios über die Verarbeitung hinaus statt.
2. ConsentGate prüft die dokumentierte Einwilligung. Ohne gültige Einwilligung wird die Verarbeitung mit HTTP 403 abgelehnt (Bezug § 201 StGB).
3. Transkription und Diarisation über Mistral (Voxtral) in Paris, EU. Phase 1 Batch über voxtral-mini-2602, Phase 2 Live über voxtral-mini-realtime-2602. Optional lokaler MLX-Worker (voxtral_local) auf der Maschine des Coaches.
4. Trigger-Router (Phase 2) klassifiziert Segmente regelbasiert und mit ministral-3b-2512, ob eine Karte sinnvoll ist.
5. Reasoning über magistral-medium-2509 in Paris, EU, ergänzt um Coaching-Wissen aus dem lokalen MCP-Server. Erzeugt Karten (Phase 2) bzw. Protokoll-Zusammenfassung (Phase 1).
6. Display: Web-Protokoll (Phase 1) bzw. semitransparentes Overlay (Phase 2).
7. Audit-Log schreibt zu jedem Modellaufruf einen Metadaten-Eintrag (kein Gesprächsinhalt, pii_present gleich false, routing_region gleich EU).

## Empfänger

- Auftragsverarbeiter Mistral SAS, Paris, Frankreich (EU) für Transkription und Reasoning.
- Optional Gladia (Frankreich, EU) ausschließlich als Latenz-Fallback für die Live-Transkription.
- Keine weiteren externen Empfänger. Coaching-MCP-Server und Display laufen lokal.

## Speicherorte und Grenzen

- Audio und Transkripte werden gemäß RETENTION-DELETION.md aufbewahrt und gelöscht.
- Audit-Log liegt lokal als JSONL nach dem Schema in templates AUDIT-LOG.schema.json.
- Region aller Verarbeitungsschritte: EU. Drittlandübermittlung: nein.

## Diagramm

```
Capture (lokal) → ConsentGate → Voxtral STT/Diarisation (Paris, EU)
   → [Phase2: TriggerRouter ministral-3b] → magistral-medium + Coaching-MCP (lokal)
   → Display (Web-Protokoll / Overlay)        ⟂ Audit-Log (lokal, EU-Metadaten)
```
