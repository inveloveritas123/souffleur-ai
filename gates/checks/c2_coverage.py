"""Gate C2 — Test-Coverage >= Zielwert. Nutzt coverage.py, sonst SKIP (kein Vortäuschen).

Zielwert via Env C2_MIN (Default 70). SKIP, wenn coverage fehlt oder kein Testverzeichnis da ist.
"""
import os
import re
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C2"
TEST_DIRS = ("gates/checks/tests", "tests", "test")


def _testdir(target):
    for c in TEST_DIRS:
        d = os.path.join(target, c)
        if os.path.isdir(d):
            return os.path.abspath(d)
    return None


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not shutil.which("coverage"):
        return common.skipped(GATE, "coverage nicht installiert", common.TOOL_MISSING)
    td = _testdir(target)
    if not td:
        return common.skipped(GATE, "kein Testverzeichnis", common.NOT_APPLICABLE)
    minimum = int(os.environ.get("C2_MIN", "70"))
    cwd = os.path.abspath(target)
    try:
        subprocess.run(["coverage", "run", "-m", "unittest", "discover", "-s", td, "-p", "test_*.py"],
                       cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        rep = subprocess.run(["coverage", "report"], cwd=cwd,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "coverage-Lauf fehlgeschlagen: %s" % ex)
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", rep.stdout or "")
    if not m:
        return common.CheckResult(GATE, common.SKIP, "coverage-Report nicht lesbar")
    pct = int(m.group(1))
    if pct >= minimum:
        return common.CheckResult(GATE, common.PASS, "Coverage %d%% >= %d%%" % (pct, minimum))
    return common.CheckResult(GATE, common.FAIL, "Coverage %d%% < %d%%" % (pct, minimum))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
