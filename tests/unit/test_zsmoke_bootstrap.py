"""Smoke-Test: `_pathfix` macht `souffleur`/`coaching_mcp` unter `unittest discover` importierbar."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()


class BootstrapSmokeTest(unittest.TestCase):
    def test_souffleur_importable(self) -> None:
        from souffleur.core.settings import MODEL_REASONING

        self.assertEqual(MODEL_REASONING, "magistral-medium-2509")

    def test_coaching_mcp_importable(self) -> None:
        import coaching_mcp

        self.assertIsNotNone(coaching_mcp)


if __name__ == "__main__":
    unittest.main()
