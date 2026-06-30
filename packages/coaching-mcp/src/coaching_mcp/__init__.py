"""Souffleur AI — Coaching-MCP-Server.

Stellt Coaching-Wissen (Frameworks, Fragetechniken, Einwand-Reframes) zur
Laufzeit über das Model Context Protocol (MCP) bereit. Das Wissen liegt als
strukturierte Daten in ``knowledge/`` (kein Fine-Tuning, kein externer
Datenabfluss, läuft rein lokal).
"""

from coaching_mcp.types import CardType, KnowledgeEntry

__all__ = ["CardType", "KnowledgeEntry"]
