"""Gate G1 — Lasttest grün via k6 (deterministisch, kein LLM).

Sucht ein k6-Lasttest-Skript unter target (`*.k6.js`, `loadtest*.js` oder ein `k6/`-Dir).
Ohne Skript -> SKIP/NOT_APPLICABLE (kein Lasttest konfiguriert). Skript vorhanden, aber
k6 fehlt -> SKIP/TOOL_MISSING (kein Vortäuschen). Sonst `k6 run --quiet <script>`:
Returncode 0 -> PASS, sonst WARN mit redigiertem Output-Tail.

G1 ist ein WARN-Gate: ein roter Lasttest blockiert nicht (beratend), ist aber ein Hinweis
auf ein Performance-/Kapazitätsproblem.
"""
import os
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "G1"
_SCRIPT_SUFFIXES = (".k6.js",)
_SCRIPT_PREFIX = "loadtest"
_K6_DIR = "k6/"


def _find_script(target, exclude_dirs, exclude_abs):
    for ap, rel in common.iter_files(target, exts={".js"},
                                     exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        name = os.path.basename(rel).lower()
        if name.endswith(_SCRIPT_SUFFIXES) or name.startswith(_SCRIPT_PREFIX) or rel.startswith(_K6_DIR):
            return ap, rel
    return None, None


def _redacted_tail(text, lines=12):
    tail = (text or "").strip().splitlines()[-lines:]
    return "\n".join(common.redact(ln, 64, 0) for ln in tail) if tail else "(keine Ausgabe)"


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    script_abs, script_rel = _find_script(target, exclude_dirs, exclude_abs)
    if not script_abs:
        return common.skipped(GATE, "kein Lasttest konfiguriert", common.NOT_APPLICABLE)
    if shutil.which("k6") is None:
        return common.skipped(GATE, "k6 nicht installiert", common.TOOL_MISSING)
    try:
        proc = subprocess.run(
            ["k6", "run", "--quiet", script_abs],
            cwd=os.path.abspath(target), capture_output=True, text=True, timeout=900)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.WARN, "k6-Lauf nicht möglich: %s" % ex)
    if proc.returncode == 0:
        return common.CheckResult(GATE, common.PASS, "Lasttest grün (k6, %s)" % script_rel)
    out = (proc.stdout or "") + (proc.stderr or "")
    return common.CheckResult(GATE, common.WARN, "Lasttest rot (k6, %s)" % script_rel,
                              [common.Finding(script_rel, 0, "loadtest-failure", _redacted_tail(out))])


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
