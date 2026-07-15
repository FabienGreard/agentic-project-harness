#!/usr/bin/env python3
"""Install, adoption, migration, update, and rollback tests for Baton."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import (  # noqa: E402
    SKILLS,
    assert_no_python_cache,
    baton,
    build_bundle,
    changed_paths,
    expected_consumer_config,
    git_commit,
    install_bundle,
    json_output,
    make_activation_proposal,
    make_candidate,
    make_mature_project,
    manifest,
    semantic_toml,
    sha256,
    tree_snapshot,
)


class BatonInstallAndAdoptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-lifecycle-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle-060"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_fresh_install_is_namespaced_and_has_exact_config_and_discovery(self) -> None:
        target = self.base / "fresh"
        state_home = self.base / "state-fresh"
        result = json_output(install_bundle(self.bundle, target, state_home))
        self.assertEqual(result["mode"], "new-project")
        self.assertEqual(result["version"], "0.6.0")
        self.assertEqual(result["installationStatus"], "Installed")
        self.assertEqual(
            {path.name for path in target.iterdir()},
            {".git", ".baton", ".agents", ".codex", "AGENTS.md"},
        )
        self.assertFalse((target / "install.sh").exists())
        self.assertFalse((target / "VERSION").exists())
        self.assertFalse((target / ".codex/skills").exists())
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["schemaVersion"], 3)
        self.assertEqual(metadata["batonVersion"], "0.6.0")
        self.assertIsNone(metadata["projectVersion"])
        self.assertEqual(metadata["source"]["commit"], git_commit(self.source))
        self.assertEqual(metadata["source"]["channel"], "stable")
        self.assertEqual(semantic_toml(target / ".codex/config.toml"), expected_consumer_config())
        for name in SKILLS:
            path = target / ".agents/skills" / name
            self.assertTrue(path.is_symlink(), path)
            self.assertEqual(path.readlink().as_posix(), f"../../.baton/skills/{name}")
        status = json_output(baton(target, ["status", "--json"], state_home))
        self.assertTrue(status["ok"])
        self.assertEqual(status["batonVersion"], "0.6.0")
        self.assertEqual(status["integrity"], {"modified": [], "missing": [], "agentsBlock": "ok"})
        self.assertEqual(baton(target, ["check", "--json"], state_home).returncode, 0)
        assert_no_python_cache(target)

    def test_mature_adoption_preserves_project_files_and_quarantines_state(self) -> None:
        target = self.base / "mature"
        target.mkdir()
        fixtures = make_mature_project(target)
        before = tree_snapshot(target)
        state_home = self.base / "state-mature"
        result = json_output(install_bundle(self.bundle, target, state_home))
        after = tree_snapshot(target)
        self.assertEqual(result["mode"], "adoption")
        self.assertEqual(result["installationStatus"], "Needs Integration")
        adoption_check = json_output(baton(target, ["check", "--json"], state_home))
        self.assertTrue(adoption_check["ok"])
        self.assertTrue(adoption_check["quarantinedStarter"])
        for relative, content in fixtures.items():
            if relative == "AGENTS.md":
                self.assertIn(content.decode("utf-8"), (target / relative).read_text(encoding="utf-8"))
            else:
                self.assertEqual((target / relative).read_bytes(), content, relative)
        self.assertTrue((target / "node_modules/vendor/outside-link").is_symlink())
        self.assertFalse((target / ".baton/state").exists())
        self.assertTrue((target / ".baton/integration/starter/state/project.json").is_file())
        self.assertTrue((target / ".baton/integration/starter/state/team.json").is_file())
        self.assertTrue((target / ".baton/integration/cleanup-prompt.txt").is_file())
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Needs Integration")
        self.assertEqual(metadata["batonVersion"], "0.6.0")
        self.assertIsNone(metadata["projectVersion"])
        self.assertEqual(metadata["legacyCleanupCandidates"], [])
        self.assertFalse((target / "install.sh").exists())
        self.assertFalse((target / ".codex/skills").exists())
        self.assertEqual(
            semantic_toml(target / ".baton/integration/codex-config.toml"),
            expected_consumer_config(),
        )
        changed = changed_paths(before, after)
        disallowed = [
            path
            for path in changed
            if not (
                path == "AGENTS.md"
                or path == ".baton"
                or path.startswith(".baton/")
                or path in {f".agents/skills/{name}" for name in SKILLS if name != "brainstorm"}
            )
        ]
        self.assertEqual(disallowed, [])
        self.assertEqual((target / ".codex/config.toml").read_bytes(), fixtures[".codex/config.toml"])
        self.assertEqual(
            (target / ".agents/skills/brainstorm/SKILL.md").read_bytes(),
            fixtures[".agents/skills/brainstorm/SKILL.md"],
        )
        assert_no_python_cache(target)

    def test_reviewed_mature_state_requires_explicit_activate_from_path(self) -> None:
        target = self.base / "activation"
        target.mkdir()
        fixtures = make_mature_project(target)
        state_home = self.base / "state-activation"
        json_output(install_bundle(self.bundle, target, state_home))
        invalid = make_activation_proposal(
            target,
            self.base / "invalid-activation-proposal",
            valid=False,
        )
        before_invalid = tree_snapshot(target)
        rejected = baton(
            target,
            ["_activate", "--from", invalid, "--yes", "--json"],
            state_home,
            expected=1,
        )
        self.assertIn("concrete outcome/current goal", rejected.stdout + rejected.stderr)
        self.assertEqual(tree_snapshot(target), before_invalid)
        proposal = make_activation_proposal(
            target,
            self.base / "valid-activation-proposal",
        )
        activated = json_output(
            baton(
                target,
                ["_activate", "--from", proposal, "--yes", "--json"],
                state_home,
            )
        )
        self.assertEqual(activated["mode"], "activate")
        self.assertEqual(activated["installationStatus"], "Installed")
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Installed")
        self.assertTrue((target / ".baton/state/team.json").is_file())
        project = json.loads((target / ".baton/state/project.json").read_text(encoding="utf-8"))
        self.assertFalse(project["project"]["templateMode"])
        self.assertEqual(project["project"]["currentGoal"], "MATURE-GOAL-001")
        self.assertIn("Baton is active", (target / "AGENTS.md").read_text(encoding="utf-8"))
        for relative, content in fixtures.items():
            if relative != "AGENTS.md":
                self.assertEqual((target / relative).read_bytes(), content, relative)
        self.assertEqual(baton(target, ["check", "--json"], state_home).returncode, 0)
        assert_no_python_cache(target)

    def test_v02_through_v05_legacy_files_become_cleanup_candidates_only(self) -> None:
        for version in ("0.2.0", "0.3.0", "0.4.0", "0.5.0"):
            with self.subTest(version=version):
                target = self.base / f"legacy-{version}"
                target.mkdir()
                legacy_files = {
                    "HARNESS.md": b"legacy guide\n",
                    "tools/harness_state.py": b"# legacy state\n",
                    "docs/project-state.json": b'{"legacy":true}\n',
                }
                for relative, content in legacy_files.items():
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                legacy_metadata = {
                    "schemaVersion": 2,
                    "harnessVersion": version,
                    "managedFiles": {
                        relative: {"ownership": "harness-managed", "baselineSha256": hashlib.sha256(content).hexdigest()}
                        for relative, content in legacy_files.items()
                    },
                }
                (target / ".agent-harness.json").write_text(
                    json.dumps(legacy_metadata, indent=2) + "\n",
                    encoding="utf-8",
                )
                result = json_output(
                    install_bundle(self.bundle, target, self.base / f"state-legacy-{version}")
                )
                self.assertEqual(result["mode"], "adoption")
                for relative, content in legacy_files.items():
                    self.assertEqual((target / relative).read_bytes(), content)
                self.assertTrue((target / ".agent-harness.json").is_file())
                metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(
                    metadata["legacyCleanupCandidates"],
                    sorted([".agent-harness.json", *legacy_files]),
                )
                self.assertEqual(result["legacyCleanupCandidates"], metadata["legacyCleanupCandidates"])

    def test_failed_adoption_rolls_back_every_project_entry(self) -> None:
        target = self.base / "rollback-adoption"
        target.mkdir()
        make_mature_project(target)
        before = tree_snapshot(target)
        state_home = self.base / "state-rollback-adoption"
        failed = install_bundle(
            self.bundle,
            target,
            state_home,
            expected=1,
            extra_env={"BATON_TEST_FAIL_AFTER_WRITES": "2"},
        )
        self.assertIn("was rolled back", failed.stdout + failed.stderr)
        after = tree_snapshot(target)
        self.assertEqual(
            changed_paths(before, after),
            [],
            f"rollback tree drift: {changed_paths(before, after)}",
        )
        reports = list(state_home.rglob("update-report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["result"], "rolled-back")
        self.assertTrue(Path(report["backupPath"]).is_relative_to(state_home))

    def test_unsafe_symlink_and_unreadable_targets_fail_without_writes(self) -> None:
        real_target = self.base / "symlink-real-target"
        real_target.mkdir()
        sentinel = real_target / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        symlink_target = self.base / "symlink-target"
        symlink_target.symlink_to(real_target, target_is_directory=True)
        rejected_target = install_bundle(
            self.bundle,
            symlink_target,
            self.base / "state-symlink-target",
            expected=1,
        )
        self.assertIn("symbolic link", rejected_target.stdout + rejected_target.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((real_target / ".baton").exists())

        linked_parent = self.base / "linked-managed-parent"
        linked_parent.mkdir()
        outside = self.base / "outside-managed-parent"
        outside.mkdir()
        (linked_parent / "keep.txt").write_text("preserve\n", encoding="utf-8")
        (linked_parent / ".agents").symlink_to(outside, target_is_directory=True)
        outside_before = tree_snapshot(outside)
        linked_before = tree_snapshot(linked_parent)
        rejected_parent = install_bundle(
            self.bundle,
            linked_parent,
            self.base / "state-linked-parent",
            expected=1,
        )
        self.assertIn("symbolic link", rejected_parent.stdout + rejected_parent.stderr)
        self.assertEqual(tree_snapshot(outside), outside_before)
        self.assertEqual(tree_snapshot(linked_parent), linked_before)

        unreadable = self.base / "unreadable-target"
        unreadable.mkdir()
        unreadable_sentinel = unreadable / "sentinel.txt"
        unreadable_sentinel.write_text("preserve\n", encoding="utf-8")
        unreadable.chmod(0)
        try:
            rejected_unreadable = install_bundle(
                self.bundle,
                unreadable,
                self.base / "state-unreadable-target",
                expected=1,
            )
        finally:
            unreadable.chmod(0o700)
        self.assertIn(
            "Permission denied",
            rejected_unreadable.stdout + rejected_unreadable.stderr,
        )
        self.assertEqual(unreadable_sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((unreadable / ".baton").exists())


class BatonUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-update-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source_060 = make_candidate(cls.base, "0.6.0")
        cls.bundle_060 = cls.base / "bundle-060"
        build_bundle(cls.source_060, cls.bundle_060)
        cls.origin_manifest_sha = sha256(cls.bundle_060 / "baton-manifest.json")
        cls.source_061 = make_candidate(cls.base, "0.6.1", marker="v0.6.1 target")
        cls.bundle_061 = cls.base / "bundle-061"
        cls.origin = ("v0.6.0", git_commit(cls.source_060), cls.origin_manifest_sha)
        build_bundle(cls.source_061, cls.bundle_061, origins=[cls.origin])
        cls.bad_source_061 = make_candidate(cls.base / "bad", "0.6.1", marker="bad origin")
        cls.bad_bundle_061 = cls.base / "bundle-061-bad-origin"
        build_bundle(
            cls.bad_source_061,
            cls.bad_bundle_061,
            origins=[("v0.6.0", "0" * 40, cls.origin_manifest_sha)],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def install_060(self, name: str) -> tuple[Path, Path]:
        target = self.base / name
        state_home = self.base / f"state-{name}"
        result = json_output(install_bundle(self.bundle_060, target, state_home))
        self.assertEqual(result["version"], "0.6.0")
        return target, state_home

    def test_update_rejects_unpinned_origin_then_accepts_exact_commit_and_manifest(self) -> None:
        target, state_home = self.install_060("origin-pinning")
        json_output(
            baton(
                target,
                [
                    "_team",
                    "hire",
                    "--consultant",
                    "security-lead",
                    "--yes",
                    "--json",
                ],
                state_home,
            )
        )
        project_path = target / ".baton/state/project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["project"]["phase"] = "State preserved across stable update"
        operation = self.base / "state-preserving-update-operation.json"
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
        json_output(
            baton(target, ["_state", "apply", operation, "--json"], state_home)
        )
        overview = target / ".baton/docs/overview.md"
        overview.write_text(
            overview.read_text(encoding="utf-8")
            + "\nProject-owned update evidence.\n",
            encoding="utf-8",
        )
        state_before = {
            name: (target / f".baton/state/{name}.json").read_bytes()
            for name in ("project", "goals", "tickets", "ownership", "reviews", "team")
        }
        overview_before = overview.read_bytes()
        before = tree_snapshot(target)
        rejected = baton(
            target,
            ["update", "--yes", "--json"],
            state_home,
            bundle=self.bad_bundle_061,
            expected=1,
        )
        self.assertIn("immutable supported upgrade origin", rejected.stdout + rejected.stderr)
        self.assertEqual(tree_snapshot(target), before)
        updated = json_output(
            baton(
                target,
                ["update", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )
        self.assertFalse(updated["upToDate"])
        self.assertEqual(updated["version"], "0.6.1")
        self.assertIn("Release marker: v0.6.1 target", (target / ".baton/guide.md").read_text(encoding="utf-8"))
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["batonVersion"], "0.6.1")
        self.assertEqual(metadata["source"]["commit"], git_commit(self.source_061))
        self.assertEqual(metadata["source"]["manifestSha256"], sha256(self.bundle_061 / "baton-manifest.json"))
        self.assertFalse((target / "install.sh").exists())
        for name, content in state_before.items():
            self.assertEqual((target / f".baton/state/{name}.json").read_bytes(), content, name)
        self.assertEqual(overview.read_bytes(), overview_before)
        self.assertEqual(
            semantic_toml(target / ".codex/config.toml"),
            expected_consumer_config(("product-designer", "security-lead")),
        )
        self.assertEqual(baton(target, ["check", "--json"], state_home).returncode, 0)

    def test_needs_integration_update_advances_quarantined_starter_only(self) -> None:
        target = self.base / "needs-integration-update"
        target.mkdir()
        fixtures = make_mature_project(target)
        state_home = self.base / "state-needs-integration-update"
        installed = json_output(install_bundle(self.bundle_060, target, state_home))
        self.assertEqual(installed["installationStatus"], "Needs Integration")
        starter_overview = target / ".baton/integration/starter/docs/overview.md"
        self.assertNotIn("v0.6.1 target", starter_overview.read_text(encoding="utf-8"))

        updated = json_output(
            baton(
                target,
                ["update", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )
        self.assertEqual(updated["version"], "0.6.1")
        self.assertIn("v0.6.1 target", starter_overview.read_text(encoding="utf-8"))
        self.assertFalse((target / ".baton/state").exists())
        for relative, content in fixtures.items():
            if relative == "AGENTS.md":
                self.assertIn(content.decode("utf-8"), (target / relative).read_text(encoding="utf-8"))
            else:
                self.assertEqual((target / relative).read_bytes(), content, relative)
        checked = json_output(baton(target, ["check", "--json"], state_home))
        self.assertTrue(checked["ok"])
        self.assertEqual(checked["installationStatus"], "Needs Integration")
        self.assertTrue(checked["quarantinedStarter"])
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Needs Integration")
        self.assertFalse((target / ".codex/skills").exists())
        assert_no_python_cache(target)

    def test_failed_update_restores_all_touched_paths_and_reports_external_backup(self) -> None:
        target, state_home = self.install_060("update-rollback")
        before = tree_snapshot(target)
        failed = baton(
            target,
            ["update", "--yes", "--json"],
            state_home,
            bundle=self.bundle_061,
            expected=1,
            extra_env={"BATON_TEST_FAIL_AFTER_WRITES": "2"},
        )
        self.assertIn("was rolled back", failed.stdout + failed.stderr)
        after = tree_snapshot(target)
        self.assertEqual(
            changed_paths(before, after),
            [],
            f"rollback tree drift: {changed_paths(before, after)}",
        )
        reports = [
            path
            for path in state_home.rglob("update-report.json")
            if json.loads(path.read_text(encoding="utf-8")).get("result") == "rolled-back"
        ]
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertTrue(Path(report["backupPath"]).is_relative_to(state_home))


if __name__ == "__main__":
    unittest.main()
