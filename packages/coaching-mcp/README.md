# packages/coaching-mcp — Coaching-Wissensschicht (MCP-Server)

Eigenes IP: Coaching-Frameworks, Fragetechniken und Methodenbausteine als strukturiertes Wissen, das das LLM zur Laufzeit holt. Bewusst KEIN Fine-Tuning — Wissen lebt im Kontext, nicht in Gewichten (aktualisierbar, prüfbar).

## Was hier hineingehört

- `src/` — MCP-Server (stdio bzw. HTTP, Port aus SOUFFLEUR_MCP_PORT). Tools liefern passendes Coaching-Wissen zu einem Karten-Typ (Einwand, vertiefende Frage, Strukturhinweis).
- `knowledge/` — strukturiertes Coaching-Wissen (Frameworks, Fragetechniken) als versionierte Daten.

## Anbindung

Die ReasoningEngine im Backend ruft diesen Server, wenn der Trigger-Router eine Karte anfordert. Läuft lokal, kein externer Datenabfluss.
