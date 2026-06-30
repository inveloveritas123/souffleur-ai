"""Gate E3 — Mandantentrennung (deterministisch, aus dem Audit-Log).

Prinzip: Ein Audit-Log-Eintrag mit result=success, dessen Ressource-Mandant (tenant:<owner>)
vom handelnden Mandanten (tenant_id) abweicht, ist ein Tenant-übergreifender Zugriff → FAIL.
Denied-Versuche sind erlaubt (genau die soll die App erzeugen). SKIP ohne Audit-Log-Kontext.
"""
import json
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E3"
# Mandant der Ressource — auch ohne folgendes "/customer:" (sonst Evasion durch verkürzte Ressource).
_OWNER_RE = re.compile(r"tenant:([^/\s]+)")


def run(target, exclude_dirs=None, exclude_abs=None, audit_log=None, **_):
    if not audit_log or not os.path.isfile(audit_log):
        return common.skipped(GATE, "kein Audit-Log (nicht anwendbar)", common.NOT_APPLICABLE)
    findings = []
    with open(audit_log, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                findings.append(common.Finding(os.path.basename(audit_log), ln, "audit-parse", "kein JSON"))
                continue
            m = _OWNER_RE.search(str(e.get("resource", "")))
            owner = m.group(1) if m else None
            actor = e.get("tenant_id")
            # 'unknown' (Nicht-gefunden) erscheint nur bei denied; '*' ist kein legitimer Mandant.
            # Kein Owner-Wert wird mehr ausgenommen -> jeder Cross-Tenant-ERFOLG schlägt an.
            if owner and actor and owner != actor and e.get("result") == "success":
                findings.append(common.Finding(
                    os.path.basename(audit_log), ln, "cross-tenant-success",
                    "actor=%s resource-tenant=%s" % (actor, owner)))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d Tenant-übergreifende(r) Erfolg(e) im Audit-Log" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "keine Tenant-übergreifenden Zugriffe (Audit-Log)")


if __name__ == "__main__":
    ap = sys.argv[1] if len(sys.argv) > 1 else None
    res = run(".", audit_log=ap)
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
