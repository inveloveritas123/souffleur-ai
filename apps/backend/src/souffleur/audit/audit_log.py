"""AuditLog — unveränderliche JSONL-Einträge nach `templates/AUDIT-LOG.schema.json` (Gate E4).

Loggt NIEMALS Gesprächsinhalt (kein Transkript-Text, keine Klartext-PII — Gate E2).
Jeder Eintrag trägt `routing_region="EU"` (Gate E1) und `pii_present=False` fest verdrahtet.
`tenant_id` ist Pflicht und wird durchgängig geführt (Vorbereitung Mandantentrennung, Gate E3).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
from dataclasses import dataclass
from typing import Literal

Action = Literal["create", "read", "update", "delete", "export", "gate_run", "model_call"]
Result = Literal["success", "denied", "error"]


def _now_iso() -> str:
    """RFC3339/ISO-8601-Zeitstempel in UTC (passend zum Schema-Format date-time)."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditEntry:
    """Ein einzelner Audit-Eintrag — Felder exakt gemäß AUDIT-LOG.schema.json."""

    timestamp: str
    actor: str
    action: Action
    resource: str
    tenant_id: str
    result: Result
    routing_region: Literal["EU"] = "EU"
    model: str | None = None
    pii_present: bool = False
    correlation_id: str | None = None

    def to_dict(self) -> dict:
        """Serialisiert nur belegte Felder — `additionalProperties: false` im Schema."""
        entry: dict = {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "tenant_id": self.tenant_id,
            "result": self.result,
            "routing_region": self.routing_region,
            "pii_present": self.pii_present,
        }
        if self.model is not None:
            entry["model"] = self.model
        if self.correlation_id is not None:
            entry["correlation_id"] = self.correlation_id
        return entry


class AuditLog:
    """Schreibt Audit-Einträge append-only als JSONL-Datei."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    @property
    def path(self) -> str:
        return self._path

    def record(
        self,
        *,
        actor: str,
        action: Action,
        resource: str,
        tenant_id: str,
        result: Result,
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEntry:
        """Erzeugt und persistiert einen Audit-Eintrag. Niemals Gesprächsinhalt übergeben."""
        if not tenant_id:
            raise ValueError("tenant_id ist Pflicht (Mandantentrennung, Gate E3)")
        entry = AuditEntry(
            timestamp=_now_iso(),
            actor=actor,
            action=action,
            resource=resource,
            tenant_id=tenant_id,
            result=result,
            routing_region="EU",
            model=model,
            pii_present=False,
            correlation_id=correlation_id,
        )
        line = json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry
