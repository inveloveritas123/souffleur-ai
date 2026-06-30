"""Gate H4 — CHANGELOG-Eintrag vorhanden (append, newest-top). Deterministisch.

FAIL: keine CHANGELOG.md, kein Eintrag, oder datierte Einträge nicht newest-top sortiert.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "H4"
_DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})", re.M)
_ANY_HEADING = re.compile(r"^##\s+\S", re.M)


def run(target, **_):
    p = os.path.join(target, "CHANGELOG.md")
    if not os.path.isfile(p):
        return common.CheckResult(GATE, common.FAIL, "CHANGELOG.md fehlt")
    with open(p, encoding="utf-8", errors="replace") as f:
        text = f.read()
    dates = _DATE_HEADING.findall(text)
    if not dates:
        if _ANY_HEADING.search(text):
            return common.CheckResult(GATE, common.PASS, "CHANGELOG vorhanden (ohne Datums-Header)")
        return common.CheckResult(GATE, common.FAIL, "kein CHANGELOG-Eintrag (## …)")
    if any(dates[i] < dates[i + 1] for i in range(len(dates) - 1)):
        return common.CheckResult(GATE, common.FAIL, "Einträge nicht newest-top sortiert",
                                  [common.Finding("CHANGELOG.md", 0, "order", "älterer Eintrag über neuerem")])
    return common.CheckResult(GATE, common.PASS, "CHANGELOG vorhanden, %d Einträge, newest-top" % len(dates))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status == common.PASS else 1)
