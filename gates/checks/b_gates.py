"""Gates B — statisch. B1 Lint (ruff), B2 Typecheck (mypy), B3 Build (py_compile, stdlib).

B3 ist immer real (kompiliert alle .py). B1/B2 nutzen externe Tools, sonst SKIP (kein Vortäuschen).
"""
import os
import py_compile
import shutil
import subprocess
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore


def run_b3(target, exclude_dirs=None, exclude_abs=None, **_):
    findings, n = [], 0
    for ap, rel in common.iter_files(target, exts={".py"}, exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        n += 1
        try:
            py_compile.compile(ap, doraise=True)
        except py_compile.PyCompileError as ex:
            findings.append(common.Finding(rel, 0, "syntax-error", str(ex).splitlines()[-1][:80]))
        except OSError:
            continue
    if n == 0:
        return common.skipped("B3", "kein Python-Code", common.NOT_APPLICABLE)
    if findings:
        return common.CheckResult("B3", common.FAIL, "%d Datei(en) kompilieren nicht" % len(findings), findings)
    return common.CheckResult("B3", common.PASS, "Build/Compile sauber (%d .py)" % n)


def _tool_gate(gate, tool, args, target):
    if not shutil.which(tool):
        return common.skipped(gate, "%s nicht installiert" % tool, common.TOOL_MISSING)
    try:
        proc = subprocess.run([tool] + args, cwd=os.path.abspath(target),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as ex:
        return common.CheckResult(gate, common.FAIL, "%s-Lauf fehlgeschlagen: %s" % (tool, ex))
    if proc.returncode == 0:
        return common.CheckResult(gate, common.PASS, "%s sauber" % tool)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    return common.CheckResult(gate, common.FAIL, "%s meldet Befunde: %s" % (tool, tail[0][:80]))


def run_b1(target, exclude_dirs=None, exclude_abs=None, **_):
    return _tool_gate("B1", "ruff", ["check", "."], target)


def run_b2(target, exclude_dirs=None, exclude_abs=None, **_):
    return _tool_gate("B2", "mypy", ["."], target)


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "."
    for fn in (run_b1, run_b2, run_b3):
        print("\n".join(fn(t).to_report_lines()))
