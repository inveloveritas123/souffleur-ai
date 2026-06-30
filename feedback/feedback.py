#!/usr/bin/env python3
"""feedback v2 — selbstheilende Rückkopplung: rote Gates -> Backlog / GitHub-Issues.

Adressiert die 3-Experten-Bewertung:
- **Gate-ID-Dedup** (nicht Notiz-Text): eine offene Aufgabe je Gate; Zähler-Änderung erzeugt KEIN Duplikat.
  Eine erledigte `[x]`-Aufgabe wird bei erneutem Fehler wieder geöffnet.
- **Robuste Regex**: mehrstellige Gate-IDs, Notiz ohne Pipe.
- **Egress-Redaction**: `sanitize()` maskiert Secrets/PII/Pfade VOR jedem Ausgang (Backlog & GitHub) —
  Schutz strukturell am Rand, nicht abhängig von der Disziplin künftiger Gate-Summaries.
- **Loop-Closure**: PASS-Gates haken die Backlog-Aufgabe ab / schließen das Issue.
- **gh-Fehler** werden unterschieden (nicht verfügbar) und signalisiert.

Default Dry-Run. CLI:
  feedback.py --report GATE-REPORT.md --backlog BACKLOG.md [--apply] [--gh-issues] [--close-resolved] [--exit-code]
"""
import argparse
import json
import re
import subprocess
import sys

try:
    from datetime import date
    _TODAY = date.today().isoformat()
except Exception:  # pragma: no cover
    _TODAY = ""

LABEL = "werkbank-gate"
SECTION = "## Auto-Findings (Gate-Feedback)"
_GATE = r"[A-Za-z]+\d+"
_ROW_FAIL = re.compile(r"^\|[^|\n]+\|\s*(%s)\s*\|[^|\n]*\|\s*FAIL\s*\|\s*([^|\n]+?)\s*\|?\s*$" % _GATE, re.M)
_ROW_PASS = re.compile(r"^\|[^|\n]+\|\s*(%s)\s*\|[^|\n]*\|\s*PASS\b" % _GATE, re.M)
_OPEN_TASK = re.compile(r"-\s*\[ \]\s*\[(%s)\]" % _GATE)

# Egress-Redaction: maskiert riskante Tokens, bevor sie das System verlassen.
_SANITIZE = [
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),      # E-Mail
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9 ]{10,30}\b"),                      # IBAN-artig
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                   # AWS-Key
    re.compile(r"-----BEGIN[^\n]*KEY-----"),                               # Private Key
    re.compile(r"(?<![\w/])(?:/[\w.\-]+){2,}"),                            # absolute Pfade (>=2 Segmente)
    re.compile(r"\b[\w\-]+\.(?:py|md|json|ya?ml|env|pem|key|log|txt|sh)\b"),  # Dateinamen
    re.compile(r"\b[A-Za-z0-9_\-]{24,}\b"),                                # lange Tokens
]


def sanitize(text):
    out = text or ""
    for pat in _SANITIZE:
        out = pat.sub("[redigiert]", out)
    return out


def parse_failures(report_text):
    out, seen = [], set()
    for m in _ROW_FAIL.finditer(report_text):
        gate, note = m.group(1), m.group(2).strip()
        if gate not in seen:
            seen.add(gate)
            out.append({"gate": gate, "note": note})
    return out


def parse_passes(report_text):
    return sorted({m.group(1) for m in _ROW_PASS.finditer(report_text)})


def _open_gates(text):
    return set(_OPEN_TASK.findall(text or ""))


def plan(failures, existing_text):
    open_now = _open_gates(existing_text)
    return [f for f in failures if f["gate"] not in open_now]


def append_backlog(backlog_path, failures, today=None):
    today = today or _TODAY
    try:
        with open(backlog_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    new = plan(failures, text)
    if not new:
        return 0
    if SECTION not in text:
        text = text.rstrip() + "\n\n" + SECTION + "\n"
    lines = ["- [ ] [%s] %s (%s)" % (f["gate"], sanitize(f["note"]), today) for f in new]
    with open(backlog_path, "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n" + "\n".join(lines) + "\n")
    return len(new)


def close_resolved_backlog(backlog_path, passed_gates):
    try:
        with open(backlog_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return 0
    closed = [0]

    def repl(m):
        if m.group(1) in passed_gates:
            closed[0] += 1
            return m.group(0).replace("[ ]", "[x]", 1)
        return m.group(0)

    text = re.sub(r"-\s*\[ \]\s*\[(%s)\][^\n]*" % _GATE, repl, text)
    if closed[0]:
        with open(backlog_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return closed[0]


def gh_issue_cmd(f):
    note = sanitize(f["note"])
    title = "WERKBANK-Gate %s: %s" % (f["gate"], note[:50])
    body = ("Automatisch aus GATE-REPORT erzeugt (Befunde egress-redigiert).\n\n"
            "Gate: **%s**\nBefund: %s\n\nVerification-first beheben, bis das Gate grün ist." % (f["gate"], note))
    return ["gh", "issue", "create", "--title", title, "--body", body, "--label", LABEL]


def _gh_open_issues():
    """-> (list[{title}], available_bool). available=False, wenn gh fehlt/nicht authentifiziert."""
    try:
        r = subprocess.run(["gh", "issue", "list", "--label", LABEL, "--state", "open",
                            "--json", "title,number", "--limit", "300"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return [], False
        return json.loads(r.stdout or "[]"), True
    except (subprocess.SubprocessError, ValueError, OSError):
        return [], False


def _gate_of_title(title):
    m = re.match(r"WERKBANK-Gate (%s):" % _GATE, title or "")
    return m.group(1) if m else None


def _ensure_label():
    """Legt das Label idempotent an. Ohne existierendes Label scheitert `gh issue create`."""
    try:
        subprocess.run(["gh", "label", "create", LABEL, "--color", "B60205",
                        "--description", "WERKBANK-Gate rot (automatisch)"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (subprocess.SubprocessError, OSError):
        pass


def create_gh_issues(failures, apply=False):
    issues, ok = _gh_open_issues()
    if not ok:
        return {"available": False, "created": [], "error": "gh nicht verfügbar/authentifiziert"}
    if apply:
        _ensure_label()
    open_gates = {_gate_of_title(i.get("title")) for i in issues}
    created, failed = [], []
    for f in failures:
        if f["gate"] in open_gates:
            continue
        if apply:
            try:
                r = subprocess.run(gh_issue_cmd(f), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=60, check=False)
            except (subprocess.SubprocessError, OSError):
                failed.append(f["gate"])
                continue
            if r.returncode != 0:          # nur als erstellt zaehlen, wenn gh wirklich ok war
                failed.append(f["gate"])
                continue
        created.append(f["gate"])
    err = ("gh issue create fehlgeschlagen: %s" % ", ".join(failed)) if failed else None
    return {"available": True, "created": created, "error": err}


def close_gh_issues(passed_gates, apply=False):
    issues, ok = _gh_open_issues()
    if not ok:
        return {"available": False, "closed": []}
    closed = []
    for i in issues:
        g = _gate_of_title(i.get("title"))
        if g in passed_gates:
            if apply:
                try:
                    subprocess.run(["gh", "issue", "close", str(i.get("number"))],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)
                except (subprocess.SubprocessError, OSError):
                    continue
            closed.append(g)
    return {"available": True, "closed": closed}


def main(argv=None):
    ap = argparse.ArgumentParser(description="rote Gates -> Backlog/GH-Issues (selbstheilend)")
    ap.add_argument("--report", required=True)
    ap.add_argument("--backlog", default="BACKLOG.md")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--gh-issues", action="store_true")
    ap.add_argument("--close-resolved", action="store_true", help="PASS-Gates: Backlog abhaken / Issue schließen")
    ap.add_argument("--exit-code", action="store_true", help="Exit 1, wenn neue Befunde angelegt wurden")
    a = ap.parse_args(argv)
    with open(a.report, encoding="utf-8") as fh:
        report = fh.read()
    fails = parse_failures(report)
    passes = parse_passes(report)

    if not a.apply:
        try:
            with open(a.backlog, encoding="utf-8") as fh:
                existing = fh.read()
        except OSError:
            existing = ""
        new = plan(fails, existing)
        print("feedback DRY-RUN: %d neue Befunde (von %d FAIL):" % (len(new), len(fails)))
        for f in new:
            print("  - [ ] [%s] %s" % (f["gate"], sanitize(f["note"])))
        if a.close_resolved:
            print("  würde schließen (PASS): %s" % ", ".join(passes))
        return 0

    n = append_backlog(a.backlog, fails)
    print("feedback: %d Aufgabe(n) angehängt." % n)
    if a.close_resolved:
        c = close_resolved_backlog(a.backlog, passes)
        print("feedback: %d Aufgabe(n) abgehakt (PASS)." % c)
    if a.gh_issues:
        res = create_gh_issues(fails, apply=True)
        if not res["available"]:
            print("feedback: GitHub übersprungen — %s" % res["error"], file=sys.stderr)
        else:
            print("feedback: %d GitHub-Issue(s) erstellt." % len(res["created"]))
            if a.close_resolved:
                cl = close_gh_issues(passes, apply=True)
                print("feedback: %d GitHub-Issue(s) geschlossen." % len(cl["closed"]))
    return 1 if (a.exit_code and n > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
