"""Gate E5 — DSGVO-Artefakt-Vollstaendigkeit (deterministisch, kein LLM).

Prueft, ob die Soll-Artefakte vorhanden, gefuellt und platzhalterfrei sind und keine
Non-EU-Region referenzieren. NUR anwendbar, wenn ein Privacy-Kontext (privacy_dir)
gesetzt ist — sonst SKIP (nicht anwendbar). So bleibt ein Lauf ohne DSGVO-Projekt gruen.
"""
import os
import re
import sys

try:
    from . import common, e1_eu_routing
except ImportError:
    import common  # type: ignore
    import e1_eu_routing  # type: ignore

GATE = "E5"

# Soll-Artefakte (GATE-REPORT.md ist Output des Laufs -> nicht Vorbedingung).
REQUIRED_DEFAULT = [
    "DATA-FLOW.md",
    "PROCESSING-REGISTER.md",
    "LAWFUL-BASIS.md",
    "DPIA-SCREENING.md",
    "TOMs.md",
    "PROCESSORS-SUBPROCESSORS.md",
    "RETENTION-DELETION.md",
]

# Platzhalter, die "nicht ausgefuellt" bedeuten.
# angle-placeholder verlangt einen Buchstaben im Innern und schliesst '@' (Mail-Autolinks)
# sowie reine Pfeile (<->) aus -> kein False Positive auf legitime Inhalte.
PLACEHOLDER_PATTERNS = [
    ("angle-placeholder", re.compile(r"<(?=[^>\n]*[A-Za-zÄÖÜäöüß])[^>@\n]{1,60}>")),
    ("bracket-fill",      re.compile(r"(?i)\[[^\]\n]*(?:\.\.\.|…|bitte|ausf[üu]e?llen|einsetzen|"
                                     r"tbd|todo|platzhalter|hier\s|name\b)[^\]\n]*\]")),
    ("ellipsis",          re.compile(r"…")),
    ("triple-dot",        re.compile(r"(?<!\d)\.\.\.(?!\d)")),
    ("empty-checkbox",    re.compile(r"\[\s\]")),               # offener Status [ ]
    ("underscore-blank",  re.compile(r"_{3,}")),               # z. B. ____ als Leerfeld
    ("todo-marker",       re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b")),
]

# Prosa-Marker fuer Non-EU (ergaenzend zu den Endpoint-Mustern aus E1, die strukturierte
# Region-Codes erwarten). Faengt Klartext-Drittlandbezuege in den Artefakten.
NON_EU_PROSE = [
    ("usa",            re.compile(r"\bUSA\b")),
    ("united-states",  re.compile(r"\bUnited States\b", re.I)),
    ("bare-us-region", re.compile(r"\bus-(?:east|west|central)\b", re.I)),
    ("china",          re.compile(r"\bChina\b")),
    ("drittland-ja",   re.compile(r"(?i)drittland\w*\s*[:=]?\s*ja\b")),
]


def _placeholders_in(text):
    hits = []
    for ln, line in enumerate(text.splitlines(), 1):
        for kind, pat in PLACEHOLDER_PATTERNS:
            if pat.search(line):
                hits.append((ln, kind))
                break
    return hits


def run(target, exclude_dirs=None, exclude_abs=None, privacy_dir=None, required=None, **_):
    if not privacy_dir:
        return common.skipped(GATE, "kein Privacy-Kontext (nicht anwendbar)", common.NOT_APPLICABLE)
    base = privacy_dir
    req = required or REQUIRED_DEFAULT
    findings = []

    for name in req:
        p = os.path.join(base, name)
        if not os.path.isfile(p):
            findings.append(common.Finding(name, 0, "missing", "Soll-Artefakt fehlt"))
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if not text.strip():
            findings.append(common.Finding(name, 0, "empty", "Artefakt leer"))
            continue
        for ln, kind in _placeholders_in(text):
            findings.append(common.Finding(name, ln, "placeholder:" + kind, "unausgefuelltes Feld"))
        # Region=EU: weder strukturierte Endpoint-Marker (E1) noch Prosa-Drittlandbezuege
        for ln, line in enumerate(text.splitlines(), 1):
            for ekind, pat in list(e1_eu_routing.NON_EU_PATTERNS) + NON_EU_PROSE:
                m = pat.search(line)
                if m:
                    findings.append(common.Finding(name, ln, "non-eu-region:" + ekind,
                                                   common.redact(m.group(0), 6, 0)))

    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d Vollstaendigkeits-/Platzhalter-/Region-Befund(e)" % len(findings),
                                  findings)
    return common.CheckResult(GATE, common.PASS,
                              "alle %d Soll-Artefakte vorhanden, gefuellt, platzhalterfrei, EU" % len(req))


if __name__ == "__main__":
    pd = sys.argv[1] if len(sys.argv) > 1 else "."
    res = run(pd, privacy_dir=pd)
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
