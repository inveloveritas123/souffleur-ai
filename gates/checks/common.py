"""Gemeinsame Bausteine fuer deterministische Checks.

Kein externer Dependency (stdlib only). Ergebnis-Typen, Datei-Walk mit sinnvollen
Ausschluessen, und Redaction — damit GATE-REPORT.md NIE Klartext-Secrets/PII enthaelt
(Selbstkonsistenz mit Gate D3/E2).
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

# SKIP-Gruende — unterscheiden, WARUM ein Gate nicht lief. Das entscheidet ueber
# "hartes Gruen": ist ein Gate im Pflichtenheft des Profils gefordert, darf es NICHT
# stillschweigend per SKIP gruen aussehen — egal aus welchem Grund (siehe gates/verdict.py).
NOT_APPLICABLE = "not_applicable"    # Kontext fehlt legitim (kein Privacy-Kontext, kein SPEC)
TOOL_MISSING = "tool_missing"        # Pflicht-Tool nicht installiert (ruff/mypy/coverage/bandit)
NOT_IMPLEMENTED = "not_implemented"  # Gate deklariert, aber (noch) kein Checker hinterlegt

# Menschlich lesbare Kurztexte fuer den Report.
SKIP_REASON_LABEL = {
    NOT_APPLICABLE: "nicht anwendbar (Kontext fehlt)",
    TOOL_MISSING: "Pflicht-Tool nicht installiert",
    NOT_IMPLEMENTED: "kein Check implementiert",
}

# Verzeichnisse, die Checks nie scannen (Build-/Vendor-/State-Artefakte).
DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".werkbank",
    "_bmad", "_bmad-output", ".claude",
}


def redact(value: str, keep_head: int = 4, keep_tail: int = 2) -> str:
    """Maskiert die Mitte eines sensiblen Strings: 'AKIA…MN' statt Klartext."""
    value = value.replace("\n", " ").strip()
    if len(value) <= keep_head + keep_tail:
        return "*" * len(value)
    return "%s…%s" % (value[:keep_head], value[-keep_tail:])


@dataclass
class Finding:
    file: str          # Pfad relativ zum Scan-Ziel
    line: int
    kind: str          # z. B. "aws-access-key", "email", "non-eu-endpoint"
    evidence: str      # bereits redigiert (nie Klartext-Secret/PII)


@dataclass
class CheckResult:
    gate: str                       # z. B. "E1"
    status: str                     # PASS | FAIL | WARN | SKIP
    summary: str = ""
    findings: List[Finding] = field(default_factory=list)
    skip_reason: Optional[str] = None  # nur bei status==SKIP gesetzt (NOT_APPLICABLE|TOOL_MISSING|NOT_IMPLEMENTED)

    def to_report_lines(self) -> List[str]:
        lines = ["- **%s** — %s — %s" % (self.gate, self.status, self.summary)]
        for f in self.findings:
            lines.append("    - `%s:%d` [%s] %s" % (f.file, f.line, f.kind, f.evidence))
        return lines


def skipped(gate: str, summary: str, reason: str = NOT_APPLICABLE) -> "CheckResult":
    """Konstruiert ein SKIP-Ergebnis MIT Grund. Checks sollen das statt eines nackten
    CheckResult(..., SKIP, ...) nutzen, damit das Pflichtenheft den Grund auswerten kann."""
    return CheckResult(gate, SKIP, summary, skip_reason=reason)


def iter_files(target: str,
               exts: Optional[set] = None,
               name_suffixes: Optional[tuple] = None,
               path_contains: Optional[tuple] = None,
               exclude_dirs: Optional[set] = None,
               exclude_abs: Optional[set] = None):
    """Liefert (abs_path, rel_path) je Datei unter target.

    exts:           nur Dateien mit dieser Endung (z. B. {'.py','.yaml'})
    name_suffixes:  ODER: Dateiname endet auf einem dieser Suffixe (z. B. ('.log',))
    path_contains:  ODER: relativer Pfad enthaelt eines dieser Segmente (z. B. ('logs/',))
    exclude_abs:    absolute Pfad-Praefixe, die ganz uebersprungen werden (z. B. die
                    Gate-Tooling-Signaturdateien beim Self-Lauf — ein Scanner flaggt
                    nicht seine eigene Signaturliste).
    Wenn exts/name_suffixes/path_contains alle None -> alle Dateien.
    """
    exclude = (exclude_dirs or DEFAULT_EXCLUDE_DIRS)
    abs_prefixes = {os.path.abspath(p) for p in (exclude_abs or set())}
    target = os.path.abspath(target)
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in exclude]
        if abs_prefixes and any(os.path.abspath(root) == p or os.path.abspath(root).startswith(p + os.sep)
                                for p in abs_prefixes):
            dirs[:] = []
            continue
        for name in files:
            ap = os.path.join(root, name)
            rel = os.path.relpath(ap, target)
            rel_posix = rel.replace(os.sep, "/")
            if exts is None and name_suffixes is None and path_contains is None:
                yield ap, rel_posix
                continue
            ext_ok = exts is not None and os.path.splitext(name)[1].lower() in exts
            suf_ok = name_suffixes is not None and name.lower().endswith(name_suffixes)
            path_ok = path_contains is not None and any(seg in rel_posix for seg in path_contains)
            if ext_ok or suf_ok or path_ok:
                yield ap, rel_posix


def read_lines(abs_path: str):
    """Robustes Zeilenlesen (Binaerdateien werden uebersprungen)."""
    try:
        with open(abs_path, encoding="utf-8", errors="strict") as f:
            return f.readlines()
    except (UnicodeDecodeError, OSError):
        return None
