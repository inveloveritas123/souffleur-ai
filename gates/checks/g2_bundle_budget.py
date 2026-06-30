"""Gate G2 — Ressourcen-/Bundle-Budget (deterministisch, kein LLM).

Sucht ein Build-Output-Verzeichnis (`dist/` oder `build/`) unter target. Ohne solches
Verzeichnis -> SKIP/NOT_APPLICABLE (kein Build-Output). Sonst wird die Gesamtgröße aller
Dateien darin in KB gegen das Budget `G2_MAX_KB` (Default 5000) verglichen:
über Budget -> WARN (mit Fundstelle), innerhalb -> PASS.

G2 ist ein WARN-Gate: ein zu großes Bundle blockiert nicht (beratend), ist aber ein
Hinweis auf ein Performance-/Ladezeit-Problem.
"""
import os
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "G2"
_BUILD_DIRS = ("dist", "build")
_DEFAULT_MAX_KB = 5000


def _find_build_dir(target):
    for name in _BUILD_DIRS:
        p = os.path.join(target, name)
        if os.path.isdir(p):
            return p, name
    return None, None


def _dir_size_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            ap = os.path.join(root, f)
            try:
                total += os.path.getsize(ap)
            except OSError:
                continue
    return total


def _budget_kb():
    raw = os.environ.get("G2_MAX_KB")
    if raw is None:
        return _DEFAULT_MAX_KB
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_MAX_KB


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    build_abs, build_rel = _find_build_dir(target)
    if not build_abs:
        return common.skipped(GATE, "kein Build-Output (dist/ oder build/)", common.NOT_APPLICABLE)
    max_kb = _budget_kb()
    size_kb = _dir_size_bytes(build_abs) // 1024
    if size_kb > max_kb:
        return common.CheckResult(
            GATE, common.WARN, "%s über Budget (%d KB > %d KB)" % (build_rel, size_kb, max_kb),
            [common.Finding(build_rel, 0, "bundle-budget", "%s %d KB > %d KB" % (build_rel, size_kb, max_kb))])
    return common.CheckResult(GATE, common.PASS, "%s im Budget (%d KB ≤ %d KB)" % (build_rel, size_kb, max_kb))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
