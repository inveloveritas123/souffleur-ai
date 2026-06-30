"""Gate F3 — Golden-Output-Snapshot-Stabilitaet (WARN-Gate, deterministisch).

Sucht ein Snapshot-Verzeichnis (`__snapshots__/`, `snapshots/` oder `golden/`) unter target.
- keines vorhanden        -> SKIP/NOT_APPLICABLE.
- vorhanden mit >=1 Datei -> PASS ("N Golden-Snapshot(s) vorhanden").
- vorhanden, aber leer    -> WARN ("Snapshot-Verzeichnis leer").

WARN-Gate: es gibt KEIN FAIL.
"""
import os
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "F3"
SNAPSHOT_DIRNAMES = ("__snapshots__", "snapshots", "golden")


def _find_snapshot_dirs(target, exclude_dirs):
    exclude = exclude_dirs or common.DEFAULT_EXCLUDE_DIRS
    target = os.path.abspath(target)
    found = []
    for root, dirs, _files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in exclude]
        for d in dirs:
            if d in SNAPSHOT_DIRNAMES:
                found.append(os.path.join(root, d))
    return found


def _count_files(snapshot_dir):
    total = 0
    for _root, _dirs, files in os.walk(snapshot_dir):
        total += len(files)
    return total


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    snapshot_dirs = _find_snapshot_dirs(target, exclude_dirs)
    if not snapshot_dirs:
        return common.skipped(GATE, "kein Snapshot-Verzeichnis", common.NOT_APPLICABLE)

    total = sum(_count_files(d) for d in snapshot_dirs)
    if total >= 1:
        return common.CheckResult(GATE, common.PASS, "%d Golden-Snapshot(s) vorhanden" % total)
    return common.CheckResult(GATE, common.WARN, "Snapshot-Verzeichnis leer")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
