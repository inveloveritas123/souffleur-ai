"""Gate C6 — Accessibility (a11y) via axe (deterministisch, kein LLM).

Sucht ein a11y/axe-Setup:
  - "axe-core" in den Dependencies von package.json, ODER
  - ein npm-Skript namens "a11y" / "axe" in package.json, ODER
  - eine a11y-/axe-Konfigurationsdatei (axe.config.*, a11y.config.*, .axerc*).
Ohne Setup -> SKIP/NOT_APPLICABLE. Setup vorhanden, aber npx fehlt -> SKIP/TOOL_MISSING
(kein Vortäuschen). Sonst Lauf des a11y-Skripts (npm run a11y/axe falls definiert, sonst
`npx axe`): Returncode 0 -> PASS, sonst FAIL. Defensiv (Subprozess-Fehler -> FAIL). Warn-Gate.
"""
import json
import os
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "C6"
_CONFIG_NAMES = ("axe.config.js", "axe.config.json", "a11y.config.js", "a11y.config.json",
                 ".axerc", ".axerc.json")
_SCRIPT_NAMES = ("a11y", "axe")


def _load_package_json(target):
    p = os.path.join(target, "package.json")
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f), os.path.relpath(p, target).replace(os.sep, "/")
    except (OSError, json.JSONDecodeError):
        return None, None


def _detect(target):
    """Liefert (command_list, label) oder (None, None) wenn kein a11y-Setup gefunden."""
    pkg, rel = _load_package_json(target)
    if pkg is not None:
        scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
        for name in _SCRIPT_NAMES:
            if name in scripts:
                return ["npm", "run", name], "%s (script:%s)" % (rel, name)
        deps = {}
        for key in ("dependencies", "devDependencies"):
            d = pkg.get(key)
            if isinstance(d, dict):
                deps.update(d)
        if "axe-core" in deps or "@axe-core/cli" in deps:
            return ["npx", "axe"], "%s (axe-core)" % rel
    for _ap, frel in common.iter_files(target):
        if os.path.basename(frel) in _CONFIG_NAMES:
            return ["npx", "axe"], frel
    return None, None


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    cmd, label = _detect(target)
    if cmd is None:
        return common.skipped(GATE, "kein a11y/axe-Setup", common.NOT_APPLICABLE)
    if shutil.which("npx") is None:
        return common.skipped(GATE, "npx/axe nicht installiert", common.TOOL_MISSING)
    try:
        proc = subprocess.run(
            cmd, cwd=os.path.abspath(target), capture_output=True, text=True, timeout=900)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(GATE, common.FAIL, "a11y-Lauf nicht möglich: %s" % ex)
    if proc.returncode == 0:
        return common.CheckResult(GATE, common.PASS, "a11y grün (%s)" % label)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = out.strip().splitlines()[-8:]
    evidence = " | ".join(common.redact(ln, 64, 0) for ln in tail) if tail else "(keine Ausgabe)"
    return common.CheckResult(GATE, common.FAIL, "a11y-Verstöße (%s)" % label,
                              [common.Finding(label, 0, "a11y-failure", evidence)])


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP, common.WARN) else 1)
