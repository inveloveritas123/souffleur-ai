"""Gate D1 — SAST (statische Sicherheitsanalyse) via bandit, ohne High/Medium-Befunde.

Deterministisch: ruft `bandit -r <target> -f json`. Bewertet nach Severity.
- High oder Medium Severity  -> FAIL (mit redigierten Fundstellen).
- nur Low                    -> WARN-artig, hier PASS mit Hinweis (Low ist beraten, nicht blockend).
- bandit nicht installiert   -> SKIP/TOOL_MISSING (kein Vortaeuschen).
- kein Python-Code           -> SKIP/NOT_APPLICABLE.

Kein Klartext im Report: Fundstelle = Datei:Zeile + Test-ID, kein Code-Snippet.
"""
import json
import os
import shutil
import subprocess

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "D1"
_BLOCK_SEVERITIES = {"HIGH", "MEDIUM"}


def _has_python(target, exclude_dirs, exclude_abs):
    for _ap, _rel in common.iter_files(target, exts={".py"},
                                       exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        return True
    return False


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not _has_python(target, exclude_dirs, exclude_abs):
        return common.skipped(GATE, "kein Python-Code", common.NOT_APPLICABLE)
    if not shutil.which("bandit"):
        return common.skipped(GATE, "bandit nicht installiert", common.TOOL_MISSING)

    # exclude_dirs = Namen (z. B. node_modules); exclude_abs = absolute Pfade, die beim
    # Self-Lauf uebersprungen werden (Gate-Tooling/Test-Fixtures — ein Scanner flaggt nicht
    # seine eigenen, absichtlich "unsicheren" Test-Fixtures). bandit -x nimmt beides.
    excludes = sorted(exclude_dirs or common.DEFAULT_EXCLUDE_DIRS)
    excludes += [os.path.abspath(p) for p in (exclude_abs or set())]
    cmd = ["bandit", "-q", "-r", os.path.abspath(target), "-f", "json",
           "-x", ",".join(excludes)]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "bandit-Lauf fehlgeschlagen: %s" % ex)

    # bandit kann eine Fortschrittszeile vor das JSON auf stdout schreiben -> ab dem
    # ersten '{' parsen (robust gegen Progress-Ausgabe).
    raw = proc.stdout or ""
    brace = raw.find("{")
    try:
        data = json.loads(raw[brace:] if brace >= 0 else "{}")
    except json.JSONDecodeError:
        return common.CheckResult(GATE, common.FAIL, "bandit-Ausgabe nicht lesbar")

    blocking, low = [], 0
    for r in data.get("results", []):
        sev = (r.get("issue_severity") or "").upper()
        rel = os.path.relpath(r.get("filename", "?"), os.path.abspath(target))
        if sev in _BLOCK_SEVERITIES:
            blocking.append(common.Finding(rel.replace(os.sep, "/"), int(r.get("line_number", 0)),
                                           "sast:%s/%s" % (sev.lower(), r.get("test_id", "?")),
                                           common.redact(r.get("test_name", ""), 24, 0)))
        elif sev == "LOW":
            low += 1

    if blocking:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d High/Medium-SAST-Befund(e)" % len(blocking), blocking)
    if low:
        return common.CheckResult(GATE, common.PASS, "kein High/Medium (%d Low, beraten)" % low)
    return common.CheckResult(GATE, common.PASS, "kein SAST-Befund (bandit)")
