#!/usr/bin/env python3
"""Canonical state, team, config, and discovery tests for installed Baton."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import (  # noqa: E402
    SKILLS,
    assert_no_python_cache,
    baton,
    build_bundle,
    expected_consumer_config,
    install_bundle,
    json_output,
    make_candidate,
    run,
    semantic_toml,
)


class StateTeamConfigDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-state-team-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def setUp(self) -> None:
        self.target = self.base / self.id().rsplit(".", 1)[-1]
        self.state_home = self.base / ("state-" + self.target.name)
        json_output(install_bundle(self.bundle, self.target, self.state_home))

    def test_state_apply_is_transactional_and_refreshes_dashboard_baseline(self) -> None:
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        project_path = self.target / ".baton/state/project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["project"]["phase"] = "Verified by deterministic state smoke"
        operation = self.base / f"{self.target.name}-operation.json"
        operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {"project": project},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied = json_output(
            baton(
                self.target,
                ["_state", "apply", operation, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(applied["changed"], ["project"])
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        dashboard = (self.target / ".baton/dashboard/index.html").read_text(encoding="utf-8")
        self.assertIn("Verified by deterministic state smoke", dashboard)
        status = json_output(baton(self.target, ["status", "--json"], self.state_home))
        self.assertTrue(status["ok"])

    def test_hire_and_fire_reconcile_nested_codex_agent_registry(self) -> None:
        hired = json_output(
            baton(
                self.target,
                ["_team", "hire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(hired["action"], "hire")
        self.assertEqual(hired["manualActions"], [])
        security_config = self.target / ".baton/agents/consultant-security-lead.toml"
        self.assertTrue(security_config.is_file())
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(("product-designer", "security-lead")),
        )
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        fired = json_output(
            baton(
                self.target,
                ["_team", "fire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(fired["action"], "fire")
        self.assertFalse(fired["manualCleanupRequired"])
        self.assertFalse(security_config.exists())
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(),
        )
        team = json.loads((self.target / ".baton/state/team.json").read_text(encoding="utf-8"))
        security = next(item for item in team["consultants"] if item["id"] == "security-lead")
        self.assertEqual(security["status"], "inactive")
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)

    def test_codex_contract_accepts_exact_nested_agent_semantics(self) -> None:
        config = self.target / ".codex/config.toml"
        self.assertEqual(semantic_toml(config), expected_consumer_config())
        expected_names = [
            "management",
            "operations",
            "contractor",
            "internal_audit",
            "consultant_product_designer",
        ]
        contract_script = (
            "import sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(self.target / '.baton/lib')!r}); "
            "from codex_config_contract import assert_codex_config; "
            f"assert_codex_config(Path({str(config)!r}), {expected_names!r})"
        )
        run([sys.executable, "-c", contract_script], cwd=self.target)

    def test_discovery_uses_individual_links_and_never_codex_skills_or_bytecode(self) -> None:
        self.assertFalse((self.target / ".codex/skills").exists())
        self.assertFalse((self.target / ".codex/skills").is_symlink())
        actual = {path.name for path in (self.target / ".agents/skills").iterdir()}
        self.assertEqual(actual, set(SKILLS))
        for name in SKILLS:
            link = self.target / ".agents/skills" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (self.target / ".baton/skills" / name).resolve())
        self.assertEqual(baton(self.target, ["status", "--json"], self.state_home).returncode, 0)
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        assert_no_python_cache(self.target)

    def test_cross_process_mutations_share_one_lock_without_lost_team_updates(self) -> None:
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_PROJECT_ROOT": str(self.target),
                "HOME": str(self.base / "lock-home"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(self.state_home),
            }
        )
        first_environment = dict(environment)
        first_environment["BATON_TEST_HOLD_MUTATION_LOCK_MS"] = "700"
        command = [
            str(self.target / ".baton/bin/baton"),
            "_team",
            "hire",
            "--yes",
            "--json",
            "--consultant",
        ]
        first = subprocess.Popen(
            [*command, "security-lead"],
            cwd=str(self.target),
            env=first_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        project_id = hashlib.sha256(str(self.target.resolve()).encode("utf-8")).hexdigest()[:16]
        lock_path = Path("/tmp") / f"baton-{os.getuid()}" / project_id / "mutation.lock"
        deadline = time.monotonic() + 5
        acquired = False
        while time.monotonic() < deadline:
            try:
                record = json.loads(lock_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            if (
                record.get("operation") == "team-hire_consultant"
                and first.poll() is None
            ):
                acquired = True
                break
            time.sleep(0.02)
        self.assertTrue(acquired, "first process never acquired the shared mutation lock")

        second_started = time.monotonic()
        second = subprocess.Popen(
            [*command, "accessibility-lead"],
            cwd=str(self.target),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        first_stdout, first_stderr = first.communicate(timeout=15)
        second_stdout, second_stderr = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
        self.assertEqual(second.returncode, 0, second_stdout + second_stderr)
        self.assertGreaterEqual(time.monotonic() - second_started, 0.35)

        team = json.loads((self.target / ".baton/state/team.json").read_text(encoding="utf-8"))
        active = [item["id"] for item in team["consultants"] if item["status"] == "active"]
        self.assertEqual(
            active,
            ["product-designer", "security-lead", "accessibility-lead"],
        )
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(tuple(active)),
        )
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        assert_no_python_cache(self.target)

    def test_full_goal_controls_do_not_revive_legacy_persistent_goal_onboarding(self) -> None:
        regression_fixture = {
            "availableGoalControls": ["create_goal", "get_goal", "update_goal"],
            "legacyOnboardingPrompt": (
                "Create a persistent goal for this permanent role and rely on automatic continuation."
            ),
            "automaticContinuation": True,
            "newTaskMessage": False,
            "expectedAction": "perform no work and report the legacy continuation",
        }
        self.assertEqual(
            regression_fixture["availableGoalControls"],
            ["create_goal", "get_goal", "update_goal"],
        )
        thread_registry = (self.target / ".baton/thread-registry.md").read_text(
            encoding="utf-8"
        )
        lifecycle_rule = (self.target / ".baton/rules/lifecycle-and-idle.md").read_text(
            encoding="utf-8"
        )
        policy = (thread_registry + "\n" + lifecycle_rule).casefold()
        for expected in (
            "sole wake mechanism",
            "full goal controls",
            "never create, resume, recreate, or attach a persistent goal",
            "inspect for control purposes",
            "automatic continuation without a new task message",
            "performs no work",
            "older onboarding prompt",
        ):
            self.assertIn(expected, policy)
        goals_path = self.target / ".baton/state/goals.json"
        goals_before = goals_path.read_bytes()
        self.assertEqual(json.loads(goals_before)["goals"], [])
        self.assertEqual(baton(self.target, ["status", "--json"], self.state_home).returncode, 0)
        self.assertEqual(baton(self.target, ["check", "--json"], self.state_home).returncode, 0)
        self.assertEqual(goals_path.read_bytes(), goals_before)
        self.assertEqual(
            regression_fixture["expectedAction"],
            "perform no work and report the legacy continuation",
        )


if __name__ == "__main__":
    unittest.main()
