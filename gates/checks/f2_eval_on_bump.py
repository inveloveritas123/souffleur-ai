"""Gate F2 — Eval-on-Bump (Evidenz-basiert, deterministisch).

Regel: Wer ein LLM-Modell pinnt, muss eine Regressions-Eval-Baseline mitfuehren — sonst
laesst sich ein Modellwechsel nicht gegen Qualitaetsregressionen absichern.

- Kein Modell-Bezug in Config -> SKIP/NOT_APPLICABLE ("kein Modell gepinnt").
- Modell-Bezug + Eval-Evidenz (evals/ ODER .werkbank/eval-baseline.json ODER
  evals/baseline.json, jeweils nicht leer) -> PASS.
- Modell-Bezug, aber KEINE Eval-Evidenz -> FAIL.
"""
import os
import re
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "F2"
CONFIG_EXTS = {".yaml", ".yml", ".json", ".toml"}
NAME_SUFFIXES = (".env",)

MODEL_PATTERNS = [
    re.compile(r"(?i)\bclaude-"),
    re.compile(r"(?i)\bgpt-"),
    re.compile(r"(?i)\bmodel_id\s*[:=]"),
    re.compile(r"(?i)\bmodel\s*[:=]"),
]


def _has_model_reference(target, exclude_dirs, exclude_abs):
    for ap, _rel in common.iter_files(target, exts=CONFIG_EXTS, name_suffixes=NAME_SUFFIXES,
                                      exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for line in lines:
            if any(pat.search(line) for pat in MODEL_PATTERNS):
                return True
    return False


def _non_empty_dir(path):
    return os.path.isdir(path) and bool(os.listdir(path))


def _non_empty_file(path):
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _has_eval_evidence(target):
    target = os.path.abspath(target)
    if _non_empty_dir(os.path.join(target, "evals")):
        return True
    if _non_empty_file(os.path.join(target, ".werkbank", "eval-baseline.json")):
        return True
    if _non_empty_file(os.path.join(target, "evals", "baseline.json")):
        return True
    return False


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    if not _has_model_reference(target, exclude_dirs, exclude_abs):
        return common.skipped(GATE, "kein Modell gepinnt", common.NOT_APPLICABLE)
    if _has_eval_evidence(target):
        return common.CheckResult(GATE, common.PASS, "Regressions-Eval-Baseline vorhanden")
    return common.CheckResult(
        GATE, common.FAIL,
        "Modell gepinnt, aber kein Regressions-Eval (Eval-on-Bump) hinterlegt")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0 if res.status in (common.PASS, common.SKIP) else 1)
