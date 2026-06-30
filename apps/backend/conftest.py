"""Pytest-Bootstrap fürs Backend-Package.

Macht `apps/backend/src` importierbar (Package `souffleur`), ohne dass das Projekt
installiert (`pip install -e`) werden muss. Pytest lädt conftest.py automatisch für
jede Ancestor-Directory der gesammelten Testdateien — dadurch funktioniert
`python3 -m pytest apps/backend/tests/...` aus dem Repo-Root ohne weitere Schritte.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
