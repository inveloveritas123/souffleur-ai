"""Gate G3 — N+1 / Query-in-Loop-Heuristik (deterministisch, kein LLM).

Scannt .py-Dateien via stdlib `ast`. Geflaggt wird ein DB-/Query-Aufruf (Call, dessen
func ein Attribut-Name aus `_QUERY_NAMES` ist, z. B. `.execute()`, `.filter()`, `.all()`)
der INNERHALB des Bodys einer `for`-/`while`-Schleife steht — ein klassisches N+1-Muster
(eine Query pro Iteration statt eines Bulk-Zugriffs). Aufrufe in einer im Schleifenkörper
verschachtelten Funktionsdefinition werden NICHT gezählt (die läuft nicht je Iteration).

G3 ist ein WARN-Gate: ein Treffer blockiert nicht (Heuristik, beratend), ist aber ein
Hinweis auf ein potenzielles Performance-Problem.
- Treffer -> WARN (mit Fundstellen).
- keine Treffer -> PASS.
- kein .py-File -> SKIP/NOT_APPLICABLE.
"""
import ast
import sys

try:
    from . import common
except ImportError:
    import common  # type: ignore

GATE = "G3"
_QUERY_NAMES = {"execute", "query", "filter", "get", "all", "fetchone", "fetchall", "find", "aggregate"}
_LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)
_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _query_calls_in_body(nodes):
    """Yield Query-Call-Nodes in `nodes` (Schleifenkörper), ohne in verschachtelte
    Funktionsdefinitionen abzusteigen (die laufen nicht je Iteration)."""
    for node in nodes:
        yield from _walk_skip_funcs(node)


def _walk_skip_funcs(node):
    if isinstance(node, _FUNC_TYPES):
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _QUERY_NAMES:
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_skip_funcs(child)


def _scan_source(src):
    """Liefert Liste (lineno, snippet) der N+1-Verdachts-Aufrufe in `src`."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    hits = []
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, _LOOP_TYPES):
            continue
        for call in _query_calls_in_body(node.body):
            if id(call) in seen:
                continue
            seen.add(id(call))
            hits.append((call.lineno, _snippet(call)))
    hits.sort()
    return hits


def _snippet(call):
    attr = call.func.attr if isinstance(call.func, ast.Attribute) else "?"
    try:
        return ast.unparse(call.func)
    except (AttributeError, ValueError):
        return ".%s()" % attr


def run(target, exclude_dirs=None, exclude_abs=None, **_):
    findings, n = [], 0
    for ap, rel in common.iter_files(target, exts={".py"},
                                     exclude_dirs=exclude_dirs, exclude_abs=exclude_abs):
        n += 1
        lines = common.read_lines(ap)
        if lines is None:
            continue
        for lineno, snippet in _scan_source("".join(lines)):
            findings.append(common.Finding(rel, lineno, "n+1-query", common.redact(snippet, 48, 0)))
    if n == 0:
        return common.skipped(GATE, "kein Python-Code", common.NOT_APPLICABLE)
    if findings:
        return common.CheckResult(GATE, common.WARN,
                                  "%d Query-in-Loop-Verdacht (N+1)" % len(findings), findings)
    return common.CheckResult(GATE, common.PASS, "kein N+1-Verdacht (Query-in-Loop)")


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(res.to_report_lines()))
    sys.exit(0)
