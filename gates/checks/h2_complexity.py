"""Gate H2 — zyklomatische Komplexitaet je Python-Funktion (stdlib `ast`, kein radon).

Komplexitaet = 1 + Anzahl der Verzweigungspunkte je Funktion:
If, For, While, ExceptHandler, With, BoolOp-Operanden ueber den ersten hinaus,
`if`-Klauseln in Comprehensions, IfExp (ternaer), Assert, sowie Match-Cases (falls
die Laufzeit ast.Match kennt — Python 3.10+).

Schwelle via env `H2_MAX` (Default 12). H2 ist ein WARN-Gate: hohe Komplexitaet
blockiert nicht, ist aber ein Hinweis (Refactoring-Kandidat).
- Funktion ueber Schwelle -> WARN (mit Fundstellen "func() = N").
- kein .py -> SKIP/NOT_APPLICABLE.
"""
import ast
import os
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "H2"
_DEFAULT_MAX = 12


def _max_threshold():
    raw = os.environ.get("H2_MAX")
    if raw is None:
        return _DEFAULT_MAX
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_MAX


def _complexity(func_node):
    """Zaehlt Verzweigungspunkte INNERHALB einer Funktion, ohne in geschachtelte
    Funktionen/Klassen abzusteigen (die werden separat bewertet)."""
    score = 1
    body = list(func_node.body)
    # Decorator-/Argument-Defaults ignorieren; nur der Rumpf zaehlt.
    while body:
        node = body.pop()
        # Geschachtelte Definitionen nicht in DIESE Funktion einrechnen.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not func_node:
            continue
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While,
                             ast.ExceptHandler, ast.With, ast.AsyncWith,
                             ast.IfExp, ast.Assert)):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += len(node.ifs)
        elif hasattr(ast, "Match") and isinstance(node, ast.Match):
            score += len(node.cases)
        for child in ast.iter_child_nodes(node):
            body.append(child)
    return score


def _iter_functions(tree):
    """Liefert alle (Async)FunctionDef-Knoten — auch geschachtelte und Methoden."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    limit = _max_threshold()
    findings, n = [], 0
    for ap, rel in common.iter_files(target, exts={".py"},
                                     exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        n += 1
        try:
            with open(ap, encoding="utf-8", errors="strict") as f:
                tree = ast.parse(f.read(), filename=ap)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for func in _iter_functions(tree):
            score = _complexity(func)
            if score > limit:
                findings.append(common.Finding(rel, getattr(func, "lineno", 0), "complexity",
                                               "%s() = %d" % (func.name, score)))
    if n == 0:
        return common.skipped(GATE, "kein Python-Code", common.NOT_APPLICABLE)
    if findings:
        return common.CheckResult(GATE, common.WARN,
                                  "%d Funktion(en) ueber Komplexitaet %d" % (len(findings), limit),
                                  findings)
    return common.CheckResult(GATE, common.PASS,
                              "alle Funktionen <= Komplexitaet %d (%d .py)" % (limit, n))


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
