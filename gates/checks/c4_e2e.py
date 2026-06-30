"""Gate C4 — E2E-Tests grün via Playwright (deterministisch, kein LLM).

Sucht eine Playwright-Konfiguration unter target. Ohne Config -> SKIP/NOT_APPLICABLE
(kein E2E konfiguriert). Config vorhanden, aber npx/playwright fehlt -> SKIP/TOOL_MISSING
(kein Vortäuschen). Sonst `npx playwright test`: Returncode 0 -> PASS, sonst FAIL mit
redigiertem Output-Tail. Block-Gate.
"""
import os
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C4"
_CONFIG_NAMES = ("playwright.config.js", "playwright.config.ts", "playwright.config.mjs")


def _find_config(target):
    for ap, rel in common.iter_files(target):
        if os.path.basename(rel) in _CONFIG_NAMES:
            return ap, rel
    return None, None


def _redacted_tail(text, lines=12):
    tail = (text or "").strip().splitlines()[-lines:]
    return "\n".join(common.redact(ln, 64, 0) for ln in tail) if tail else "(keine Ausgabe)"


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    cfg_abs, cfg_rel = _find_config(target)
    if not cfg_abs:
        return common.skipped(GATE, "kein E2E konfiguriert", common.NOT_APPLICABLE)
    if shutil.which("npx") is None:
        return common.skipped(GATE, "npx/playwright nicht installiert", common.TOOL_MISSING)
    try:
        proc = subprocess.run(
            ["npx", "playwright", "test"],
            cwd=os.path.abspath(target), capture_output=True, text=True, timeout=900)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "Playwright-Lauf nicht möglich: %s" % ex)
    if proc.returncode == 0:
        return common.CheckResult(GATE, common.PASS, "E2E grün (Playwright, %s)" % cfg_rel)
    out = (proc.stdout or "") + (proc.stderr or "")
    return common.CheckResult(GATE, common.FAIL, "E2E rot (Playwright, %s)" % cfg_rel,
                              [common.Finding(cfg_rel, 0, "e2e-failure", _redacted_tail(out))])


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
