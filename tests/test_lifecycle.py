#!/usr/bin/env python3
"""Install, adoption, migration, update, and rollback tests for Baton."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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
    changed_paths,
    expected_consumer_config,
    git_commit,
    install_bundle,
    json_output,
    make_activation_proposal,
    make_candidate,
    make_mature_project,
    manifest,
    resign_manifest,
    semantic_toml,
    sha256,
    tree_snapshot,
)


V05_COMMIT = "4191fe4be3a8da1ce3cea075bfb8f81a8d0d737c"
V05_MANIFEST_SHA256 = "744041e438990c37f3303666560c49cfbb919dec84e937e15307bae1fad3c88a"
V05_SKILL_PATHS = (
    ".agents/skills/README.md",
    ".agents/skills/brainstorm/SKILL.md",
    ".agents/skills/brainstorm/agents/openai.yaml",
    ".agents/skills/code-review/SKILL.md",
    ".agents/skills/code-review/agents/openai.yaml",
    ".agents/skills/code-review/references/review-axes.md",
    ".agents/skills/fire-consultant/SKILL.md",
    ".agents/skills/fire-consultant/agents/openai.yaml",
    ".agents/skills/hire-consultant/SKILL.md",
    ".agents/skills/hire-consultant/agents/openai.yaml",
    ".agents/skills/improve-codebase-architecture/SKILL.md",
    ".agents/skills/improve-codebase-architecture/agents/openai.yaml",
    ".agents/skills/improve-codebase-architecture/references/report-format.md",
    ".agents/skills/skills.json",
)


def make_v05_skill_install(target: Path) -> dict[str, bytes]:
    """Reproduce the public v0.5 discovery shape with exact provenance semantics."""
    target.mkdir()
    project_file = target / "README.md"
    project_file.write_text("# Project-owned identity\n", encoding="utf-8")
    legacy_files: dict[str, bytes] = {}
    managed: dict[str, dict[str, str]] = {
        "README.md": {
            "ownership": "project-owned",
            "baselineSha256": hashlib.sha256(project_file.read_bytes()).hexdigest(),
        }
    }
    for relative in V05_SKILL_PATHS:
        content = f"public v0.5 skill-shape fixture: {relative}\n".encode()
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        legacy_files[relative] = content
        managed[relative] = {
            "ownership": "harness-managed",
            "baselineSha256": hashlib.sha256(content).hexdigest(),
        }
    codex_skills = target / ".codex/skills"
    codex_skills.parent.mkdir(parents=True)
    codex_skills.symlink_to("../.agents/skills")
    managed[".codex/skills"] = {
        "ownership": "harness-managed",
        "baselineSha256": hashlib.sha256(b"../.agents/skills").hexdigest(),
    }
    metadata = {
        "schemaVersion": 2,
        "harnessVersion": "0.5.0",
        "stateSchemaVersion": 1,
        "provider": "codex",
        "installationStatus": "Installed",
        "projectName": "v0.5 migration fixture",
        "projectType": "software-product",
        "source": {
            "repository": "FabienGreard/agentic-project-harness",
            "channel": "stable",
            "tag": "v0.5.0",
            "commit": V05_COMMIT,
            "manifestSha256": V05_MANIFEST_SHA256,
        },
        "managedFiles": managed,
    }
    (target / ".agent-harness.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return legacy_files


def markdown_link_failures(root: Path) -> tuple[int, list[str]]:
    checked = 0
    missing: list[str] = []
    for document in root.rglob("*.md"):
        for raw_target in re.findall(
            r"(?<!!)\[[^]]+\]\(([^)]+)\)",
            document.read_text(encoding="utf-8"),
        ):
            link = raw_target.strip().split()[0].strip("<>")
            if not link or link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = link.split("#", 1)[0]
            if not relative:
                continue
            checked += 1
            if not (document.parent / relative).resolve().exists():
                missing.append(f"{document.relative_to(root)} -> {link}")
    return checked, missing


class BatonInstallAndAdoptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-lifecycle-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle-060"
        build_bundle(cls.source, cls.bundle)
        cls.bundle_with_v05_origin = cls.base / "bundle-060-v05-origin"
        build_bundle(
            cls.source,
            cls.bundle_with_v05_origin,
            origins=[("v0.5.0", V05_COMMIT, V05_MANIFEST_SHA256)],
        )

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
        self.assertEqual(metadata["memorySchemaVersion"], 1)
        self.assertIsNone(metadata["repositoryVersion"])
        self.assertEqual(metadata["source"]["commit"], git_commit(self.source))
        self.assertEqual(metadata["source"]["channel"], "stable")
        self.assertEqual(
            {
                path.relative_to(target / ".baton/memory").as_posix(): path.read_bytes()
                for path in (target / ".baton/memory").iterdir()
            },
            {
                path.name: path.read_bytes()
                for path in (self.source / "template/.baton/memory").iterdir()
            },
        )
        self.assertTrue(
            {".baton/memory/memory.json", ".baton/memory/history.jsonl"}
            <= set(metadata["projectOwnedFiles"])
        )
        self.assertFalse(
            any(path.startswith(".baton/memory/") for path in metadata["managedFiles"])
        )
        self.assertNotIn(".baton/views/team-tasks.md", metadata["projectOwnedFiles"])
        self.assertEqual(
            metadata["managedFiles"][".baton/views/team-tasks.md"]["ownership"],
            "generated-config",
        )
        self.assertIn(
            "Use `$boot` for initial assembly or `$roster` for later changes",
            (target / ".baton/views/team-tasks.md").read_text(encoding="utf-8"),
        )
        self.assertTrue((target / ".baton/records/README.md").is_file())
        self.assertIn(
            ".baton/records/<GOAL-ID>/",
            (target / ".baton/records/README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            ".baton/records/<TICKET-ID>/",
            (target / ".baton/records/README.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(semantic_toml(target / ".codex/config.toml"), expected_consumer_config())
        for name in SKILLS:
            path = target / ".agents/skills" / name
            self.assertTrue(path.is_symlink(), path)
            self.assertEqual(path.readlink().as_posix(), f"../../.baton/skills/{name}")
        status = json_output(baton(target, ["terminal", "status", "--json"], state_home))
        self.assertTrue(status["ok"])
        self.assertEqual(status["batonVersion"], "0.6.0")
        self.assertEqual(status["memorySchemaVersion"], 1)
        self.assertEqual(status["integrity"], {"modified": [], "missing": [], "agentsBlock": "ok"})
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)
        checked_links, missing_links = markdown_link_failures(target)
        self.assertGreater(checked_links, 0)
        self.assertEqual(missing_links, [])
        assert_no_python_cache(target)

    def test_install_rejects_false_projection_provenance(self) -> None:
        tampered = self.base / "false-projection-bundle"
        shutil.copytree(self.bundle, tampered)
        document = manifest(tampered)
        record = next(
            item
            for item in document["payloads"]["new-project"]["files"]
            if item["path"] == ".baton/workflow.md"
        )
        record["projection"] = "starter"
        resign_manifest(tampered, document)
        result = install_bundle(
            tampered,
            self.base / "false-projection-target",
            self.base / "state-false-projection",
            expected=1,
        )
        self.assertIn("payload projection provenance mismatch", result.stdout)

    def test_concurrent_installers_recheck_target_state_inside_the_lock(self) -> None:
        target = self.base / "concurrent-install"
        target.mkdir()
        state_home = self.base / "state-concurrent-install"
        command = [
            "bash",
            str(self.bundle / "install.sh"),
            "--yes",
            "--json",
            "--target",
            str(target),
        ]
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_RELEASE_DIR": str(self.bundle),
                "HOME": str(self.base / "concurrent-home"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(state_home),
            }
        )
        first_environment = dict(environment)
        first_environment["BATON_TEST_HOLD_MUTATION_LOCK_MS"] = "700"
        first = subprocess.Popen(
            command,
            cwd=str(self.base),
            env=first_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        project_id = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:16]
        lock_path = Path("/tmp") / f"baton-{os.getuid()}" / project_id / "mutation.lock"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                lock_record = json.loads(lock_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            if lock_record.get("operation") == "lifecycle-new-project" and first.poll() is None:
                break
            time.sleep(0.02)
        else:
            self.fail("first installer never acquired the shared mutation lock")
        second = subprocess.Popen(
            command,
            cwd=str(self.base),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        first_stdout, first_stderr = first.communicate(timeout=15)
        second_stdout, second_stderr = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
        self.assertEqual(second.returncode, 1, second_stdout + second_stderr)
        self.assertIn("Baton is already installed; use update", second_stdout + second_stderr)
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)
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
        adoption_check = json_output(baton(target, ["doctor", "check", "--json"], state_home))
        self.assertTrue(adoption_check["ok"])
        self.assertTrue(adoption_check["quarantinedStarter"])
        for relative, content in fixtures.items():
            if relative == "AGENTS.md":
                self.assertIn(content.decode("utf-8"), (target / relative).read_text(encoding="utf-8"))
            else:
                self.assertEqual((target / relative).read_bytes(), content, relative)
        self.assertTrue((target / "node_modules/vendor/outside-link").is_symlink())
        self.assertFalse((target / ".baton/state").exists())
        self.assertTrue((target / ".baton/migration/starter/state/project.json").is_file())
        self.assertTrue((target / ".baton/migration/starter/state/team.json").is_file())
        self.assertFalse((target / ".baton/AGENTS.md").exists())
        self.assertTrue((target / ".baton/migration/starter/AGENTS.md").is_file())
        self.assertTrue((target / ".baton/migration/starter/views/dashboard.html").is_file())
        self.assertTrue((target / ".baton/migration/starter/records/README.md").is_file())
        for bridge, destination in {
            "metadata.json": "../../metadata.json",
            "roles": "../../roles",
            "rules": "../../rules",
            "skills": "../../skills",
            "templates": "../../templates",
        }.items():
            path = target / ".baton/migration/starter" / bridge
            self.assertTrue(path.is_symlink(), bridge)
            self.assertEqual(path.readlink().as_posix(), destination)
        self.assertEqual(
            {
                path.relative_to(target / ".baton/migration/starter/memory").as_posix(): path.read_bytes()
                for path in (target / ".baton/migration/starter/memory").iterdir()
            },
            {
                path.name: path.read_bytes()
                for path in (self.source / "template/.baton/memory").iterdir()
            },
        )
        self.assertFalse((target / ".baton/memory").exists())
        self.assertTrue((target / ".baton/migration/cleanup-prompt.txt").is_file())
        cleanup_prompt = (target / ".baton/migration/cleanup-prompt.txt").read_text(encoding="utf-8")
        self.assertIn(
            ".baton/bin/baton boot activate --from /absolute/path/to/reviewed-proposal --json",
            cleanup_prompt,
        )
        self.assertIn("preserved legacy files", cleanup_prompt)
        self.assertIn("conflicts or manual actions", cleanup_prompt)
        self.assertIn("external transactional backup and rollback location", cleanup_prompt)
        self.assertIn("blob/<immutable-commit>/<source-path>", cleanup_prompt)
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Needs Integration")
        self.assertEqual(metadata["batonVersion"], "0.6.0")
        self.assertEqual(metadata["memorySchemaVersion"], 1)
        self.assertIsNone(metadata["repositoryVersion"])
        self.assertEqual(metadata["legacyCleanupCandidates"], [])
        self.assertFalse((target / "install.sh").exists())
        self.assertFalse((target / ".codex/skills").exists())
        self.assertEqual(
            semantic_toml(target / ".baton/migration/codex-config.toml"),
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
                or path in {".agents", ".agents/skills"}
                or path in {f".agents/skills/{name}" for name in SKILLS}
            )
        ]
        self.assertEqual(disallowed, [])
        self.assertEqual((target / ".codex/config.toml").read_bytes(), fixtures[".codex/config.toml"])
        checked_links, missing_links = markdown_link_failures(target)
        self.assertGreater(checked_links, 0)
        self.assertEqual(missing_links, [])
        assert_no_python_cache(target)

    def test_skill_discovery_collision_fails_before_any_write(self) -> None:
        target = self.base / "skill-discovery-collision"
        collision = target / ".agents/skills/boot/SKILL.md"
        collision.parent.mkdir(parents=True)
        collision.write_text("# Project-owned boot skill\n", encoding="utf-8")
        before = tree_snapshot(target)
        failed = install_bundle(
            self.bundle,
            target,
            self.base / "state-skill-discovery-collision",
            expected=1,
        )
        self.assertIn("skill-discovery collision", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_authentic_v05_skill_discovery_is_preserved_as_one_manual_boundary(self) -> None:
        target = self.base / "authentic-v05-skill-discovery"
        legacy_files = make_v05_skill_install(target)
        project_before = (target / "README.md").read_bytes()
        result = json_output(
            install_bundle(
                self.bundle_with_v05_origin,
                target,
                self.base / "state-authentic-v05-skill-discovery",
            )
        )

        self.assertEqual(result["mode"], "adoption")
        self.assertEqual(result["installationStatus"], "Needs Integration")
        self.assertEqual((target / "README.md").read_bytes(), project_before)
        for relative, content in legacy_files.items():
            self.assertEqual((target / relative).read_bytes(), content, relative)
        for name in SKILLS:
            self.assertFalse((target / f".agents/skills/{name}").is_symlink(), name)
        self.assertTrue((target / ".agents/skills/brainstorm").is_dir())
        self.assertTrue((target / ".codex/skills").is_symlink())
        self.assertEqual(os.readlink(target / ".codex/skills"), "../.agents/skills")

        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertTrue(
            {".agent-harness.json", ".codex/skills", *V05_SKILL_PATHS}
            <= set(metadata["legacyCleanupCandidates"])
        )
        self.assertTrue(
            any("verified v0.5 skill discovery" in item for item in metadata["pendingIntegration"])
        )
        plan = target / ".baton/migration/skill-discovery.md"
        self.assertTrue(plan.is_file())
        plan_text = plan.read_text(encoding="utf-8")
        for name in SKILLS:
            self.assertIn(f".agents/skills/{name}", plan_text)
            self.assertIn(f"../../.baton/skills/{name}", plan_text)

        state_home = self.base / "state-authentic-v05-skill-discovery"
        status = json_output(baton(target, ["terminal", "status", "--json"], state_home))
        self.assertTrue(status["ok"])
        self.assertEqual(status["installationStatus"], "Needs Integration")
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)

        proposal = make_activation_proposal(
            target,
            self.base / "authentic-v05-activation-proposal",
        )
        before_blocked_activation = tree_snapshot(target)
        blocked = baton(
            target,
            ["boot", "activate", "--from", proposal, "--yes", "--json"],
            state_home,
            expected=1,
        )
        self.assertIn("skill discovery", blocked.stdout + blocked.stderr)
        self.assertEqual(tree_snapshot(target), before_blocked_activation)

        (target / ".codex/skills").unlink()
        shutil.rmtree(target / ".agents/skills")
        (target / ".agents/skills").mkdir()
        for name in SKILLS:
            (target / f".agents/skills/{name}").symlink_to(
                f"../../.baton/skills/{name}"
            )
        activated = json_output(
            baton(
                target,
                ["boot", "activate", "--from", proposal, "--yes", "--json"],
                state_home,
            )
        )
        self.assertEqual(activated["installationStatus"], "Installed")
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertFalse(
            any("verified v0.5 skill discovery" in item for item in metadata["pendingIntegration"])
        )
        self.assertFalse(
            any(path.startswith(".agents/skills/") for path in metadata["legacyCleanupCandidates"])
        )
        self.assertNotIn(".codex/skills", metadata["legacyCleanupCandidates"])
        for name in SKILLS:
            record = metadata["managedFiles"][f".agents/skills/{name}"]
            self.assertEqual(record["ownership"], "integration-link")
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)

    def test_modified_v05_skill_discovery_still_fails_before_any_write(self) -> None:
        target = self.base / "modified-v05-skill-discovery"
        make_v05_skill_install(target)
        modified = target / ".agents/skills/brainstorm/SKILL.md"
        modified.write_text("# Locally modified legacy skill\n", encoding="utf-8")
        before = tree_snapshot(target)
        failed = install_bundle(
            self.bundle_with_v05_origin,
            target,
            self.base / "state-modified-v05-skill-discovery",
            expected=1,
        )
        self.assertIn("skill-discovery collision", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_v05_skill_discovery_with_an_untracked_extra_still_fails_atomically(self) -> None:
        target = self.base / "extra-v05-skill-discovery"
        make_v05_skill_install(target)
        (target / ".agents/skills/.DS_Store").write_bytes(b"untracked extra\n")
        before = tree_snapshot(target)
        failed = install_bundle(
            self.bundle_with_v05_origin,
            target,
            self.base / "state-extra-v05-skill-discovery",
            expected=1,
        )
        self.assertIn("skill-discovery collision", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_adoption_preserves_agents_symlink_as_manual_integration(self) -> None:
        target = self.base / "agents-symlink"
        target.mkdir()
        project_agents = target / "PROJECT_AGENTS.md"
        project_agents.write_text("# Project-owned agent map\n", encoding="utf-8")
        (target / "AGENTS.md").symlink_to("PROJECT_AGENTS.md")
        before_target = project_agents.read_bytes()
        state_home = self.base / "state-agents-symlink"
        result = json_output(install_bundle(self.bundle, target, state_home))
        self.assertEqual(result["mode"], "adoption")
        self.assertTrue((target / "AGENTS.md").is_symlink())
        self.assertEqual(os.readlink(target / "AGENTS.md"), "PROJECT_AGENTS.md")
        self.assertEqual(project_agents.read_bytes(), before_target)
        proposal = target / ".baton/migration/AGENTS.md"
        self.assertTrue(proposal.is_file())
        self.assertIn("BATON:START", proposal.read_text(encoding="utf-8"))
        self.assertTrue(any("AGENTS.md" in item for item in result["manualActions"]))
        status = json_output(baton(target, ["terminal", "status", "--json"], state_home))
        self.assertTrue(status["ok"])
        self.assertEqual(status["integrity"]["agentsBlock"], "pending-manual")
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)
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
            ["boot", "activate", "--from", invalid, "--yes", "--json"],
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
                ["boot", "activate", "--from", proposal, "--yes", "--json"],
                state_home,
            )
        )
        self.assertEqual(activated["mode"], "activate")
        self.assertEqual(activated["installationStatus"], "Installed")
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Installed")
        self.assertTrue((target / ".baton/memory/memory.json").is_file())
        self.assertTrue((target / ".baton/memory/history.jsonl").is_file())
        self.assertTrue(
            {".baton/memory/memory.json", ".baton/memory/history.jsonl"}
            <= set(metadata["projectOwnedFiles"])
        )
        self.assertFalse(
            any(path.startswith(".baton/memory/") for path in metadata["managedFiles"])
        )
        self.assertTrue((target / ".baton/state/team.json").is_file())
        self.assertTrue((target / ".baton/records/README.md").is_file())
        project = json.loads((target / ".baton/state/project.json").read_text(encoding="utf-8"))
        self.assertFalse(project["project"]["templateMode"])
        self.assertEqual(project["project"]["currentGoal"], "MATURE-GOAL-001")
        self.assertIn("Baton is active", (target / "AGENTS.md").read_text(encoding="utf-8"))
        for relative, content in fixtures.items():
            if relative != "AGENTS.md":
                self.assertEqual((target / relative).read_bytes(), content, relative)
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)
        assert_no_python_cache(target)

    def test_activation_rejects_drift_in_any_managed_starter_path(self) -> None:
        target = self.base / "activation-starter-drift"
        target.mkdir()
        make_mature_project(target)
        state_home = self.base / "state-activation-starter-drift"
        json_output(install_bundle(self.bundle, target, state_home))
        proposal = make_activation_proposal(
            target,
            self.base / "activation-starter-drift-proposal",
        )
        agents = target / ".baton/migration/starter/AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8") + "\nUnreviewed starter drift.\n",
            encoding="utf-8",
        )
        before = tree_snapshot(target)
        rejected = baton(
            target,
            ["boot", "activate", "--from", proposal, "--yes", "--json"],
            state_home,
            expected=1,
        )
        self.assertIn("Baton-managed files differ from their baselines", rejected.stdout + rejected.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_activation_finalization_failure_rolls_back_every_project_entry(self) -> None:
        target = self.base / "activation-finalization-rollback"
        target.mkdir()
        make_mature_project(target)
        state_home = self.base / "state-activation-finalization-rollback"
        json_output(install_bundle(self.bundle, target, state_home))
        proposal = make_activation_proposal(
            target,
            self.base / "activation-finalization-rollback-proposal",
        )
        before = tree_snapshot(target)
        failed = baton(
            target,
            ["boot", "activate", "--from", proposal, "--yes", "--json"],
            state_home,
            expected=1,
            extra_env={"BATON_TEST_FAIL_DURING_FINALIZE": "1"},
        )
        self.assertIn("was rolled back", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_v02_through_v05_legacy_files_become_cleanup_candidates_only(self) -> None:
        legacy_commits = {
            "0.2.0": "8c3f9da8b08fca2408fa37bbf2a52d94e3fe8ad8",
            "0.3.0": "a8c041c2737f0cdec0834e5307906a4f9f15fabf",
            "0.4.0": "07c05a9d0ab72614a59809f3bd499ace5594797d",
            "0.5.0": "4191fe4be3a8da1ce3cea075bfb8f81a8d0d737c",
        }
        for version, source_commit in legacy_commits.items():
            with self.subTest(version=version):
                target = self.base / f"legacy-{version}"
                target.mkdir()
                legacy_files = {
                    "HARNESS.md": b"legacy guide\n",
                    "tools/harness_state.py": b"# locally modified legacy state\n",
                    "README.md": b"# Project-owned identity\n",
                }
                for relative, content in legacy_files.items():
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                if version in {"0.2.0", "0.3.0", "0.4.0"}:
                    legacy_metadata = {
                        "schemaVersion": 1,
                        "harnessVersion": version,
                        "provider": "codex",
                        "source": "FabienGreard/agentic-project-harness",
                        "ref": "main",
                        "sourceMode": "remote" if version in {"0.2.0", "0.3.0"} else "local",
                        "sourceRevision": None if version in {"0.2.0", "0.3.0"} else source_commit,
                        "sourceDirty": False,
                        "installed": True,
                        "installedAt": "2026-01-01T00:00:00+00:00",
                    }
                else:
                    legacy_metadata = {
                        "schemaVersion": 2,
                        "harnessVersion": version,
                        "source": {
                            "repository": "FabienGreard/agentic-project-harness",
                            "channel": "stable",
                            "tag": "v0.5.0",
                            "commit": source_commit,
                            "manifestSha256": "744041e438990c37f3303666560c49cfbb919dec84e937e15307bae1fad3c88a",
                        },
                        "managedFiles": {
                            "HARNESS.md": {
                                "ownership": "harness-managed",
                                "baselineSha256": hashlib.sha256(legacy_files["HARNESS.md"]).hexdigest(),
                            },
                            "tools/harness_state.py": {
                                "ownership": "harness-managed",
                                "baselineSha256": hashlib.sha256(b"# original legacy state\n").hexdigest(),
                            },
                            "README.md": {
                                "ownership": "project-owned",
                                "baselineSha256": hashlib.sha256(legacy_files["README.md"]).hexdigest(),
                            },
                        },
                    }
                (target / ".agent-harness.json").write_text(
                    json.dumps(legacy_metadata, indent=2) + "\n",
                    encoding="utf-8",
                )
                before = tree_snapshot(target)
                result = json_output(
                    install_bundle(self.bundle, target, self.base / f"state-legacy-{version}")
                )
                self.assertEqual(result["mode"], "adoption")
                after = tree_snapshot(target)
                for relative, value in before.items():
                    self.assertEqual(after.get(relative), value, relative)
                metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
                expected_candidates = (
                    [".agent-harness.json"]
                    if version != "0.5.0"
                    else [".agent-harness.json", "HARNESS.md"]
                )
                self.assertEqual(metadata["legacyCleanupCandidates"], expected_candidates)
                self.assertEqual(result["legacyCleanupCandidates"], metadata["legacyCleanupCandidates"])
                migration = metadata["legacyMigration"]
                self.assertEqual(migration["schemaVersion"], legacy_metadata["schemaVersion"])
                self.assertEqual(migration["harnessVersion"], version)
                if version in {"0.2.0", "0.3.0"}:
                    self.assertIsNone(migration["source"]["commit"])
                    self.assertNotIn("tree", migration["source"])
                    anchor = migration["source"]["versionAnchor"]
                    self.assertEqual(anchor["commit"], source_commit)
                    self.assertIn(source_commit, anchor["tree"])
                    self.assertIn(f"v{version}", anchor["release"])
                    self.assertIn("did not record", anchor["note"])
                else:
                    self.assertEqual(migration["source"]["commit"], source_commit)
                    self.assertIn(source_commit, migration["source"]["tree"])
                if version == "0.5.0":
                    statuses = {item["path"]: item["status"] for item in migration["files"]}
                    self.assertEqual(statuses["HARNESS.md"], "unchanged-managed-candidate")
                    self.assertEqual(statuses["tools/harness_state.py"], "modified-preserved")
                    self.assertEqual(statuses["README.md"], "project-owned-preserved")
                else:
                    self.assertEqual(migration["baselineMode"], "unavailable")
                    self.assertIn("no per-file baselines", migration["reason"])

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

    def test_adoption_finalization_failure_rolls_back_every_project_entry(self) -> None:
        target = self.base / "rollback-adoption-finalization"
        target.mkdir()
        make_mature_project(target)
        before = tree_snapshot(target)
        state_home = self.base / "state-rollback-adoption-finalization"
        failed = install_bundle(
            self.bundle,
            target,
            state_home,
            expected=1,
            extra_env={"BATON_TEST_FAIL_DURING_FINALIZE": "1"},
        )
        self.assertIn("was rolled back", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)
        reports = list(state_home.rglob("update-report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["result"], "rolled-back")

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
                    "roster",
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
            baton(target, ["control", "apply", operation, "--json"], state_home)
        )
        agents = target / ".baton/AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8")
            + "\nProject-owned update evidence.\n",
            encoding="utf-8",
        )
        state_before = {
            name: (target / f".baton/state/{name}.json").read_bytes()
            for name in ("project", "goals", "tickets", "ownership", "reviews", "team")
        }
        agents_before = agents.read_bytes()
        memory_before = {
            path.name: path.read_bytes()
            for path in (target / ".baton/memory").iterdir()
        }
        before = tree_snapshot(target)
        rejected = baton(
            target,
            ["upgrade", "apply", "--yes", "--json"],
            state_home,
            bundle=self.bad_bundle_061,
            expected=1,
        )
        self.assertIn("immutable supported upgrade origin", rejected.stdout + rejected.stderr)
        self.assertEqual(tree_snapshot(target), before)
        updated = json_output(
            baton(
                target,
                ["upgrade", "apply", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )
        self.assertFalse(updated["upToDate"])
        self.assertEqual(updated["version"], "0.6.1")
        self.assertIn("Release marker: v0.6.1 target", (target / ".baton/workflow.md").read_text(encoding="utf-8"))
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["batonVersion"], "0.6.1")
        self.assertEqual(metadata["source"]["commit"], git_commit(self.source_061))
        self.assertEqual(metadata["source"]["manifestSha256"], sha256(self.bundle_061 / "baton-manifest.json"))
        self.assertFalse((target / "install.sh").exists())
        for name, content in state_before.items():
            self.assertEqual((target / f".baton/state/{name}.json").read_bytes(), content, name)
        self.assertEqual(agents.read_bytes(), agents_before)
        self.assertEqual(
            {
                path.name: path.read_bytes()
                for path in (target / ".baton/memory").iterdir()
            },
            memory_before,
        )
        self.assertFalse(
            any(path.startswith(".baton/memory/") for path in metadata["managedFiles"])
        )
        self.assertEqual(
            semantic_toml(target / ".codex/config.toml"),
            expected_consumer_config(("product-designer", "security-lead")),
        )
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)

    def test_update_does_not_initialize_memory_for_an_older_installed_project(self) -> None:
        target, state_home = self.install_060("older-install-without-memory")
        shutil.rmtree(target / ".baton/memory")
        metadata_path = target / ".baton/metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.pop("memorySchemaVersion")
        metadata["projectOwnedFiles"] = [
            path
            for path in metadata["projectOwnedFiles"]
            if not path.startswith(".baton/memory/")
        ]
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        updated = json_output(
            baton(
                target,
                ["upgrade", "apply", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )
        self.assertEqual(updated["version"], "0.6.1")
        self.assertFalse((target / ".baton/memory").exists())
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["memorySchemaVersion"], 1)
        self.assertFalse(
            any(path.startswith(".baton/memory/") for path in metadata["managedFiles"])
        )
        initialized = json_output(
            baton(
                target,
                ["boot", "initialize", "--json"],
                state_home,
            )
        )
        self.assertTrue(initialized["changed"])
        self.assertTrue((target / ".baton/memory/memory.json").is_file())
        self.assertTrue((target / ".baton/memory/history.jsonl").is_file())
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertTrue(
            {
                ".baton/memory/memory.json",
                ".baton/memory/history.jsonl",
            }
            <= set(metadata["projectOwnedFiles"])
        )
        self.assertFalse(
            any(path.startswith(".baton/memory/") for path in metadata["managedFiles"])
        )
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)

    def test_update_moves_generated_views_without_deleting_legacy_paths(self) -> None:
        target, state_home = self.install_060("legacy-generated-views")
        metadata_path = target / ".baton/metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        managed = metadata["managedFiles"]

        old_dashboard = target / ".baton/dashboard/index.html"
        old_dashboard.parent.mkdir(parents=True)
        (target / ".baton/views/dashboard.html").replace(old_dashboard)
        managed[".baton/dashboard/index.html"] = managed.pop(
            ".baton/views/dashboard.html"
        )

        old_tasks = target / ".baton/thread-registry.md"
        (target / ".baton/views/team-tasks.md").replace(old_tasks)
        managed[".baton/thread-registry.md"] = managed.pop(
            ".baton/views/team-tasks.md"
        )
        (target / ".baton/views").rmdir()
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        old_dashboard_bytes = old_dashboard.read_bytes()
        old_tasks_bytes = old_tasks.read_bytes()

        updated = json_output(
            baton(
                target,
                ["upgrade", "apply", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )

        self.assertEqual(updated["version"], "0.6.1")
        self.assertTrue((target / ".baton/views/dashboard.html").is_file())
        self.assertTrue((target / ".baton/views/team-tasks.md").is_file())
        self.assertEqual(old_dashboard.read_bytes(), old_dashboard_bytes)
        self.assertEqual(old_tasks.read_bytes(), old_tasks_bytes)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertIn(".baton/views/dashboard.html", metadata["managedFiles"])
        self.assertIn(".baton/views/team-tasks.md", metadata["managedFiles"])
        self.assertNotIn(".baton/dashboard/index.html", metadata["managedFiles"])
        self.assertNotIn(".baton/thread-registry.md", metadata["managedFiles"])
        self.assertTrue(
            {
                ".baton/dashboard/index.html",
                ".baton/thread-registry.md",
            }
            <= set(metadata["legacyCleanupCandidates"])
        )
        self.assertEqual(baton(target, ["doctor", "check", "--json"], state_home).returncode, 0)

    def test_update_rejects_memory_schema_change_without_explicit_sequential_migration(self) -> None:
        target, state_home = self.install_060("memory-schema-migration-required")
        schema_two_bundle = self.base / "bundle-061-memory-schema-2"
        shutil.copytree(self.bundle_061, schema_two_bundle)
        document = manifest(schema_two_bundle)
        document["memorySchemaVersion"] = 2
        resign_manifest(schema_two_bundle, document)
        before = tree_snapshot(target)

        failed = baton(
            target,
            ["upgrade", "apply", "--yes", "--json"],
            state_home,
            bundle=schema_two_bundle,
            expected=1,
        )
        self.assertIn("explicit sequential memory migration", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_update_rejects_legacy_assurance_state_without_explicit_migration(self) -> None:
        target, state_home = self.install_060("assurance-state-migration-required")
        metadata_path = target / ".baton/metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["stateSchemaVersion"] = 1
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        before = tree_snapshot(target)

        failed = baton(
            target,
            ["upgrade", "apply", "--yes", "--json"],
            state_home,
            bundle=self.bundle_061,
            expected=1,
        )
        self.assertIn("explicit Baton migration path", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)

    def test_needs_integration_update_advances_quarantined_starter_only(self) -> None:
        target = self.base / "needs-integration-update"
        target.mkdir()
        fixtures = make_mature_project(target)
        state_home = self.base / "state-needs-integration-update"
        installed = json_output(install_bundle(self.bundle_060, target, state_home))
        self.assertEqual(installed["installationStatus"], "Needs Integration")
        starter_agents = target / ".baton/migration/starter/AGENTS.md"
        starter_project = target / ".baton/migration/starter/state/project.json"
        project_name = json.loads(starter_project.read_text(encoding="utf-8"))["project"]["name"]
        self.assertNotIn("v0.6.1 target", starter_agents.read_text(encoding="utf-8"))

        updated = json_output(
            baton(
                target,
                ["upgrade", "apply", "--yes", "--json"],
                state_home,
                bundle=self.bundle_061,
            )
        )
        self.assertEqual(updated["version"], "0.6.1")
        self.assertIn("v0.6.1 target", starter_agents.read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(starter_project.read_text(encoding="utf-8"))["project"]["name"],
            project_name,
        )
        self.assertFalse((target / ".baton/state").exists())
        self.assertFalse((target / ".baton/AGENTS.md").exists())
        self.assertTrue((target / ".baton/migration/starter/AGENTS.md").is_file())
        self.assertTrue((target / ".baton/migration/starter/views/dashboard.html").is_file())
        for relative, content in fixtures.items():
            if relative == "AGENTS.md":
                self.assertIn(content.decode("utf-8"), (target / relative).read_text(encoding="utf-8"))
            else:
                self.assertEqual((target / relative).read_bytes(), content, relative)
        checked = json_output(baton(target, ["doctor", "check", "--json"], state_home))
        self.assertTrue(checked["ok"])
        self.assertEqual(checked["installationStatus"], "Needs Integration")
        self.assertTrue(checked["quarantinedStarter"])
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["installationStatus"], "Needs Integration")
        self.assertFalse((target / ".codex/skills").exists())
        checked_links, missing_links = markdown_link_failures(target)
        self.assertGreater(checked_links, 0)
        self.assertEqual(missing_links, [])
        assert_no_python_cache(target)

    def test_upgrade_rejects_modified_missing_or_duplicated_agents_block(self) -> None:
        variants = ("modified", "missing", "duplicated")
        for variant in variants:
            with self.subTest(variant=variant):
                target, state_home = self.install_060(f"agents-integrity-{variant}")
                agents = target / "AGENTS.md"
                original = agents.read_text(encoding="utf-8")
                if variant == "modified":
                    agents.write_text(original.replace("Baton is active", "Baton block modified"), encoding="utf-8")
                elif variant == "missing":
                    agents.unlink()
                else:
                    agents.write_text(original + "\n" + original, encoding="utf-8")
                before = tree_snapshot(target)
                failed = baton(
                    target,
                    ["upgrade", "apply", "--yes", "--json"],
                    state_home,
                    bundle=self.bundle_061,
                    expected=1,
                )
                self.assertIn("Baton-managed files differ from their baselines", failed.stdout + failed.stderr)
                self.assertEqual(tree_snapshot(target), before)

    def test_update_and_activation_cannot_apply_from_stale_prelock_state(self) -> None:
        target = self.base / "concurrent-update-activation"
        target.mkdir()
        make_mature_project(target)
        state_home = self.base / "state-concurrent-update-activation"
        json_output(install_bundle(self.bundle_060, target, state_home))
        proposal = make_activation_proposal(
            target,
            self.base / "concurrent-update-activation-proposal",
        )
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_RELEASE_DIR": str(self.bundle_061),
                "HOME": str(self.base / "concurrent-update-home"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(state_home),
            }
        )
        update_environment = dict(environment)
        update_environment["BATON_TEST_HOLD_MUTATION_LOCK_MS"] = "700"
        updater = subprocess.Popen(
            [str(target / ".baton/bin/baton"), "upgrade", "apply", "--yes", "--json"],
            cwd=str(target),
            env=update_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        project_id = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:16]
        lock_path = Path("/tmp") / f"baton-{os.getuid()}" / project_id / "mutation.lock"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                lock_record = json.loads(lock_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            if lock_record.get("operation") == "lifecycle-update" and updater.poll() is None:
                break
            time.sleep(0.02)
        else:
            self.fail("update never acquired the shared mutation lock")
        activator = subprocess.Popen(
            [
                str(target / ".baton/bin/baton"),
                "boot", "activate",
                "--from",
                str(proposal),
                "--yes",
                "--json",
            ],
            cwd=str(target),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        update_stdout, update_stderr = updater.communicate(timeout=15)
        activate_stdout, activate_stderr = activator.communicate(timeout=15)
        self.assertEqual(updater.returncode, 0, update_stdout + update_stderr)
        self.assertEqual(activator.returncode, 1, activate_stdout + activate_stderr)
        self.assertIn("changed while activation was waiting for the lock", activate_stdout + activate_stderr)
        status = json_output(baton(target, ["terminal", "status", "--json"], state_home))
        self.assertEqual(status["batonVersion"], "0.6.1")
        self.assertEqual(status["installationStatus"], "Needs Integration")
        self.assertTrue(status["ok"])

    def test_failed_update_restores_all_touched_paths_and_reports_external_backup(self) -> None:
        target, state_home = self.install_060("update-rollback")
        before = tree_snapshot(target)
        failed = baton(
            target,
            ["upgrade", "apply", "--yes", "--json"],
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

    def test_update_finalization_failure_restores_every_touched_path(self) -> None:
        target, state_home = self.install_060("update-finalization-rollback")
        before = tree_snapshot(target)
        failed = baton(
            target,
            ["upgrade", "apply", "--yes", "--json"],
            state_home,
            bundle=self.bundle_061,
            expected=1,
            extra_env={"BATON_TEST_FAIL_DURING_FINALIZE": "1"},
        )
        self.assertIn("was rolled back", failed.stdout + failed.stderr)
        self.assertEqual(tree_snapshot(target), before)
        reports = [
            path
            for path in state_home.rglob("update-report.json")
            if json.loads(path.read_text(encoding="utf-8")).get("result") == "rolled-back"
        ]
        self.assertEqual(len(reports), 1)


if __name__ == "__main__":
    unittest.main()
