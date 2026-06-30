"""Gates J1/J2 — Produktivfreigabe (menschliche Abnahme). Deterministisch.

J1 = Security-Abnahme, J2 = Datenschutz-/DSB-Abnahme. Liest docs/produktivfreigabe/FREIGABE.yaml,
das ein MENSCH ausfuellt und signiert — KEIN Self-Sign durch den Agenten. Ohne erteilte Freigabe
kein 'produktiv'-Gruen (Profil `produktiv`). So ist die menschliche Abnahme hart + auditierbar
erzwungen — der Kern der WERKBANK-Nachweisfuehrung.

FREIGABE.yaml (Vorlage: docs/produktivfreigabe/FREIGABE.template.yaml):
  security:
    freigegeben: true
    von: "Max Mustermann (Security Lead)"
    datum: "2026-06-11"
    referenz: "docs/produktivfreigabe/SECURITY-REVIEW.md"
  datenschutz:
    freigegeben: true
    von: "Erika Musterfrau (DSB)"
    datum: "2026-06-11"
    referenz: "docs/produktivfreigabe/DATENSCHUTZ-REVIEW.md"

Fehlt die Datei/der Abschnitt -> SKIP/NOT_APPLICABLE (unter `produktiv` => UNGEDECKT => ROT;
also kein stilles Gruen ohne Abnahme). freigegeben=false -> FAIL. Unvollstaendig (von/datum
fehlt oder Platzhalter) -> FAIL. Vollstaendig erteilt -> PASS.
"""
import os
import re

try:
    from . import common
except ImportError:
    import common  # type: ignore

REL = os.path.join("docs", "produktivfreigabe", "FREIGABE.yaml")
_TRUTHY = {"true", "ja", "yes", "x", "1", "erteilt", "freigegeben"}
_PLACEHOLDER = re.compile(r"<[^>]*>|\bTODO\b|\bTBD\b|…|^_+$", re.I)


def _parse(text):
    """Mini-Parser: Abschnitte (security/datenschutz) auf Spalte 0, Felder eingerueckt."""
    data, cur = {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0 and s.endswith(":"):
            cur = s[:-1].strip().lower()
            data[cur] = {}
            continue
        if cur is not None and ":" in s:
            k, v = s.split(":", 1)
            data[cur][k.strip().lower()] = v.strip().strip('"').strip("'")
    return data


def _truthy(v):
    return str(v).strip().lower() in _TRUTHY


def _missing(v):
    return (not str(v).strip()) or bool(_PLACEHOLDER.search(str(v)))


def _check(target, gate, section, label):
    p = os.path.join(target, REL)
    if not os.path.isfile(p):
        return common.skipped(gate, "keine Produktivfreigabe (%s)" % REL, common.NOT_APPLICABLE)
    with open(p, encoding="utf-8", errors="replace") as f:
        data = _parse(f.read())
    sec = data.get(section)
    if not sec:
        return common.skipped(gate, "FREIGABE.yaml ohne Abschnitt '%s'" % section, common.NOT_APPLICABLE)
    if not _truthy(sec.get("freigegeben", "")):
        return common.CheckResult(gate, common.FAIL, "%s NICHT erteilt" % label)
    von, datum = sec.get("von", ""), sec.get("datum", "")
    if _missing(von) or _missing(datum):
        return common.CheckResult(gate, common.FAIL, "%s unvollstaendig (von/datum fehlt)" % label)
    return common.CheckResult(gate, common.PASS, "%s: %s (%s)" % (label, von, datum))


def run_j1(target, **_):
    return _check(target, "J1", "security", "Security-Abnahme")


def run_j2(target, **_):
    return _check(target, "J2", "datenschutz", "Datenschutz-/DSB-Abnahme")
