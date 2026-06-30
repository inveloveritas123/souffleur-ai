"""Gates K1/K2 — Branchenregeln (branchenspezifische Pflichten je Domaene).

Konzept (analog DSGVO): WERKBANK ERZWINGT, dass die branchenspezifischen Pflicht-Artefakte da
sind (K1) und dass die fachliche Abnahme durch einen Menschen vorliegt (K2). Die fachliche
SUBSTANZ (ist die HOAI-Berechnung/MaRisk-Abbildung korrekt?) liefert der Domaenen-Experte — wie
die materielle DSGVO-Wuerdigung der DSB. So sind kritische Branchenregeln auditierbar verankert,
ohne dass WERKBANK Fachrecht halluziniert.

Die aktive Branche kommt aus `--branch <name>` oder `<target>/.werkbank/branch.txt`.
Das Regelpaket liegt in `branch-modules/<name>/rules.yaml`:
  name: finanzen
  desc: "Finanzdienstleistung — BaFin/Audit-Trail"
  required_artefacts: [AUDIT-TRAIL.md, AUFBEWAHRUNG.md, MARISK-MAPPING.md]
  required_signoff: fachaufsicht     # Abschnitt in docs/produktivfreigabe/FREIGABE.yaml

Keine Branche aktiv -> SKIP/NOT_APPLICABLE (unter einem Branchen-Profil => UNGEDECKT => ROT).
"""
import os

try:
    from . import common, freigabe
except ImportError:
    import common  # type: ignore
    import freigabe  # type: ignore

BRANCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "branch-modules")


def _resolve_branch(target, branch):
    if branch:
        return branch
    p = os.path.join(target, ".werkbank", "branch.txt")
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    return ln
    except OSError:
        pass
    return None


def _load_rules(branch):
    p = os.path.join(BRANCH_DIR, branch, "rules.yaml")
    if not os.path.isfile(p):
        return None
    rules = {"name": branch, "desc": "", "required_artefacts": [], "required_signoff": ""}
    with open(p, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#") or ":" not in s:
                continue
            k, v = s.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "desc":
                rules["desc"] = v.strip('"').strip("'")
            elif k == "required_signoff":
                rules["required_signoff"] = v.strip('"').strip("'")
            elif k == "required_artefacts":
                v = v.strip("[]")
                rules["required_artefacts"] = [x.strip().strip('"').strip("'") for x in v.split(",") if x.strip()]
    return rules


def run_k1(target, exclude_dirs=None, exclude_abs=None, branch=None, **_):
    b = _resolve_branch(target, branch)
    if not b:
        return common.skipped("K1", "keine Branche aktiviert (--branch / .werkbank/branch.txt)",
                              common.NOT_APPLICABLE)
    rules = _load_rules(b)
    if rules is None:
        return common.CheckResult("K1", common.FAIL,
                                  "Branche '%s' ohne Regelpaket (branch-modules/%s/rules.yaml)" % (b, b))
    req = rules["required_artefacts"]
    if not req:
        return common.skipped("K1", "Branche '%s' ohne Pflicht-Artefakte" % b, common.NOT_APPLICABLE)
    present = {os.path.basename(rel) for _ap, rel in
               common.iter_files(target, exclude_dirs=exclude_dirs, exclude_abs=exclude_abs)}
    missing = [a for a in req if a not in present]
    if missing:
        findings = [common.Finding("branche:%s" % b, 0, "missing-artefakt", a) for a in missing]
        return common.CheckResult("K1", common.FAIL,
                                  "%d Branchen-Pflicht-Artefakt(e) fehlen (%s)" % (len(missing), b), findings)
    return common.CheckResult("K1", common.PASS, "Branchen-Pflicht-Artefakte vollstaendig (%s)" % b)


def run_k2(target, branch=None, **_):
    b = _resolve_branch(target, branch)
    if not b:
        return common.skipped("K2", "keine Branche aktiviert", common.NOT_APPLICABLE)
    rules = _load_rules(b)
    if rules is None or not rules["required_signoff"]:
        return common.skipped("K2", "Branche '%s' ohne Fachabnahme-Pflicht" % b, common.NOT_APPLICABLE)
    return freigabe._check(target, "K2", rules["required_signoff"], "Branchen-Fachabnahme (%s)" % b)
