"""Gate E8 — Datenminimierung (Art. 25), deterministischer Dokumentations-Check.

Prüft, ob in den Privacy-Artefakten (a) Datenminimierung DOKUMENTIERT ist und (b) bei besonderen
Kategorien (Art. 9) eine DSFA vorliegt. **Nicht** die materielle Angemessenheit — die bleibt
DSB/LLM-Urteil. In gates.yaml als warn geführt (FAIL blockt nicht). SKIP ohne Privacy-Kontext.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E8"
_MINIM = re.compile(r"(?i)datenminimierung|datensparsam|minimal|nur das.{0,20}erforderlich|erforderlich|notwendige")
_ART9 = re.compile(r"(?i)besondere kategorien|art\.?\s*9")
_NEG = re.compile(r"(?i)\b(keine|nein|nicht|kein)\b")


def _art9_present(text):
    for line in text.splitlines():
        if _ART9.search(line) and not _NEG.search(line):
            return True
    return False


def run(target, exclude_dirs=None, exclude_abs=None, privacy_dir=None, **_):
    if not privacy_dir:
        return common.skipped(GATE, "kein Privacy-Kontext (nicht anwendbar)", common.NOT_APPLICABLE)
    parts = []
    for name in sorted(os.listdir(privacy_dir)) if os.path.isdir(privacy_dir) else []:
        if name.lower().endswith(".md"):
            try:
                with open(os.path.join(privacy_dir, name), encoding="utf-8", errors="replace") as f:
                    parts.append(f.read())
            except OSError:
                pass
    if not parts:
        return common.skipped(GATE, "keine Artefakte zum Prüfen", common.NOT_APPLICABLE)
    text = "\n".join(parts)
    findings = []
    if _art9_present(text) and not os.path.isfile(os.path.join(privacy_dir, "DPIA.md")):
        findings.append(common.Finding("DATA-FLOW.md", 0, "art9-no-dpia",
                                       "besondere Kategorien (Art. 9) ohne DSFA-Begründung"))
    if not _MINIM.search(text):
        findings.append(common.Finding("privacy/*", 0, "no-minimization-doc",
                                       "Datenminimierung (Art. 25) nicht dokumentiert"))
    if findings:
        return common.CheckResult(GATE, common.FAIL, "%d Datenminimierungs-Befund(e) (warn)" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "Datenminimierung dokumentiert; Art-9-Disziplin ok")


if __name__ == "__main__":
    pd = sys.argv[1] if len(sys.argv) > 1 else None
    res = run(pd or ".", privacy_dir=pd)
    print("\n".join(res.to_report_lines()))
