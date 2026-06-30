"""Welle 2 — ConsentGate: 403 ohne Einwilligung, Erfolg mit gültiger Consent-Referenz."""
from __future__ import annotations

import pytest
from souffleur.core.consent import ConsentDeniedError, ConsentGate, ConsentRecord


def test_consent_gate_rejects_processing_without_consent_ref() -> None:
    gate = ConsentGate()
    with pytest.raises(ConsentDeniedError) as excinfo:
        gate.check(consent_ref=None, tenant_id="zukunftsbund")
    assert excinfo.value.status_code == 403


def test_consent_gate_rejects_unknown_consent_ref() -> None:
    gate = ConsentGate()
    with pytest.raises(ConsentDeniedError) as excinfo:
        gate.check(consent_ref="does-not-exist", tenant_id="zukunftsbund")
    assert excinfo.value.status_code == 403


def test_consent_gate_rejects_consent_from_other_tenant() -> None:
    gate = ConsentGate()
    gate.register(
        ConsentRecord(
            consent_ref="consent-1", tenant_id="other-tenant",
            session_id="s1", granted_at="2026-07-01T10:00:00+00:00",
        )
    )
    with pytest.raises(ConsentDeniedError):
        gate.check(consent_ref="consent-1", tenant_id="zukunftsbund")


def test_consent_gate_allows_processing_with_valid_consent_ref() -> None:
    gate = ConsentGate()
    record = ConsentRecord(
        consent_ref="consent-1", tenant_id="zukunftsbund",
        session_id="s1", granted_at="2026-07-01T10:00:00+00:00",
    )
    gate.register(record)

    result = gate.check(consent_ref="consent-1", tenant_id="zukunftsbund")

    assert result is record


def test_consent_gate_rejects_without_tenant_id() -> None:
    gate = ConsentGate()
    with pytest.raises(ConsentDeniedError):
        gate.check(consent_ref="consent-1", tenant_id="")
