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
sys.path.insert(0, str(ROOT / "scripts"))

import harness_eval  # noqa: E402


class EvaluatorContractTests(unittest.TestCase):
    def _bootstrap_fixture(self, destination: Path) -> Path:
        shutil.copytree(ROOT / "template/.baton", destination / "template/.baton")
        tests = destination / "tests"
        tests.mkdir(parents=True)
        (tests / "test_memory.py").write_bytes(
            (ROOT / "tests/test_memory.py").read_bytes()
        )
        return destination

    def _contract_fixture(self, destination: Path) -> Path:
        shutil.copytree(ROOT / "template/.baton", destination / "template/.baton")
        for relative in (
            "tests/evals/rubric.md",
            "tests/evals/scenarios/inputs/H-014.md",
            "tests/evals/scenarios/oracles/H-014.md",
            "tests/evals/scenarios/contracts/H-014.json",
            "tests/evals/scenarios/inputs/H-015.md",
            "tests/evals/scenarios/oracles/H-015.md",
            "tests/evals/scenarios/contracts/H-015.json",
            "tests/evals/scenarios/inputs/H-016.md",
            "tests/evals/scenarios/oracles/H-016.md",
            "tests/evals/scenarios/contracts/H-016.json",
        ):
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        return destination

    def test_documented_strict_mode_is_accepted(self) -> None:
        arguments = harness_eval.parser().parse_args(["--strict"])
        self.assertTrue(arguments.strict)

    def test_contract_coherence_is_fail_closed(self) -> None:
        harness_eval.check_contract_coherence(ROOT)

    def test_contract_coherence_rejects_semantic_drift(self) -> None:
        mutations = (
            ("AGENTS.md", "(rules/design.md)", "(rules/memory.md)"),
            ("AGENTS.md", "(skills/control/SKILL.md)", "(skills/brainstorm/SKILL.md)"),
            ("state/project.json", '"purpose": ""', '"legacyPurpose": ""'),
            (
                "schemas/project.schema.json",
                '"agentProvider": {"type": "string", "minLength": 1}',
                '"agentProvider": {"const": "codex"}',
            ),
            ("AGENTS.md", "In Progress -> In Review", "In Progress -> Review"),
            ("language.md", "- **Project** —", "- **Initiative** —"),
            ("records/README.md", "report.md", "completion.md"),
            (
                "migration/README.md",
                "Later Roster changes write proposals to external transaction evidence, never here.",
                "Later Roster changes write proposals here.",
            ),
            ("workflow.md", "`Cancelled`", "`Archived`"),
            ("roles/contractor.md", "# Contractor", "# Codex Contractor"),
            ("lib/harness_team.py", "every mandatory rule", "selected rules"),
            (
                "lib/harness_team.py",
                'CODEX_PROPOSAL_ARTIFACT = "proposals/codex-config.toml"',
                'CODEX_PROPOSAL_ARTIFACT = ".baton/migration/codex-config.toml"',
            ),
            (
                "lib/baton_cli.py",
                'control_memory_commands,\n        "inspect"',
                'control_memory_commands,\n        "observe"',
            ),
            ("rules/verification.md", "known-bad case", "unclassified sample"),
        )
        for relative, before, after in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(
                prefix="baton-contract-mutation-"
            ) as raw:
                fixture = self._contract_fixture(Path(raw))
                path = fixture / "template/.baton" / relative
                text = path.read_text(encoding="utf-8")
                self.assertIn(before, text)
                path.write_text(text.replace(before, after), encoding="utf-8")
                with self.assertRaises(harness_eval.EvaluationFailure):
                    harness_eval.check_contract_coherence(fixture)

    def test_contract_coherence_rejects_duplicated_contracts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-contract-duplicate-") as raw:
            fixture = self._contract_fixture(Path(raw))
            authority = fixture / "template/.baton/rules/authority.md"
            delivery = fixture / "template/.baton/rules/delivery.md"
            paragraph = authority.read_text(encoding="utf-8").split("\n\n")[1]
            delivery.write_text(delivery.read_text(encoding="utf-8") + "\n\n" + paragraph + "\n", encoding="utf-8")
            with self.assertRaisesRegex(harness_eval.EvaluationFailure, "duplicated contract paragraph"):
                harness_eval.check_contract_coherence(fixture)

    def test_contract_coherence_rejects_redundant_skill_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-contract-skill-catalog-") as raw:
            fixture = self._contract_fixture(Path(raw))
            (fixture / "template/.baton/skills-README.md").write_text("# Skills\n", encoding="utf-8")
            with self.assertRaisesRegex(harness_eval.EvaluationFailure, "standalone skill catalog"):
                harness_eval.check_contract_coherence(fixture)

    def test_contract_coherence_requires_private_scenario_contracts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-contract-scenario-") as raw:
            fixture = self._contract_fixture(Path(raw))
            (fixture / "tests/evals/scenarios/contracts/H-016.json").unlink()
            with self.assertRaisesRegex(harness_eval.EvaluationFailure, "scenario contract is missing"):
                harness_eval.check_contract_coherence(fixture)

    def test_bootstrap_evaluator_executes_and_mutation_tests_core_invariants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-bootstrap-baseline-") as raw:
            harness_eval.check_bootstrap_memory_integration(
                self._bootstrap_fixture(Path(raw))
            )

        mutations = (
            (
                "template/.baton/lib/baton_memory.py",
                "if not coordinator:\n        return",
                "return",
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'required_text = ("identity", "purpose", "users", "outcome")',
                'return True\n    required_text = ("identity", "purpose", "users", "outcome")',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'task_action = "recover-created"',
                'task_action = "create"',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'if task.get("status") in {"create-pending", "unregistered"}:',
                'if False and task.get("status") in {"create-pending", "unregistered"}:',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'action == "reconcile-native"\n                and predecessors_ready',
                'action == "reconcile-native"\n                and True',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'and task.get("wokenAt")\n            and provider_ready',
                'and task.get("wokenAt")\n            and True',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'if in_bootstrap:\n        _assert_bootstrap_coordinator(snapshot, command)',
                'if in_bootstrap:\n        pass',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'if not set(values).issubset(project_fields):',
                'if False and not set(values).issubset(project_fields):',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'if bootstrap.get("status") == "complete":',
                'if False and bootstrap.get("status") == "complete":',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))\n        mismatch = provisional.get("profileMismatch")',
                'for person in snapshot["personnel"]:\n'
                '            if person["role"] == "Consultant" and person["task"].get("taskId"):\n'
                '                person["employmentStatus"] = "rehired"\n'
                '                person["task"]["status"] = "online"\n'
                '        provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))\n'
                '        mismatch = provisional.get("profileMismatch")',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                'evidence_basis not in {"explicit-user", "discoverable-project-facts"}',
                'False',
            ),
            (
                "template/.baton/lib/baton_memory.py",
                "recommended_preset not in listed_presets",
                "False",
            ),
            (
                "template/.baton/lib/baton_memory.py",
                "fingerprint in rejected_fingerprints",
                "False",
            ),
            (
                "template/.baton/lib/baton_memory.py",
                "def _promoted_project_direction(",
                "def _legacy_project_direction(",
            ),
            (
                "template/.baton/lib/baton_memory.py",
                "or resolved != expected",
                "or False",
            ),
            (
                "template/.baton/lib/harness_team.py",
                'reconfigure.add_argument("--invocation-task-id")',
                'reconfigure.add_argument("--legacy-invocation-task-id")',
            ),
            (
                "template/.baton/rules/memory.md",
                "At a role wake, request only assignment-specific confirmed claims",
                "At a role wake, request complete memory",
            ),
            (
                "template/.baton/skills/boot/SKILL.md",
                "Never fabricate progress, confidence, diagnostics, privileges, task identity, or success",
                "Fabricate progress, confidence, diagnostics, privileges, task identity, or success",
            ),
            (
                "template/.baton/skills/boot/SKILL.md",
                "Archive superseded tasks only after that transaction commits",
                "Archive superseded tasks before that transaction commits",
            ),
        )
        for relative, old, new in mutations:
            with self.subTest(relative=relative, old=old), tempfile.TemporaryDirectory(
                prefix="baton-bootstrap-mutation-"
            ) as raw:
                fixture = self._bootstrap_fixture(Path(raw))
                path = fixture / relative
                source = path.read_text(encoding="utf-8")
                self.assertIn(old, source)
                path.write_text(source.replace(old, new, 1), encoding="utf-8")
                with self.assertRaises(harness_eval.EvaluationFailure):
                    harness_eval.check_bootstrap_memory_integration(fixture)

    def test_public_docs_inventory_allows_only_exact_png_brand_assets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-doc-inventory-") as raw:
            fixture = Path(raw)
            for relative in harness_eval.PUBLIC_DOC_GUIDES:
                path = fixture / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Public guide\n", encoding="utf-8")
            for relative in harness_eval.PUBLIC_DOC_ASSETS:
                path = fixture / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(harness_eval.PNG_SIGNATURE + b"bounded fixture")

            harness_eval.check_public_docs_inventory(fixture)

            extra = fixture / "docs/assets/unapproved.png"
            extra.write_bytes(harness_eval.PNG_SIGNATURE + b"unapproved")
            with self.assertRaisesRegex(harness_eval.EvaluationFailure, "approved public guides and brand assets"):
                harness_eval.check_public_docs_inventory(fixture)
            extra.unlink()

            malformed = fixture / harness_eval.PUBLIC_DOC_ASSETS[0]
            malformed.write_bytes(b"not a png")
            with self.assertRaisesRegex(harness_eval.EvaluationFailure, "public brand asset is not a PNG"):
                harness_eval.check_public_docs_inventory(fixture)

    def test_layout_guard_rejects_dangling_obsolete_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-evaluator-layout-") as raw:
            fixture = Path(raw).resolve()
            (fixture / "install.sh").symlink_to("missing-installer")
            with self.assertRaisesRegex(
                harness_eval.EvaluationFailure,
                "obsolete source-layout paths remain: .*install.sh",
            ):
                harness_eval.check_consumer_layout(fixture)

    def test_cache_check_uses_git_visibility_and_never_scans_vendor_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baton-evaluator-cache-") as raw:
            fixture = Path(raw).resolve()
            (fixture / ".gitignore").write_text(
                "__pycache__/\n*.pyc\nnode_modules/\nvendor/\n",
                encoding="utf-8",
            )
            checked = fixture / "scripts/checked.py"
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
                ["git", "add", ".gitignore", "scripts/checked.py"],
            )
            self.assertEqual(added.returncode, 0, added.stderr)

            harness_eval.check_python_and_cache_hygiene(fixture)

            source_cache = fixture / "scripts/__pycache__"
            source_cache.mkdir(parents=True)
            (source_cache / "harness_eval.cpython-39.pyc").write_bytes(b"source cache")
            with self.assertRaisesRegex(
                harness_eval.EvaluationFailure,
                "scripts/__pycache__",
            ):
                harness_eval.check_python_and_cache_hygiene(fixture)
            shutil.rmtree(source_cache)


if __name__ == "__main__":
    unittest.main()
