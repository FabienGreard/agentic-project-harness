#!/usr/bin/env python3
"""Evaluator regressions for strict mode and bounded cache discovery."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import harness_eval  # noqa: E402


class EvaluatorContractTests(unittest.TestCase):
    def test_documented_strict_mode_is_accepted(self) -> None:
        arguments = harness_eval.parser().parse_args(["--strict"])
        self.assertTrue(arguments.strict)

    def test_cache_check_uses_git_visibility_and_never_scans_vendor_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-evaluator-cache-") as raw:
            fixture = Path(raw).resolve()
            (fixture / ".gitignore").write_text(
                "__pycache__/\n*.pyc\nnode_modules/\nvendor/\n",
                encoding="utf-8",
            )
            checked = fixture / "tools/checked.py"
            checked.parent.mkdir()
            checked.write_text("VALUE = 1\n", encoding="utf-8")
            vendor_cache = fixture / "vendor/dependency/__pycache__"
            vendor_cache.mkdir(parents=True)
            (vendor_cache / "ignored.pyc").write_bytes(b"ignored vendor cache")
            node_cache = fixture / "node_modules/dependency/__pycache__"
            node_cache.mkdir(parents=True)
            (node_cache / "ignored.pyc").write_bytes(b"ignored dependency cache")
            harness_eval.run(fixture, ["git", "init", "-q", "-b", "main"])
            added = harness_eval.run(
                fixture,
                ["git", "add", ".gitignore", "tools/checked.py"],
            )
            self.assertEqual(added.returncode, 0, added.stderr)

            harness_eval.check_python_and_cache_hygiene(fixture)

            source_cache = fixture / "tools/__pycache__"
            source_cache.mkdir(parents=True)
            (source_cache / "harness_eval.cpython-39.pyc").write_bytes(b"source cache")
            with self.assertRaisesRegex(
                harness_eval.EvaluationFailure,
                "tools/__pycache__",
            ):
                harness_eval.check_python_and_cache_hygiene(fixture)
            shutil.rmtree(source_cache)


if __name__ == "__main__":
    unittest.main()
