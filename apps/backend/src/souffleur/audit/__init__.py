"""AuditLog — unveränderliche Einträge nach templates/AUDIT-LOG.schema.json (Gate E4)."""

from souffleur.audit.audit_log import AuditEntry, AuditLog

__all__ = ["AuditEntry", "AuditLog"]
