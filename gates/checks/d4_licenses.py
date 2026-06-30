"""Gate D4 — Lizenz-Compliance der Dependencies via `pip-licenses` (optional, kein Fake).

Ruft `pip-licenses --format=json` (cwd=target), parst die Liste und flaggt jede
Dependency, deren Lizenz copyleft/unklar ist (GPL/AGPL/LGPL/UNKNOWN).

D4 ist ein WARN-Gate: copyleft/unklare Lizenzen blockieren nicht automatisch, sind
aber ein juristischer Pruefpunkt.
- copyleft/unklare Lizenz gefunden -> WARN (mit Fundstellen Paket -> Lizenz).
- pip-licenses nicht installiert -> SKIP/TOOL_MISSING (auch wenn ein requirements-File
  existiert: ohne Tool wird NICHT vorgetaeuscht).
- sonst PASS.
"""
import json
import os
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "D4"
# Substrings (case-insensitiv), die copyleft/unklare Lizenzen markieren.
_FLAGGED = ("GPL", "AGPL", "LGPL", "UNKNOWN")


def _is_flagged(license_name):
    up = (license_name or "").upper()
    if not up.strip() or up.strip() == "UNKNOWN":
        return True
    return any(tag in up for tag in _FLAGGED)


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not shutil.which("pip-licenses"):
        return common.skipped(GATE, "pip-licenses nicht installiert", common.TOOL_MISSING)

    cmd = ["pip-licenses", "--format=json"]
    try:
        proc = subprocess.run(cmd, cwd=os.path.abspath(target),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "pip-licenses-Lauf fehlgeschlagen: %s" % ex)

    if proc.returncode != 0:
        return common.CheckResult(GATE, common.FAIL, "pip-licenses meldet Fehler (rc=%d)" % proc.returncode)

    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return common.CheckResult(GATE, common.FAIL, "pip-licenses-Ausgabe nicht lesbar")

    findings = []
    for entry in data:
        name = entry.get("Name", "?")
        lic = entry.get("License", "")
        if _is_flagged(lic):
            findings.append(common.Finding(name, 0, "license-copyleft",
                                           "%s -> %s" % (name, lic or "UNKNOWN")))
    if findings:
        return common.CheckResult(GATE, common.WARN,
                                  "%d copyleft/unklare Lizenz(en)" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS,
                              "keine copyleft/unklaren Lizenzen (%d Pakete)" % len(data))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
