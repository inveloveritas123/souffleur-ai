"""ConsentGate — erzwingt dokumentierte Einwilligung vor Verarbeitung (§201 StGB).

Framework-agnostisch: kein FastAPI-Import hier (Phase-1-API folgt erst in Welle 6).
`ConsentDeniedError.status_code == 403` — die Web-Schicht mappt die Exception 1:1 auf
HTTP 403. Verarbeitung ohne tenant_id wird ebenfalls abgelehnt (ARCHITECTURE.md
"Mandantentrennung").
"""
from __future__ import annotations

from dataclasses import dataclass


class ConsentDeniedError(Exception):
    """Verarbeitung ohne (gültige) dokumentierte Einwilligung — entspricht HTTP 403."""

    status_code = 403

    def __init__(
        self, message: str = "Verarbeitung ohne dokumentierte Einwilligung abgelehnt (§201 StGB)"
    ) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ConsentRecord:
    """Eine dokumentierte, erteilte Einwilligung (z. B. aus dem Web-UI-Consent-Schritt).

    `text_version` (Finding 3, §201 StGB): welche Version des Einwilligungstexts der/die
    Teilnehmende bestätigt hat — optional für Rückwärtskompatibilität mit bestehenden
    Call-Sites, die (noch) keine Version führen.
    """

    consent_ref: str
    tenant_id: str
    session_id: str
    granted_at: str
    text_version: str | None = None


class ConsentGate:
    """Hält dokumentierte Einwilligungen vor und prüft sie vor jeder Verarbeitung."""

    def __init__(self) -> None:
        self._records: dict[str, ConsentRecord] = {}

    def register(self, record: ConsentRecord) -> None:
        """Dokumentiert eine erteilte Einwilligung. Überschreibt eine vorhandene Referenz nicht."""
        if record.consent_ref in self._records:
            raise ValueError(f"consent_ref bereits dokumentiert: {record.consent_ref!r}")
        self._records[record.consent_ref] = record

    def check(self, consent_ref: str | None, tenant_id: str) -> ConsentRecord:
        """Prüft eine Consent-Referenz vor der Verarbeitung.

        Wirft `ConsentDeniedError` (HTTP 403), wenn `consent_ref` fehlt, unbekannt ist oder
        zu einem anderen Mandanten gehört. Gibt sonst den dokumentierten Consent-Eintrag zurück.
        """
        if not tenant_id:
            raise ConsentDeniedError("Verarbeitung ohne tenant_id abgelehnt (Mandantentrennung)")
        if not consent_ref:
            raise ConsentDeniedError()
        record = self._records.get(consent_ref)
        if record is None or record.tenant_id != tenant_id:
            raise ConsentDeniedError()
        return record
