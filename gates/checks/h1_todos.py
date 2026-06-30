"""Gate H1 — TODO/FIXME ohne Ticket-Referenz (deterministisch, kein LLM).

Scannt Code-Dateien (.py/.js/.ts/.go/.java) nach Markern TODO/FIXME/XXX/HACK.
Ein Befund = solcher Marker OHNE Ticket-Referenz in der Naehe (akzeptiert `#123`,
`GH-123`, `JIRA-123`, `(#123)`, eine URL).

H1 ist ein WARN-Gate: offene, nicht-getrackte TODOs blockieren nicht, sind aber
ein Hinweis (technische Schuld ohne Nachverfolgbarkeit).
- Marker ohne Ticket -> WARN (mit redigierten Fundstellen).
- alle Marker getrackt / keine Marker -> PASS.
- kein Code-File -> SKIP/NOT_APPLICABLE.
"""
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "H1"
CODE_EXTS = {".py", ".js", ".ts", ".go", ".java"}

# Marker als Wortgrenze (kein Treffer in z. B. "XXXL" oder "fixme_table").
_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
# Ticket-Referenz: #123 / (#123) / GH-123 / JIRA-123 (Projektkuerzel-Zahl) / URL.
_TICKET_RE = re.compile(r"#\d+|\b[A-Z][A-Z0-9]+-\d+\b|https?://\S+")


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings, n = [], 0
    for ap, rel in common.iter_files(target, exts=CODE_EXTS,
                                     exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        n += 1
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            if _MARKER_RE.search(line) and not _TICKET_RE.search(line):
                findings.append(common.Finding(rel, i, "todo-no-ticket",
                                               common.redact(line, 32, 0)))
    if n == 0:
        return common.skipped(GATE, "kein Code-File (.py/.js/.ts/.go/.java)", common.NOT_APPLICABLE)
    if findings:
        return common.CheckResult(GATE, common.WARN,
                                  "%d TODO/FIXME ohne Ticket-Referenz" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "alle TODO/FIXME getrackt (oder keine)")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
