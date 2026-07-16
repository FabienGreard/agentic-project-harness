#!/usr/bin/env python3
"""Public Baton management CLI contract tests."""

from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template/.baton/lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import baton_cli  # noqa: E402
from baton_testkit import baton, build_bundle, install_bundle, json_output, make_candidate, run  # noqa: E402


PUBLIC_COMMANDS = {"boot", "control", "roster", "terminal", "upgrade", "doctor", "scrap"}


class PublicCliTests(unittest.TestCase):
    def test_exact_public_command_families_are_discoverable(self):
        parser = baton_cli.parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(set(subparsers.choices), PUBLIC_COMMANDS)

        output = io.StringIO()
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stdout(output):
            parser.parse_args(["--help"])
        self.assertEqual(caught.exception.code, 0)
        rendered = output.getvalue()
        for command in PUBLIC_COMMANDS:
            self.assertIn(command, rendered)
        self.assertIn("{boot,control,roster,terminal,upgrade,doctor,scrap}", rendered)
        for retired in ("status", "update", "check", "_state", "_team", "_memory", "_activate"):
            self.assertNotIn(f"\n    {retired}", rendered)
        self.assertIn("Inspect and manage this Baton control plane.", rendered)
        self.assertIn("Examples:", rendered)

    def test_leaf_help_explains_inputs_and_shows_copy_ready_examples(self):
        parser = baton_cli.parser()
        cases = (
            (
                ["boot", "record", "--help"],
                ("path to a validated JSON input, or - for stdin", "Examples:"),
            ),
            (
                ["doctor", "recover", "--help"],
                ("Recover fully recognized interrupted team or Memory transactions", "Examples:"),
            ),
            (
                ["scrap", "plan", "--help"],
                ("without changing the Repository", "--output OUTPUT", "Examples:"),
            ),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                output = io.StringIO()
                with self.assertRaises(SystemExit) as caught, contextlib.redirect_stdout(output):
                    parser.parse_args(arguments)
                self.assertEqual(caught.exception.code, 0)
                for value in expected:
                    self.assertIn(value, output.getvalue())

    def test_installer_help_routes_onboarding_to_boot(self):
        rendered = run(["bash", ROOT / "scripts/install.sh", "--help"]).stdout
        self.assertIn("Baton stable installer and updater", rendered)
        self.assertIn("After installation, invoke `$boot`", rendered)
        self.assertIn(".baton/bin/baton boot status --json", rendered)
        self.assertNotIn("`.baton/bin/baton boot`", rendered)

    def test_nested_management_contract_parses(self):
        parser = baton_cli.parser()
        cases = (
            (["boot", "inspect", "--json"], ("command", "boot")),
            (["control", "protocols", "--readiness", "Field Check"], ("control_command", "protocols")),
            (["control", "memory", "inspect", "--json"], ("control_memory_command", "inspect")),
            (["control", "memory", "transact", "operation.json"], ("control_memory_command", "transact")),
            (["roster", "hire", "--consultant", "security-lead", "--yes"], ("roster_command", "hire")),
            (["terminal", "view", "--json"], ("terminal_command", "view")),
            (["upgrade", "apply", "--yes", "--json"], ("upgrade_command", "apply")),
            (["doctor", "recover", "--json"], ("doctor_command", "recover")),
            (["scrap", "plan", "--json"], ("scrap_command", "plan")),
        )
        for arguments, (field, expected) in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(getattr(parser.parse_args(arguments), field), expected)

    def test_cli_reference_has_an_example_for_every_leaf_command(self):
        expected = {
            "boot status",
            "boot inspect",
            "boot initialize",
            "boot record",
            "boot next",
            "boot activate",
            "boot catalog",
            "boot configure",
            "control show",
            "control check",
            "control apply",
            "control protocols",
            "control memory inspect",
            "control memory transact",
            "roster list",
            "roster check",
            "roster catalog",
            "roster hire",
            "roster fire",
            "roster configure",
            "terminal status",
            "terminal view",
            "upgrade status",
            "upgrade apply",
            "doctor check",
            "doctor recover",
            "scrap plan",
            "scrap apply",
        }
        reference = (ROOT / "docs/cli.md").read_text(encoding="utf-8")
        for command in expected:
            with self.subTest(command=command):
                self.assertIn(f".baton/bin/baton {command}", reference)


class PublicCliLifecycleTests(unittest.TestCase):
    def test_public_status_view_and_reviewed_scrap_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="baton-cli-") as raw:
            base = Path(raw).resolve()
            source = make_candidate(base, "7.1.0")
            bundle = base / "bundle"
            build_bundle(source, bundle)
            target = base / "repository"
            target.mkdir()
            state_home = base / "state"
            state_home.mkdir()
            install_bundle(bundle, target, state_home)

            status = json_output(baton(target, ["terminal", "status", "--json"], state_home))
            self.assertEqual(status["installationStatus"], "Installed")
            human_status = baton(target, ["terminal", "status"], state_home).stdout
            self.assertIn("Baton / terminal", human_status)
            self.assertIn("The Baton control plane is ready.", human_status)
            self.assertIn("Next:", human_status)
            human_control = baton(target, ["control", "show"], state_home).stdout
            self.assertIn("Baton / control", human_control)
            self.assertIn("Project controls loaded.", human_control)
            human_doctor = baton(target, ["doctor", "check"], state_home).stdout
            self.assertIn("Baton / doctor", human_doctor)
            self.assertIn("Baton installation, State, roster, and Memory are healthy.", human_doctor)
            memory = json_output(
                baton(
                    target,
                    ["control", "memory", "inspect", "--section", "summary", "--json"],
                    state_home,
                )
            )
            self.assertTrue(memory["filtered"])
            self.assertEqual(memory["section"], "summary")
            view = json_output(baton(target, ["terminal", "view", "--json"], state_home))
            self.assertTrue(Path(view["path"]).is_file())

            plan_path = base / "scrap-plan.json"
            plan = json_output(
                baton(
                    target,
                    ["scrap", "plan", "--output", plan_path, "--json"],
                    state_home,
                )
            )
            self.assertEqual(plan["action"], "scrap")
            self.assertTrue(plan_path.is_file())

            project_state = target / ".baton/state/project.json"
            original_state = project_state.read_bytes()
            project_state.write_bytes(original_state + b"\n")
            stale = baton(
                target,
                ["scrap", "apply", "--plan", plan_path, "--yes", "--json"],
                state_home,
                expected=1,
            )
            self.assertIn("Baton tree changed", stale.stdout + stale.stderr)
            self.assertTrue((target / ".baton").is_dir())
            project_state.write_bytes(original_state)

            result = json_output(
                baton(
                    target,
                    ["scrap", "apply", "--plan", plan_path, "--yes", "--json"],
                    state_home,
                )
            )
            self.assertTrue(result["ok"])
            self.assertFalse((target / ".baton").exists())
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / ".agents").exists())
            self.assertFalse((target / ".codex").exists())
            self.assertTrue(Path(result["backupPath"]).is_dir())
            self.assertTrue(Path(result["reportPath"]).is_file())

    def test_doctor_recover_repairs_an_interrupted_team_transaction(self):
        with tempfile.TemporaryDirectory(prefix="baton-cli-recover-") as raw:
            base = Path(raw).resolve()
            source = make_candidate(base, "7.1.1")
            bundle = base / "bundle"
            build_bundle(source, bundle)
            target = base / "repository"
            target.mkdir()
            state_home = base / "state"
            state_home.mkdir()
            install_bundle(bundle, target, state_home)

            baton(
                target,
                ["roster", "hire", "--consultant", "security-lead", "--yes", "--json"],
                state_home,
                expected=97,
                extra_env={
                    "BATON_TEST_TEAM_EXIT_AFTER": ".baton/memory/history.jsonl",
                },
            )

            recovered = json_output(
                baton(target, ["doctor", "recover", "--json"], state_home)
            )
            self.assertTrue(recovered["ok"])
            self.assertEqual(recovered["mode"], "recover")
            self.assertEqual(recovered["recovery"]["team"]["recoveredCount"], 1)
            evidence = recovered["recovery"]["team"]["recovered"][0]
            self.assertEqual(evidence["result"], "rolled-back-recovered")
            self.assertTrue(Path(evidence["reportPath"]).is_file())
            self.assertEqual(recovered["recovery"]["memory"]["recoveredCount"], 0)

            checked = json_output(
                baton(target, ["doctor", "check", "--json"], state_home)
            )
            self.assertTrue(checked["ok"])
            self.assertNotIn("recovery", checked)


if __name__ == "__main__":
    unittest.main()
