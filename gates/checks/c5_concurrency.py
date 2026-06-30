"""Gate C5 — Concurrency-/Race-Tests grün (deterministisch, kein LLM).

Sucht Nebenläufigkeits-/Race-Tests (test_*concurren*, test_*race*, *_concurrency_test.py)
und führt sie als Subprozess aus (unittest discover, wie C1). PASS bei Returncode 0,
FAIL bei rotem Test, SKIP/NOT_APPLICABLE wenn keine vorhanden. Warn-Gate.
"""
import os
import re
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C5"
_FILE_PATTERNS = (
    re.compile(r"test_.*concurren.*\.py$"),
    re.compile(r"test_.*race.*\.py$"),
    re.compile(r".*_concurrency_test\.py$"),
)


def _find_dirs(target):
    """Liefert {abs_dir: glob_pattern} aller Verzeichnisse mit passenden Test-Dateien."""
    found = {}
    for ap, rel in common.iter_files(target, exts={".py"}):
        name = os.path.basename(rel)
        if any(p.match(name) for p in _FILE_PATTERNS):
            found.setdefault(os.path.dirname(ap), name)
    return found


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    dirs = _find_dirs(target)
    if not dirs:
        return common.skipped(GATE, "keine Concurrency-/Race-Tests", common.NOT_APPLICABLE)
    total = 0
    failures = []
    for d, pattern in sorted(dirs.items()):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", d, "-p", pattern],
                cwd=os.path.abspath(target), capture_output=True, text=True, timeout=600)
        except (subprocess.SubprocessError, OSError) as ex:
            return common.CheckResult(GATE, common.FAIL, "Concurrency-Testlauf nicht möglich: %s" % ex)
        out = (proc.stderr or "") + (proc.stdout or "")
        ran = re.search(r"Ran (\d+) test", out)
        total += int(ran.group(1)) if ran else 0
        if proc.returncode != 0:
            rel = os.path.relpath(d, os.path.abspath(target)).replace(os.sep, "/")
            fails = re.search(r"(FAILED \([^)]*\))", out)
            failures.append(common.Finding(rel, 0, "concurrency-failure",
                                           fails.group(1) if fails else "Tests rot"))
    if total == 0:
        return common.skipped(GATE, "keine Concurrency-/Race-Tests gesammelt", common.NOT_APPLICABLE)
    if failures:
        return common.CheckResult(GATE, common.FAIL,
                                  "Concurrency-Tests rot (%d Tests)" % total, failures)
    return common.CheckResult(GATE, common.PASS, "Concurrency-Tests grün (%d Tests)" % total)


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP, common.WARN) else 1)
