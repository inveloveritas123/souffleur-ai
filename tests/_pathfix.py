"""Sys-Path-Bootstrap für `unittest discover` (Gate C2, `gates/checks/c2_coverage.py`).

Gate `C2` führt exakt `coverage run -m unittest discover -s tests -p "test_*.py"`
aus — OHNE vorher `PYTHONPATH` zu setzen und ohne dass `souffleur`
(`apps/backend/src`) oder `coaching_mcp` (`packages/coaching-mcp/src`)
installiert (`pip install -e`) sind. `apps/backend/tests/conftest.py` löst
dasselbe Problem für `pytest` (das `conftest.py` automatisch lädt) — `unittest`
kennt `conftest.py` nicht.

`unittest discover -s tests` (ohne `-t`) macht `tests/` selbst zum
`top_level_dir` und fügt es vorn in `sys.path` ein (verifiziert: Testmodule in
Unterpaketen wie `tests/unit/test_x.py` werden dadurch als `unit.test_x`
importiert, NICHT als `tests.unit.test_x` — `tests/__init__.py` wird in diesem
Discovery-Modus nie importiert). Jedes Testmodul kann daher `_pathfix` als
flaches Top-Level-Modul importieren (liegt direkt in `tests/`, dem
`top_level_dir`) — unabhängig davon, ob es selbst flach unter `tests/` oder in
einem Unterpaket (`tests/unit/`, `tests/e2e/`) liegt.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_SRC = _REPO_ROOT / "apps" / "backend" / "src"
_COACHING_MCP_SRC = _REPO_ROOT / "packages" / "coaching-mcp" / "src"


def ensure_import_paths() -> None:
    """Bringt `souffleur` und `coaching_mcp` auf `sys.path` — idempotent, ohne Duplikate."""
    for extra_path in (_BACKEND_SRC, _COACHING_MCP_SRC):
        extra_path_str = str(extra_path)
        if extra_path_str not in sys.path:
            sys.path.insert(0, extra_path_str)


ensure_import_paths()
