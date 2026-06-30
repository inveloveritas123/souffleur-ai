"""Gate C1 — Unit-Tests grün (deterministisch, kein LLM).

Führt die Test-Suite des Ziels als Subprozess aus (unittest discover). PASS bei Returncode 0,
FAIL bei rotem Test, SKIP wenn kein Testverzeichnis gefunden. Schließt die Lücke
„Tests existieren, aber kein Gate führt sie aus".

Rekursion: ruft ein Test selbst den Runner auf einem Ziel OHNE Testverzeichnis auf, liefert C1
dort SKIP — die Tests dieses Repos zielen nie auf ein Suite-Verzeichnis, daher keine Endlosschleife.
"""
import os
import re
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C1"
TEST_DIRS = ("gates/checks/tests", "tests", "test")


def _find_testdir(target):
    for cand in TEST_DIRS:
        d = os.path.join(target, cand)
        if os.path.isdir(d):
            return d, cand
    return None, None


def run(target, **_):
    testdir, rel = _find_testdir(target)
    if not testdir:
        return common.skipped(GATE, "kein Testverzeichnis gefunden", common.NOT_APPLICABLE)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", os.path.abspath(testdir), "-p", "test_*.py"],
            cwd=os.path.abspath(target), capture_output=True, text=True, timeout=600)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "Testlauf nicht möglich: %s" % ex)
    out = (proc.stderr or "") + (proc.stdout or "")
    ran = re.search(r"Ran (\d+) test", out)
    n = ran.group(1) if ran else "?"
    if proc.returncode == 0:
        return common.CheckResult(GATE, common.PASS, "Tests grün (%s Tests in %s)" % (n, rel))
    fails = re.search(r"(FAILED \([^)]*\))", out)
    summary = fails.group(1) if fails else "Tests rot"
    return common.CheckResult(GATE, common.FAIL, "%s — %s Tests in %s" % (summary, n, rel),
                              [common.Finding(rel, 0, "test-failure", summary)])


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
