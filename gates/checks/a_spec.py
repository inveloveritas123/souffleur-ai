"""Gate A — Spec-Integrität (deterministisch). Prüft den SPEC (z. B. BMAD-/PRD-Output)
VOR dem Bau. A1 Pflichtfelder vollständig · A2 Akzeptanzkriterien testbar · A3 Handoff erfüllt.
Alle SKIP ohne Spec-Kontext (`spec_file`), damit Läufe ohne SPEC grün bleiben.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

MANDATORY = ["Ziel", "Scope", "Datenarten", "Akzeptanz", "Nicht-Ziele", "Handoff"]
_PLACEHOLDER = re.compile(r"<[^>\n]{1,80}>|\b(?:TODO|TBD|FIXME)\b")
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _load(spec_file):
    if spec_file and os.path.isfile(spec_file):
        with open(spec_file, encoding="utf-8", errors="replace") as f:
            return f.read()
    return None


def _sections(text):
    out, heads = {}, list(_HEADING.finditer(text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out[m.group(1)] = text[m.end():end].strip()
    return out


def _section_for(secs, keyword):
    for h, body in secs.items():
        if keyword.lower() in h.lower():
            return h, body
    return None, None


def run_a1(target, exclude_dirs=None, exclude_abs=None, spec_file=None, **_):
    text = _load(spec_file)
    if text is None:
        return common.skipped("A1", "kein SPEC (nicht anwendbar)", common.NOT_APPLICABLE)
    secs = _sections(text)
    findings = []
    for kw in MANDATORY:
        h, body = _section_for(secs, kw)
        if h is None:
            findings.append(common.Finding("SPEC.md", 0, "missing-field", "Pflichtfeld fehlt: %s" % kw))
        elif not body.strip():
            findings.append(common.Finding("SPEC.md", 0, "empty-field", "Feld leer: %s" % kw))
        elif _PLACEHOLDER.search(body):
            findings.append(common.Finding("SPEC.md", 0, "placeholder", "Platzhalter in: %s" % kw))
    if findings:
        return common.CheckResult("A1", common.FAIL, "%d Spec-Pflichtfeld-Befund(e)" % len(findings), findings)
    return common.CheckResult("A1", common.PASS, "alle 6 Spec-Pflichtfelder gefüllt")


def run_a2(target, exclude_dirs=None, exclude_abs=None, spec_file=None, **_):
    text = _load(spec_file)
    if text is None:
        return common.skipped("A2", "kein SPEC (nicht anwendbar)", common.NOT_APPLICABLE)
    _, body = _section_for(_sections(text), "Akzeptanz")
    if not body:
        return common.CheckResult("A2", common.FAIL, "kein Akzeptanzkriterien-Abschnitt")
    items = []
    for line in body.splitlines():
        m = re.match(r"\s*-\s+(?:\[[ xX]\]\s*)?(.+)$", line)
        if m and len(m.group(1).strip()) >= 8 and not _PLACEHOLDER.search(m.group(1)):
            items.append(m.group(1).strip())
    if len(items) < 2:
        return common.CheckResult("A2", common.FAIL, "Akzeptanzkriterien nicht testbar/zu wenige (%d)" % len(items))
    return common.CheckResult("A2", common.PASS, "%d testbare Akzeptanzkriterien" % len(items))


def run_a3(target, exclude_dirs=None, exclude_abs=None, spec_file=None, **_):
    text = _load(spec_file)
    if text is None:
        return common.skipped("A3", "kein SPEC (nicht anwendbar)", common.NOT_APPLICABLE)
    _, body = _section_for(_sections(text), "Handoff")
    if not body:
        return common.CheckResult("A3", common.FAIL, "kein Handoff-Abschnitt (PM→Architect)")
    if not re.search(r"\[[xX]\]", body):
        return common.CheckResult("A3", common.FAIL, "Handoff-Checkliste nicht erfüllt (kein [x])")
    return common.CheckResult("A3", common.PASS, "Handoff PM→Architect erfüllt")


if __name__ == "__main__":
    sp = sys.argv[1] if len(sys.argv) > 1 else None
    for fn in (run_a1, run_a2, run_a3):
        print("\n".join(fn(".", spec_file=sp).to_report_lines()))
