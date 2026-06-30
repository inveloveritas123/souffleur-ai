"""Gate E6 — DSFA-Erzwingung (Art. 35). Deterministisch.

Liest `DPIA-SCREENING.md` aus dem privacy_dir. Ergibt das Screening **hohes Risiko**
(angekreuzter Indikator `[x]` oder Tabellenzelle `ja`), MUSS `DPIA.md` vorhanden und gefüllt sein.
Kein hohes Risiko -> PASS (dokumentierte Verneinung). SKIP ohne Kontext/Screening.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E6"
_CHECKED = re.compile(r"-\s*\[[xX]\]")
_TABLE_JA = re.compile(r"\|\s*ja\s*\|", re.I)
_PLACEHOLDER = re.compile(r"<[^>\n]{1,80}>|\b(?:TODO|TBD|FIXME)\b|…|\.\.\.")


def _high_risk(text):
    return bool(_CHECKED.search(text) or _TABLE_JA.search(text))


def run(target, exclude_dirs=None, exclude_abs=None, privacy_dir=None, **_):
    if not privacy_dir:
        return common.skipped(GATE, "kein Privacy-Kontext (nicht anwendbar)", common.NOT_APPLICABLE)
    screening = os.path.join(privacy_dir, "DPIA-SCREENING.md")
    if not os.path.isfile(screening):
        return common.skipped(GATE, "kein DPIA-Screening vorhanden", common.NOT_APPLICABLE)
    with open(screening, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not _high_risk(text):
        return common.CheckResult(GATE, common.PASS, "Screening: kein hohes Risiko — keine DSFA erforderlich")
    dpia = os.path.join(privacy_dir, "DPIA.md")
    if not os.path.isfile(dpia):
        return common.CheckResult(GATE, common.FAIL, "hohes Risiko, aber DPIA.md fehlt (Art. 35)",
                                  [common.Finding("DPIA.md", 0, "missing", "DSFA bei hohem Risiko Pflicht")])
    with open(dpia, encoding="utf-8", errors="replace") as f:
        body = f.read()
    if not body.strip() or _PLACEHOLDER.search(body):
        return common.CheckResult(GATE, common.FAIL, "DPIA.md unvollständig (leer/Platzhalter)",
                                  [common.Finding("DPIA.md", 0, "incomplete", "DSFA nicht ausgefüllt")])
    return common.CheckResult(GATE, common.PASS, "hohes Risiko — DPIA.md vorhanden und gefüllt")


if __name__ == "__main__":
    pd = sys.argv[1] if len(sys.argv) > 1 else None
    res = run(pd or ".", privacy_dir=pd)
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
