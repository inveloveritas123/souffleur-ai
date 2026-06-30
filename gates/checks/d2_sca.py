"""Gate D2 — SCA (Software Composition Analysis) via `pip-audit` (optional, kein Fake).

Sucht bekannte Schwachstellen in den deklarierten Dependencies.
- `pip-audit` vorhanden  -> `pip-audit -f json` (cwd=target), JSON parsen.
- sonst `safety` vorhanden -> `safety check --json` als Fallback.
- keines installiert     -> SKIP/TOOL_MISSING (kein Vortaeuschen eines Pass).
- kein Dependency-Manifest (requirements*.txt/pyproject.toml/package.json) -> SKIP/NOT_APPLICABLE.

Bei Befunden: FAIL mit Anzahl + redigierten Paketnamen — KEIN Roh-Advisory-Text im Report.
Robust gegen eine Fortschrittszeile vor dem JSON (ab erstem '{' bzw. '[' parsen).
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

GATE = "D2"


def _has_manifest(target):
    target = os.path.abspath(target)
    for name in os.listdir(target) if os.path.isdir(target) else []:
        low = name.lower()
        if low == "pyproject.toml" or low == "package.json":
            return True
        if low.startswith("requirements") and low.endswith(".txt"):
            return True
    return False


def _slice_json(raw):
    """Schneidet ab dem ersten '{' oder '[' — toleriert eine Progress-Zeile davor."""
    raw = raw or ""
    starts = [i for i in (raw.find("{"), raw.find("[")) if i >= 0]
    if not starts:
        return ""
    return raw[min(starts):]


def _count_pip_audit(data):
    """pip-audit -f json: {"dependencies": [{"name", "vulns": [...]}, ...]} (neueres Format)
    oder eine Liste von {"name", "vulns": [...]} (aelteres Format). Liefert Paketnamen mit Vulns."""
    vuln_pkgs = []
    deps = data.get("dependencies", data) if isinstance(data, dict) else data
    for entry in deps or []:
        if not isinstance(entry, dict):
            continue
        vulns = entry.get("vulns") or []
        if vulns:
            vuln_pkgs.append(entry.get("name", "?"))
    return vuln_pkgs


def _count_safety(data):
    """safety check --json: liefert eine Liste von Eintraegen; Paketname an Position 0
    (aelteres Format) bzw. unter 'package_name' (neueres Format)."""
    vuln_pkgs = []
    entries = data.get("vulnerabilities", data) if isinstance(data, dict) else data
    for entry in entries or []:
        if isinstance(entry, dict):
            vuln_pkgs.append(entry.get("package_name") or entry.get("package") or "?")
        elif isinstance(entry, (list, tuple)) and entry:
            vuln_pkgs.append(entry[0])
    return vuln_pkgs


def _run_tool(cmd, target):
    try:
        proc = subprocess.run(cmd, cwd=os.path.abspath(target),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as ex:
        return None, "%s-Lauf fehlgeschlagen: %s" % (cmd[0], ex)
    try:
        return json.loads(_slice_json(proc.stdout) or "null"), None
    except json.JSONDecodeError:
        return None, "%s-Ausgabe nicht lesbar" % cmd[0]


def _findings(vuln_pkgs):
    return [common.Finding("(dependencies)", 0, "sca:vuln", common.redact(str(p), 12, 0))
            for p in vuln_pkgs]


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not _has_manifest(target):
        return common.skipped(GATE, "kein Dependency-Manifest", common.NOT_APPLICABLE)

    if shutil.which("pip-audit"):
        data, err = _run_tool(["pip-audit", "-f", "json"], target)
        if err:
            return common.CheckResult(GATE, common.FAIL, err)
        vuln_pkgs = _count_pip_audit(data)
        tool = "pip-audit"
    elif shutil.which("safety"):
        data, err = _run_tool(["safety", "check", "--json"], target)
        if err:
            return common.CheckResult(GATE, common.FAIL, err)
        vuln_pkgs = _count_safety(data)
        tool = "safety"
    else:
        return common.skipped(GATE, "pip-audit/safety nicht installiert", common.TOOL_MISSING)

    if vuln_pkgs:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d verwundbare(s) Paket(e) (%s)" % (len(vuln_pkgs), tool),
                                  _findings(vuln_pkgs))
    return common.CheckResult(GATE, common.PASS, "keine bekannten Schwachstellen (%s)" % tool)


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
