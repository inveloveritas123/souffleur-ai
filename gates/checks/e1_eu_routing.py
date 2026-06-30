"""Gate E1 — EU-Routing (deterministisch, kein LLM).

Prinzip: FAIL, wenn in Konfig/Code ein klar NICHT-EU-Endpunkt/Region referenziert wird.
Scope: Konfig- und Code-Dateien (keine Markdown-Doku — die nennt 'us-east' nur als Beispiel).
Allow: eu-* / europe-* werden nicht geflaggt.
"""
import re
import sys

try:
    from . import common
except ImportError:  # direkter Aufruf als Skript
    import common  # type: ignore

GATE = "E1"

CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".yaml", ".yml",
             ".json", ".toml", ".tf", ".sh", ".ini", ".cfg"}
NAME_SUFFIXES = (".env",)  # .env-Dateien haben keine Endung

# Hochpraezise Non-EU-Marker.
NON_EU_PATTERNS = [
    ("aws-us-region",   re.compile(r"\bus-(?:east|west|central|gov-east|gov-west)-\d\b", re.I)),
    ("aws-non-eu",      re.compile(r"\b(?:ap|sa|ca|me|af)-(?:south|east|west|central|southeast|northeast)-\d\b", re.I)),
    ("gcp-non-eu",      re.compile(r"\b(?:us|asia|northamerica|southamerica|australia)-(?:central|east|west|south|northeast|southeast)\d\b", re.I)),
    ("openai-global",   re.compile(r"\bapi\.openai\.com\b", re.I)),
    ("bedrock-non-eu",  re.compile(r"\bbedrock[.-][a-z-]*\b(?:us|ap|sa|ca)-", re.I)),
    ("azure-us-region", re.compile(r"\b(?:eastus|westus|centralus|southcentralus|northcentralus|westcentralus)\d?\b", re.I)),
    ("us-cross-region-model", re.compile(r"\bus\.(?:anthropic|meta|amazon|cohere|mistral|ai21|deepseek)\.", re.I)),
]


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings = []
    for ap, rel in common.iter_files(target, exts=CODE_EXTS,
                                     name_suffixes=NAME_SUFFIXES,
                                     exclude_dirs=exclude_dirs,
                                     exclude_abs=exclude_abs):
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            for kind, pat in NON_EU_PATTERNS:
                m = pat.search(line)
                if m:
                    findings.append(common.Finding(rel, i, "non-eu:" + kind, common.redact(m.group(0), 6, 0)))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d Non-EU-Routing-Referenz(en) gefunden" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "kein Non-EU-Endpunkt/Region referenziert")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status == common.PASS else 1)
