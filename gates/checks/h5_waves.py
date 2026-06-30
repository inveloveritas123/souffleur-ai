"""Gate H5 — Wellen sind self-contained. Deterministisch.

Doktrin (docs/DOKTRIN-Self-Contained-Wellen.md): jede OFFENE Welle in TASKS.md traegt
inline ALLES, was ein frisch gestarteter Worker (Ralph-Loop, frischer Kontext je Runde)
oder ein Resume nach Kompaktierung braucht — ohne nachzulesen:
    - Dateien:    welche Pfade angefasst werden duerfen
    - Verbote:    was NICHT angefasst werden darf
    - Smoke:      der exakte Verifikationsbefehl
    - Akzeptanz:  das Orakel (wann ist die Welle fertig)

FAIL: eine offene Welle, der eines dieser Pflichtfelder fehlt oder das nur ein
      Platzhalter (<...>, TODO, TBD, …) ist.
SKIP (NOT_APPLICABLE): keine TASKS.md, oder keine `### Welle ...`-Bloecke (Projekt nutzt
      die self-contained Form (noch) nicht).
"""
import os
import re

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "H5"
REQUIRED_FIELDS = ("Dateien", "Verbote", "Smoke", "Akzeptanz")

_WAVE_HEADING = re.compile(r"^###\s+(.*\S)\s*$", re.M)
_DONE_MARK = re.compile(r"\[(x|erledigt|done)\]", re.I)
_FIELD = re.compile(r"^\s*[-*]\s*(%s)\s*:\s*(.*)$" % "|".join(REQUIRED_FIELDS), re.I)
_PLACEHOLDER = re.compile(r"<[^>]*>|\bTODO\b|\bTBD\b|…|^_{2,}$", re.I)


def _split_waves(text):
    """Liefert [(titel, blocktext), ...] je `### ...`-Heading bis zum naechsten Heading."""
    waves, cur_title, cur_lines = [], None, []
    for line in text.splitlines():
        m = _WAVE_HEADING.match(line)
        if m:
            if cur_title is not None:
                waves.append((cur_title, "\n".join(cur_lines)))
            cur_title, cur_lines = m.group(1), []
        elif cur_title is not None:
            # naechste Top-Level-Ueberschrift beendet den Wellenbereich
            if re.match(r"^#{1,2}\s+\S", line):
                waves.append((cur_title, "\n".join(cur_lines)))
                cur_title, cur_lines = None, []
            else:
                cur_lines.append(line)
    if cur_title is not None:
        waves.append((cur_title, "\n".join(cur_lines)))
    return waves


def _missing_fields(block):
    found = {}
    for line in block.splitlines():
        m = _FIELD.match(line)
        if m:
            found[m.group(1).capitalize()] = m.group(2).strip()
    missing = []
    for field in REQUIRED_FIELDS:
        val = found.get(field)
        if not val or _PLACEHOLDER.search(val):
            missing.append(field)
    return missing


def run(target, **_):
    p = os.path.join(target, "TASKS.md")
    if not os.path.isfile(p):
        return common.skipped(GATE, "keine TASKS.md (nicht anwendbar)", common.NOT_APPLICABLE)
    with open(p, encoding="utf-8", errors="replace") as f:
        text = f.read()
    waves = _split_waves(text)
    if not waves:
        return common.skipped(GATE, "keine self-contained Wellen (### Welle ...) deklariert",
                              common.NOT_APPLICABLE)

    findings, n_open = [], 0
    for title, block in waves:
        if _DONE_MARK.search(title):
            continue                      # erledigte Welle: nicht mehr relevant
        n_open += 1
        for field in _missing_fields(block):
            findings.append(common.Finding("TASKS.md", 0, "wave-incomplete",
                                           "Welle '%s': Feld '%s' fehlt/Platzhalter" % (title[:40], field)))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d offene Welle(n) nicht self-contained" % len({f.evidence.split(":")[0] for f in findings}),
                                  findings)
    return common.CheckResult(GATE, common.PASS,
                              "%d offene Welle(n) self-contained (Dateien/Verbote/Smoke/Akzeptanz)" % n_open)


if __name__ == "__main__":
    import sys
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
