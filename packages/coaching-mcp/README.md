# packages/coaching-mcp — Coaching-Wissensschicht (MCP-Server)

Eigenes IP: Coaching-Frameworks, Fragetechniken und Methodenbausteine als strukturiertes Wissen, das das LLM zur Laufzeit holt. Bewusst KEIN Fine-Tuning — Wissen lebt im Kontext, nicht in Gewichten (aktualisierbar, prüfbar).

## Was hier hineingehört

- `src/` — MCP-Server (stdio bzw. HTTP, Port aus SOUFFLEUR_MCP_PORT). Tools liefern passendes Coaching-Wissen zu einem Karten-Typ (Einwand, vertiefende Frage, Strukturhinweis).
- `knowledge/` — strukturiertes Coaching-Wissen (Frameworks, Fragetechniken) als versionierte Daten.

## Anbindung

Die ReasoningEngine im Backend ruft diesen Server, wenn der Trigger-Router eine Karte anfordert. Läuft lokal, kein externer Datenabfluss.

## Implementierung (Welle 7)

- `src/coaching_mcp/types.py` — `CardType` (objection/deepening_question/structure_hint), `KnowledgeEntry`.
- `src/coaching_mcp/knowledge_store.py` — lädt `knowledge/*.json` von Platte (keine Netzwerk-I/O), indiziert nach Karten-Typ, rankt optional per Freitext-Query gegen `trigger_keywords`.
- `src/coaching_mcp/tools.py` — Tool `get_coaching_knowledge(card_type, query=None, limit=3)` und `list_card_types()`.
- `src/coaching_mcp/server.py` — MCP-Stdio-JSON-RPC-Server (newline-delimited JSON-RPC 2.0): `initialize`, `tools/list`, `tools/call`.
- `src/coaching_mcp/__main__.py` — Entry-Point (`python -m coaching_mcp` bzw. Console-Script `coaching-mcp`).

**Abweichung vom Auftrag (begründet):** Das offizielle MCP-Python-SDK (`mcp` auf PyPI) erfordert laut PyPI-Metadaten in jeder Version `>=3.10`. Die Root-Tooling-Config (`pyproject.toml`: `mypy` `python_version = "3.9"`) sowie die für diese Welle vorgeschriebene Verifikation (`python3 -m pytest ...`, wobei `python3` auf das System-Python 3.9.6 zeigt) sind auf Python 3.9 gepinnt — das SDK kann dort nicht installiert/importiert werden. Statt den Auftrag zu blockieren oder den Python-Baseline-Pin des gesamten Monorepos in dieser einzelnen Welle zu ändern, implementiert `server.py` das benötigte Subset des MCP-Stdio-Protokolls (newline-delimited JSON-RPC 2.0, `initialize`/`tools/list`/`tools/call`, gleiche `Tool`/`CallToolResult`-JSON-Form wie das offizielle SDK) selbst, nur mit der Standardbibliothek. `knowledge_store.py` und `tools.py` haben keine Abhängigkeit auf `server.py` und lassen sich beim Umstieg auf das offizielle SDK (sobald der Laufzeit-Container in W10/W13 auf Python >=3.10 läuft — siehe `[project.optional-dependencies].mcp-sdk` in `pyproject.toml`) unverändert weiterverwenden.
