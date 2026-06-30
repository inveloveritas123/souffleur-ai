"""Gate E4 — Audit-Log-Vollständigkeit/Konformität (deterministisch).

Validiert jede Audit-Zeile gegen templates/AUDIT-LOG.schema.json (stdlib, ohne jsonschema-Dep):
Pflichtfelder vorhanden, Enums gültig, keine unbekannten Felder (additionalProperties:false),
routing_region == EU, pii_present (falls vorhanden) == false. SKIP ohne Audit-Log-Kontext.
"""
import json
import os
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E4"

_DEFAULT_SCHEMA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "templates", "AUDIT-LOG.schema.json")


def _load_schema(schema_path):
    path = schema_path or _DEFAULT_SCHEMA
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_JSON_TYPES = {
    "string": str, "integer": int, "number": (int, float),
    "boolean": bool, "object": dict, "array": list,
}


def _type_ok(value, declared):
    py = _JSON_TYPES.get(declared)
    if py is None:
        return True
    if declared == "boolean":
        return isinstance(value, bool)            # 0/1/"false" sind KEIN boolean
    if declared in ("integer", "number"):
        return isinstance(value, py) and not isinstance(value, bool)
    return isinstance(value, py)


def _validate(entry, schema):
    errs = []
    props = schema.get("properties", {})
    required = schema.get("required", [])
    allowed = set(props)
    for k in required:
        if k not in entry:
            errs.append("Pflichtfeld fehlt: %s" % k)
    if schema.get("additionalProperties") is False:
        for k in entry:
            if k not in allowed:
                errs.append("unbekanntes Feld: %s" % k)
    for k, v in entry.items():
        spec = props.get(k)
        if not spec:
            continue
        if "type" in spec and not _type_ok(v, spec["type"]):
            errs.append("%s hat falschen Typ (erwartet %s): %r" % (k, spec["type"], v))
        enum = spec.get("enum")
        if enum is not None and v not in enum:
            errs.append("%s nicht im Enum: %r" % (k, v))
    # E2-Konsistenz: pii_present darf, wenn vorhanden, NUR exakt false sein.
    if "pii_present" in entry and entry["pii_present"] is not False:
        errs.append("pii_present muss false sein")
    return errs


def run(target, exclude_dirs=None, exclude_abs=None, audit_log=None, schema_path=None, **_):
    if not audit_log or not os.path.isfile(audit_log):
        return common.skipped(GATE, "kein Audit-Log (nicht anwendbar)", common.NOT_APPLICABLE)
    try:
        schema = _load_schema(schema_path)
    except (OSError, ValueError) as ex:
        return common.CheckResult(GATE, common.FAIL, "Schema nicht ladbar: %s" % ex)
    findings, n = [], 0
    with open(audit_log, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                entry = json.loads(line)
            except ValueError:
                findings.append(common.Finding(os.path.basename(audit_log), ln, "parse", "kein JSON"))
                continue
            for err in _validate(entry, schema):
                findings.append(common.Finding(os.path.basename(audit_log), ln, "schema", err))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d Audit-Schema-Verstoß/Verstöße" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "Audit-Log schema-konform (%d Einträge)" % n)


if __name__ == "__main__":
    ap = sys.argv[1] if len(sys.argv) > 1 else None
    res = run(".", audit_log=ap)
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
