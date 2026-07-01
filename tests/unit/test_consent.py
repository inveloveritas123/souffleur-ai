"""Unit-Tests core/consent.py — ConsentGate erzwingt §201 StGB (Gate: 403-Vertrag)."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.core.consent import ConsentDeniedError, ConsentGate, ConsentRecord  # noqa: E402


def _record(consent_ref: str = "consent-1", tenant_id: str = "zukunftsbund") -> ConsentRecord:
    return ConsentRecord(
        consent_ref=consent_ref,
        tenant_id=tenant_id,
        session_id="session-1",
        granted_at="2026-07-01T00:00:00+00:00",
    )


class ConsentGateGrantedTest(unittest.TestCase):
    def test_check_returns_record_for_valid_consent(self) -> None:
        gate = ConsentGate()
        record = _record()
        gate.register(record)

        result = gate.check(consent_ref="consent-1", tenant_id="zukunftsbund")

        self.assertEqual(result, record)


class ConsentGateDeniedTest(unittest.TestCase):
    def test_missing_tenant_id_denied(self) -> None:
        gate = ConsentGate()
        with self.assertRaises(ConsentDeniedError) as ctx:
            gate.check(consent_ref="anything", tenant_id="")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("tenant_id", ctx.exception.message)

    def test_missing_consent_ref_denied(self) -> None:
        gate = ConsentGate()
        with self.assertRaises(ConsentDeniedError):
            gate.check(consent_ref=None, tenant_id="zukunftsbund")

    def test_unknown_consent_ref_denied(self) -> None:
        gate = ConsentGate()
        with self.assertRaises(ConsentDeniedError):
            gate.check(consent_ref="does-not-exist", tenant_id="zukunftsbund")

    def test_consent_ref_for_other_tenant_denied(self) -> None:
        gate = ConsentGate()
        gate.register(_record(consent_ref="c1", tenant_id="tenant-a"))
        with self.assertRaises(ConsentDeniedError):
            gate.check(consent_ref="c1", tenant_id="tenant-b")

    def test_default_message_mentions_stgb(self) -> None:
        error = ConsentDeniedError()
        self.assertIn("201", error.message)


class ConsentGateRegisterTest(unittest.TestCase):
    def test_duplicate_consent_ref_raises_value_error(self) -> None:
        gate = ConsentGate()
        gate.register(_record(consent_ref="dup"))
        with self.assertRaises(ValueError):
            gate.register(_record(consent_ref="dup"))


if __name__ == "__main__":
    unittest.main()
