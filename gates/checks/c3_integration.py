"""Gate C3 — Integrationstests grün (deterministisch, kein LLM).

Sucht einen Integrationstest-Ort (tests/integration/, integration/, oder Dateien wie
*_integration_test.py / test_*_integration.py) und führt ihn als Subprozess aus
(unittest discover, wie C1). PASS bei Returncode 0, FAIL bei rotem Test,
SKIP/NOT_APPLICABLE wenn keine Integrationstests existieren. Block-Gate.
"""
import os
import re
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C3"
_INT_DIRS = ("tests/integration", "integration")
_INT_FILE_PATTERNS = (
    re.compile(r".*_integration_test\.py$"),
    re.compile(r"test_.*_integration\.py$"),
)


def _find_integration_dir(target):
    """Liefert (abs_dir, pattern, rel_label) oder (None, None, None).

    Bevorzugt ein dediziertes Verzeichnis; sonst das Verzeichnis, in dem die erste
    passend benannte Integrationstest-Datei liegt (discover sammelt dort per Glob).
    """
    for cand in _INT_DIRS:
        d = os.path.join(target, cand)
        if os.path.isdir(d):
            return os.path.abspath(d), "test_*.py", cand
    for ap, rel in common.iter_files(target, exts={".py"}):
        name = os.path.basename(rel)
        if any(p.match(name) for p in _INT_FILE_PATTERNS):
            d = os.path.dirname(ap)
            return d, name, os.path.dirname(rel) or "."
    return None, None, None


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    intdir, pattern, rel = _find_integration_dir(target)
    if not intdir:
        return common.skipped(GATE, "keine Integrationstests", common.NOT_APPLICABLE)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", intdir, "-p", pattern],
            cwd=os.path.abspath(target), capture_output=True, text=True, timeout=600)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "Integrationstestlauf nicht möglich: %s" % ex)
    out = (proc.stderr or "") + (proc.stdout or "")
    ran = re.search(r"Ran (\d+) test", out)
    n = int(ran.group(1)) if ran else 0
    if n == 0:
        return common.skipped(GATE, "keine Integrationstests gesammelt", common.NOT_APPLICABLE)
    if proc.returncode == 0:
        return common.CheckResult(GATE, common.PASS, "Integrationstests grün (%d in %s)" % (n, rel))
    fails = re.search(r"(FAILED \([^)]*\))", out)
    summary = fails.group(1) if fails else "Integrationstests rot"
    return common.CheckResult(GATE, common.FAIL, "%s — %d Tests in %s" % (summary, n, rel),
                              [common.Finding(rel, 0, "integration-failure", summary)])


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
