"""Make the `coaching_mcp` package importable without requiring an editable
install (pip in this environment is too old for PEP 660 editable installs
from a pyproject.toml-only, setuptools-based project — see README.md
"Abweichung vom Auftrag"). The package is still pip-installable normally
(`pip install packages/coaching-mcp`); this conftest only affects test
collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
