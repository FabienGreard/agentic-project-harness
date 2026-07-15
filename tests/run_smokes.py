#!/usr/bin/env python3
"""Run the deterministic Baton source-distribution smoke suite."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True


def main() -> int:
    tests = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
