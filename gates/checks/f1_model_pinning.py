"""Gate F1 — Modell-Pinning (kein 'latest'). Deterministisch.

FAIL, wenn ein Modell-Wert auf das bewegliche Tag statt auf eine gepinnte Version/ein Tier-Alias
verweist (Zuweisung an einen Modell-Schluessel, deren Wert auf dieses Tag endet). Scope:
Code/Config (keine Markdown-Doku). Hinweis: das Trigger-Wort steht hier bewusst nicht als
Beispiel-Literal, damit das Gate seine eigene Doku nicht flaggt.
"""
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "F1"
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".sh"}
NAME_SUFFIXES = (".env",)

PATTERNS = [
    ("model-kv-latest", re.compile(r"(?i)\bmodel[\w]*['\"]?\s*[:=]\s*['\"]?[^'\"\n,}]*\blatest\b")),
    ("model-tag-latest", re.compile(r"(?i)\b(?:claude|gpt|gemini|llama|mistral|sonnet|opus|haiku)[\w.\-]*[:\-]latest\b")),
]


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings = []
    for ap, rel in common.iter_files(target, exts=CODE_EXTS, name_suffixes=NAME_SUFFIXES,
                                     exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            for kind, pat in PATTERNS:
                m = pat.search(line)
                if m:
                    findings.append(common.Finding(rel, i, "unpinned:" + kind, common.redact(m.group(0), 12, 0)))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d ungepinnte(s) Modell ('latest')" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "kein 'latest' — Modelle gepinnt")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status == common.PASS else 1)
