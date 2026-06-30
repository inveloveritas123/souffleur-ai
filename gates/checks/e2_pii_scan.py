"""Gate E2 — PII-Scan in Logs/Prompts/Outputs (deterministisch, kein LLM).

Scope (bewusst eng = Intent des Gates): Log-/Prompt-/Output-Artefakte. Konfig/Doku
mit legitimen Kontakt-Mails (z. B. DSB) werden nicht geflaggt.
Hochpraezise Muster: E-Mail, Telefon (intl inkl. (0) + DE-National), IBAN (beliebiges Land,
mod-97), Kreditkarte (Luhn), Namen (nach Anrede/Grußformel/Selbstnennung).
Defense-in-Depth: E2 ist absichtlich BREITER als ein einzelner Redactor (GP04) -> faengt PII,
die ein Redactor evtl. uebersieht.
"""
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E2"

NAME_SUFFIXES = (".log", ".out", ".prompt")
PATH_CONTAINS = ("logs/", "log/", "prompts/", "prompt/", "outputs/", "output/")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Telefon: international (+49/0049) UND deutsche Nationalformate (0151…, 0351-…).
# National verlangt einen Trenner nach der Vorwahl -> reine Ziffernläufe (IBAN-Fragment,
# Zeitstempel, status=200) lösen nicht aus.
PHONE_PATTERNS = [
    ("phone-intl",     re.compile(r"(?:\+49|0049)[\s\-/]?(?:\(0\))?[\s\-/]?\(?\d{2,5}\)?[\s\-/]?\d{3,}(?:[\s\-/]?\d{2,})?")),
    ("phone-national", re.compile(r"(?<![\d/])0\d{1,4}[\s/\-]\d{3,}(?:[\s/\-]?\d{2,})?\b")),
]
IBAN_CAND_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b")
CC_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")

_NAME = r"([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)"
NAME_PATTERNS = [
    re.compile(r"(?:Herr|Frau|Dr\.?|Hr\.?|Fr\.?)\s+" + _NAME),
    re.compile(r"(?:Mit freundlichen|Viele|Beste|Mit besten|Herzliche|Freundliche)\s+"
               r"Gr[üu]e?(?:ß|ss)e[n]?[,\s]+" + _NAME),
    re.compile(r"(?:Mein Name ist|Ich heiße|Ich heisse|Ansprechpartner(?:in)?:?|Unterschrift:?)\s+" + _NAME),
]


def _luhn_ok(digits: str) -> bool:
    s, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


def _iban_ok(raw: str) -> bool:
    s = re.sub(r"\s", "", raw).upper()
    if not (15 <= len(s) <= 34) or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    rearr = s[4:] + s[:4]
    num = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearr)
    try:
        return int(num) % 97 == 1
    except ValueError:
        return False


def _scan_line(line):
    out = []
    for m in EMAIL_RE.finditer(line):
        out.append(("email", m.group(0)))
    phone_spans = []
    for kind, pat in PHONE_PATTERNS:
        for m in pat.finditer(line):
            if any(m.start() < e and m.end() > s for s, e in phone_spans):
                continue  # ueberlappt bereits gefundene Nummer (z. B. 0049 von beiden Mustern)
            phone_spans.append((m.start(), m.end()))
            out.append((kind, m.group(0)))
    for m in IBAN_CAND_RE.finditer(line):
        if _iban_ok(m.group(0)):
            out.append(("iban", m.group(0)))
    for m in CC_RE.finditer(line):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 16 and _luhn_ok(digits):
            out.append(("credit-card", m.group(0)))
    for pat in NAME_PATTERNS:
        for m in pat.finditer(line):
            out.append(("name", m.group(1)))
    return out


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings = []
    for ap, rel in common.iter_files(target, name_suffixes=NAME_SUFFIXES,
                                     path_contains=PATH_CONTAINS,
                                     exclude_dirs=exclude_dirs,
                                     exclude_abs=exclude_abs):
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            for kind, raw in _scan_line(line):
                findings.append(common.Finding(rel, i, "pii:" + kind, common.redact(raw)))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d Klartext-PII in Logs/Prompts/Outputs" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "keine Klartext-PII in Logs/Prompts/Outputs")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status == common.PASS else 1)
