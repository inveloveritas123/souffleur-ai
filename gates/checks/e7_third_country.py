"""Gate E7 — Drittlandübermittlung (Kap. V, Art. 44 ff.). Deterministisch.

Liest `THIRD-COUNTRY-TRANSFERS.md`. Findet eine Übermittlung außerhalb der EU/EWR statt (`ja`),
MUSS eine Garantie dokumentiert sein (Angemessenheitsbeschluss / SCC / BCR). „nein" -> PASS.
SKIP ohne Kontext/Artefakt. (In gates.yaml als warn geführt — FAIL blockt nicht, beratend.)
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "E7"
_TRANSFER_YES = re.compile(r"(?i)(?:statt\??|außerhalb der EU[^\n]*?)[:\s]*\bja\b")
_SAFEGUARD = re.compile(r"(?i)\bSCC\b|Standardvertragsklausel|Angemessenheitsbeschluss|\bBCR\b|"
                        r"verbindliche interne Datenschutzvorschriften")


def run(target, exclude_dirs=None, exclude_abs=None, privacy_dir=None, **_):
    if not privacy_dir:
        return common.skipped(GATE, "kein Privacy-Kontext (nicht anwendbar)", common.NOT_APPLICABLE)
    f = os.path.join(privacy_dir, "THIRD-COUNTRY-TRANSFERS.md")
    if not os.path.isfile(f):
        return common.skipped(GATE, "kein Drittland-Artefakt vorhanden", common.NOT_APPLICABLE)
    with open(f, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not _TRANSFER_YES.search(text):
        return common.CheckResult(GATE, common.PASS, "keine Drittlandübermittlung (EU/EWR-only)")
    if _SAFEGUARD.search(text):
        return common.CheckResult(GATE, common.PASS, "Drittlandübermittlung mit dokumentierter Garantie (Kap. V)")
    return common.CheckResult(GATE, common.FAIL, "Drittlandübermittlung ohne dokumentierte Garantie (Kap. V)",
                              [common.Finding("THIRD-COUNTRY-TRANSFERS.md", 0, "no-safeguard",
                                              "SCC/Angemessenheitsbeschluss/BCR fehlt")])


if __name__ == "__main__":
    pd = sys.argv[1] if len(sys.argv) > 1 else None
    res = run(pd or ".", privacy_dir=pd)
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
