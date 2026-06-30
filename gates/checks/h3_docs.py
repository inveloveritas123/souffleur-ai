"""Gate H3 — README vorhanden und ausgefuellt (deterministisch).

Prueft am Ziel-Root auf README.md ODER README.rst (case-insensitiv).
H3 ist ein WARN-Gate: fehlende/unfertige Doku blockiert nicht, ist aber ein Hinweis.
WARN, wenn:
- keine README, ODER
- README hat weniger als 10 nicht-leere Zeilen, ODER
- README enthaelt unausgefuellte Platzhalter (`<...>`, `TODO`, `TBD`, `…`).
- sonst PASS.
SKIP/NOT_APPLICABLE nur, wenn das Ziel ueberhaupt keine Dateien hat.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "H3"
_MIN_LINES = 10
_README_NAMES = {"readme.md", "readme.rst"}
# Platzhalter: <…> (Winkelklammern mit Inhalt), TODO/TBD als Wort, oder das Ellipsis-Zeichen.
_PLACEHOLDER_RE = re.compile(r"<[^>\n]+>|\bTODO\b|\bTBD\b|…")


def _find_readme(target):
    try:
        names = os.listdir(target)
    except OSError:
        return None
    for name in names:
        if name.lower() in _README_NAMES and os.path.isfile(os.path.join(target, name)):
            return name
    return None


def _has_any_file(target, exclude_dirs, exclude_abs):
    for _ap, _rel in common.iter_files(target, exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        return True
    return False


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not _has_any_file(target, exclude_dirs, exclude_abs):
        return common.skipped(GATE, "Ziel enthaelt keine Dateien", common.NOT_APPLICABLE)

    name = _find_readme(target)
    if name is None:
        return common.CheckResult(GATE, common.WARN, "keine README (README.md/README.rst)",
                                  [common.Finding("(root)", 0, "docs-missing", "keine README gefunden")])

    lines = common.read_lines(os.path.join(target, name)) or []
    non_empty = [ln for ln in lines if ln.strip()]
    if len(non_empty) < _MIN_LINES:
        return common.CheckResult(GATE, common.WARN,
                                  "README zu kurz (%d/%d nicht-leere Zeilen)" % (len(non_empty), _MIN_LINES),
                                  [common.Finding(name, 0, "docs-thin", "%d nicht-leere Zeilen" % len(non_empty))])

    placeholders = []
    for i, ln in enumerate(lines, 1):
        if _PLACEHOLDER_RE.search(ln):
            placeholders.append(common.Finding(name, i, "docs-placeholder", common.redact(ln, 32, 0)))
    if placeholders:
        return common.CheckResult(GATE, common.WARN,
                                  "README enthaelt %d Platzhalter" % len(placeholders), placeholders)
    return common.CheckResult(GATE, common.PASS, "README vorhanden, %d nicht-leere Zeilen" % len(non_empty))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
