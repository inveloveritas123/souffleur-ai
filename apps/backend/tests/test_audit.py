"""Welle 2 — AuditLog: JSONL nach E4-Schema, routing_region EU, pii_present false."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from souffleur.audit import AuditLog

REPO_ROOT = Path(__file__).resolve().parents[3]
GATES_CHECKS_DIR = REPO_ROOT / "gates" / "checks"
SCHEMA_PATH = REPO_ROOT / "templates" / "AUDIT-LOG.schema.json"


def _load_e4_checker() -> Any:
    """Lädt gates/checks/e4_audit_log.py standalone (read-only Konsument, kein Edit)."""
    checks_dir = str(GATES_CHECKS_DIR)
    if checks_dir not in sys.path:
        sys.path.insert(0, checks_dir)
    spec = importlib.util.spec_from_file_location("e4_audit_log", GATES_CHECKS_DIR / "e4_audit_log.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["e4_audit_log"] = module
    spec.loader.exec_module(module)
    return module


def test_audit_log_writes_jsonl_with_eu_region_and_no_pii(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLog(str(log_path))

    entry = audit.record(
        actor="backend",
        action="model_call",
        resource="voxtral-mini-2602:transcribe_batch",
        tenant_id="zukunftsbund",
        result="success",
        model="voxtral-mini-2602",
        correlation_id="11111111-1111-1111-1111-111111111111",
    )

    assert entry.routing_region == "EU"
    assert entry.pii_present is False

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["routing_region"] == "EU"
    assert parsed["pii_present"] is False
    assert parsed["tenant_id"] == "zukunftsbund"
    assert parsed["action"] == "model_call"
    # additionalProperties:false im Schema -> keine ueberschuessigen Felder.
    allowed = {
        "timestamp", "actor", "action", "resource", "tenant_id",
        "result", "routing_region", "model", "pii_present", "correlation_id",
    }
    assert set(parsed) <= allowed
    # Niemals Gespraechsinhalt: resource referenziert nur Modell+Operation, kein Transkript-Text.
    assert "transcribe_batch" in parsed["resource"]


def test_audit_log_requires_tenant_id(tmp_path: Path) -> None:
    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    with pytest.raises(ValueError):
        audit.record(
            actor="backend", action="read", resource="session:abc",
            tenant_id="", result="denied",
        )


def test_audit_log_passes_gate_e4(tmp_path: Path) -> None:
    """Akzeptanzkriterium: ein über AuditLog erzeugtes Log läuft durch e4_audit_log grün."""
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLog(str(log_path))
    audit.record(
        actor="backend", action="model_call", resource="magistral-medium-2509:summary",
        tenant_id="zukunftsbund", result="success", model="magistral-medium-2509",
    )
    audit.record(
        actor="consent-gate", action="read", resource="session:42",
        tenant_id="zukunftsbund", result="denied",
    )

    e4 = _load_e4_checker()
    result = e4.run(str(REPO_ROOT), audit_log=str(log_path), schema_path=str(SCHEMA_PATH))

    assert result.status == "PASS", f"E4 nicht gruen: {result.summary} / {result.findings}"
