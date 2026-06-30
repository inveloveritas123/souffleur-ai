"""Gate D3 — Secret-Scan (deterministisch, kein LLM).

Kern: stdlib-Regex-Scanner (respektiert Ausschluesse, deterministisch, dependency-frei).
Optional: gitleaks (falls auf PATH) als zusaetzliche Recall-Quelle; Funde werden vereinigt.
Report enthaelt NIE den Klartext-Wert (Redaction) — Selbstkonsistenz mit dem Gate.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "D3"

# Spezifische, hochpraezise Secret-Muster.
SPECIFIC = [
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("gh-token",          re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("google-api-key",    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack-token",       re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("private-key",       re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
]

# Generisch: keyword = <hochentropischer Wert>. Env-Variablennamen werden ausgenommen.
GENERIC = re.compile(
    r"(?i)(?:secret|token|api[_-]?key|access[_-]?key|client[_-]?secret|password|passwd)"
    r"\s*[:=]\s*[\"']?([A-Za-z0-9/+=_\-]{16,})[\"']?"
)
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")   # z. B. PRIMARY_API_KEY -> Referenz, kein Wert


def _scan_builtin(target, exclude_dirs, exclude_abs):
    findings = []
    for ap, rel in common.iter_files(target, exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            for kind, pat in SPECIFIC:
                m = pat.search(line)
                if m:
                    findings.append(common.Finding(rel, i, kind, common.redact(m.group(0))))
            gm = GENERIC.search(line)
            if gm and not ENV_NAME.match(gm.group(1)):
                findings.append(common.Finding(rel, i, "generic-secret", common.redact(gm.group(1))))
    return findings


def _scan_gitleaks(target, exclude_dirs, exclude_abs=None):
    """Optionaler zweiter Scanner. Schlaegt fehl-leise (nur additiv).

    gitleaks crawlt das Dateisystem selbst und kennt unsere Excludes nicht — daher
    filtern wir seine Funde nachtraeglich nach denselben ausgeschlossenen Verzeichnissen
    (sonst werden gitignorte/vendored Dirs wie _bmad/ mitgescannt).
    """
    if not shutil.which("gitleaks"):
        return []
    excl = exclude_dirs or common.DEFAULT_EXCLUDE_DIRS
    abs_prefixes = {os.path.abspath(p) for p in (exclude_abs or set())}
    findings = []
    with tempfile.TemporaryDirectory() as td:
        rep = os.path.join(td, "gl.json")
        try:
            subprocess.run(
                ["gitleaks", "detect", "--no-git", "--redact",
                 "--source", os.path.abspath(target),
                 "--report-format", "json", "--report-path", rep],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
            )
            if os.path.exists(rep):
                with open(rep, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data or []:
                    rel = os.path.relpath(item.get("File", "?"), os.path.abspath(target))
                    abs_file = os.path.abspath(os.path.join(os.path.abspath(target), rel))
                    rel = rel.replace(os.sep, "/")
                    if any(seg in excl for seg in rel.split("/")):
                        continue   # ausgeschlossenes Verzeichnis
                    if any(abs_file == p or abs_file.startswith(p + os.sep) for p in abs_prefixes):
                        continue   # Gate-Tooling-Signaturen (Self-Lauf)
                    findings.append(common.Finding(
                        rel, int(item.get("StartLine", 0)),
                        "gitleaks:" + str(item.get("RuleID", "rule")),
                        common.redact(str(item.get("Secret", "")) or "(redacted)")))
        except (subprocess.SubprocessError, ValueError, OSError):
            return []
    return findings


def _dedup(findings):
    seen, out = set(), []
    for f in findings:
        key = (f.file, f.line, f.kind)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings = _dedup(_scan_builtin(target, exclude_dirs, exclude_abs)
                      + _scan_gitleaks(target, exclude_dirs, exclude_abs))
    if findings:
        return common.CheckResult(GATE, common.FAIL,
                                  "%d potentielle(s) Secret(s) im Diff/Tree" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "kein Secret gefunden")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status == common.PASS else 1)
