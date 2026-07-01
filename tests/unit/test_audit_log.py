"""Unit-Tests audit/audit_log.py — JSONL, routing_region=EU, pii_present=false (Gate E4/E2)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.audit.audit_log import AuditLog  # noqa: E402


class AuditLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="souffleur-audit-test-")
        self.addCleanup(shutil.rmtree, self._tmp_dir, ignore_errors=True)
        self._path = os.path.join(self._tmp_dir, "nested", "audit-log.jsonl")

    def _read_lines(self) -> list[dict]:
        with open(self._path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def test_creates_parent_directory(self) -> None:
        AuditLog(self._path)
        self.assertTrue(os.path.isdir(os.path.dirname(self._path)))

    def test_record_writes_expected_fields(self) -> None:
        log = AuditLog(self._path)
        entry = log.record(
            actor="api:protocol",
            action="model_call",
            resource="voxtral-mini-2602:transcribe_batch",
            tenant_id="zukunftsbund",
            result="success",
            model="voxtral-mini-2602",
            correlation_id="corr-1",
        )

        self.assertEqual(entry.routing_region, "EU")
        self.assertFalse(entry.pii_present)

        lines = self._read_lines()
        self.assertEqual(len(lines), 1)
        record = lines[0]
        self.assertEqual(record["routing_region"], "EU")
        self.assertEqual(record["pii_present"], False)
        self.assertEqual(record["tenant_id"], "zukunftsbund")
        self.assertEqual(record["actor"], "api:protocol")
        self.assertEqual(record["model"], "voxtral-mini-2602")
        self.assertEqual(record["correlation_id"], "corr-1")
        self.assertIn("timestamp", record)

    def test_record_omits_optional_fields_when_absent(self) -> None:
        log = AuditLog(self._path)
        log.record(
            actor="api:consent",
            action="create",
            resource="consent:session-1",
            tenant_id="zukunftsbund",
            result="success",
        )
        record = self._read_lines()[0]
        self.assertNotIn("model", record)
        self.assertNotIn("correlation_id", record)

    def test_record_never_contains_transcript_text_keys(self) -> None:
        """Gate E2: das Audit-Log darf niemals Gesprächsinhalt tragen — nur Metadaten-Felder."""
        log = AuditLog(self._path)
        log.record(
            actor="api:protocol",
            action="model_call",
            resource="magistral-medium-2509:summary",
            tenant_id="zukunftsbund",
            result="success",
            model="magistral-medium-2509",
        )
        record = self._read_lines()[0]
        allowed_keys = {
            "timestamp",
            "actor",
            "action",
            "resource",
            "tenant_id",
            "result",
            "routing_region",
            "pii_present",
            "model",
            "correlation_id",
        }
        self.assertTrue(set(record.keys()).issubset(allowed_keys))

    def test_record_requires_tenant_id(self) -> None:
        log = AuditLog(self._path)
        with self.assertRaises(ValueError):
            log.record(
                actor="api:protocol",
                action="model_call",
                resource="x",
                tenant_id="",
                result="success",
            )

    def test_multiple_records_appended_in_order(self) -> None:
        log = AuditLog(self._path)
        log.record(actor="a1", action="create", resource="r1", tenant_id="t", result="success")
        log.record(actor="a2", action="read", resource="r2", tenant_id="t", result="denied")
        lines = self._read_lines()
        self.assertEqual([line["actor"] for line in lines], ["a1", "a2"])
        self.assertEqual(lines[1]["result"], "denied")

    def test_path_property(self) -> None:
        log = AuditLog(self._path)
        self.assertEqual(log.path, self._path)


if __name__ == "__main__":
    unittest.main()
