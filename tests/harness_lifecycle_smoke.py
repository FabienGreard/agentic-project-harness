#!/usr/bin/env python3
"""Focused behavior smoke for the internal install.sh lifecycle implementation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))

from harness_lifecycle import (  # type: ignore[import-not-found]
    LifecycleError,
    apply_file_plan,
    build_cleanup_prompt,
    build_metadata,
    inspect_status,
    plan_files,
    transaction_directory,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_for(source: Path, ownership: dict[str, str]) -> dict:
    return {
        "schemaVersion": 1,
        "harnessVersion": "0.5.0",
        "stateSchemaVersion": 1,
        "channel": "stable",
        "tag": "v0.5.0",
        "sourceCommit": "a" * 40,
        "supportedUpgradeOrigins": [],
        "upgradeOrigins": {},
        "files": {
            relative: {
                "ownership": category,
                "sha256": digest(source / relative),
            }
            for relative, category in sorted(ownership.items())
        },
    }


with tempfile.TemporaryDirectory(prefix="aph-lifecycle-") as raw:
    temp = Path(raw)
    source = temp / "source"
    project = temp / "project"
    source.mkdir()
    project.mkdir()

    write(source / "managed.txt", "target managed\n")
    write(source / "new.txt", "new managed\n")
    write(source / "generated.toml", "target = true\n")
    write(source / "project.json", '{"target": true}\n')
    manifest = manifest_for(
        source,
        {
            "generated.toml": "generated-config",
            "managed.txt": "harness-managed",
            "new.txt": "harness-managed",
            "project.json": "project-owned",
        },
    )
    boolean_state_manifest = json.loads(json.dumps(manifest))
    boolean_state_manifest["stateSchemaVersion"] = True
    try:
        plan_files(
            mode="adoption",
            project_root=project,
            source_root=source,
            target_manifest=boolean_state_manifest,
            installed_metadata=None,
        )
    except LifecycleError as error:
        assert "stateSchemaVersion must be an integer" in str(error)
    else:
        raise AssertionError("Boolean manifest stateSchemaVersion was accepted")

    write(project / "managed.txt", "installed managed\n")
    write(project / "generated.toml", "user changed\n")
    write(project / "project.json", '{"project": "keep"}\n')
    old_managed = digest(project / "managed.txt")
    old_generated = digest(project / "generated.toml")

    metadata = build_metadata(
        project_name="Lifecycle Test",
        project_type="software-product",
        reasoning_preset="medium",
        reasoning={
            "management": "high",
            "operations": "high",
            "consultants": "high",
            "contractors": "medium",
            "internalAudit": "xhigh",
        },
        manifest=manifest,
        manifest_sha256="b" * 64,
        installation_status="Installed",
        managed_files={
            "managed.txt": {
                "ownership": "harness-managed",
                "baselineSha256": old_managed,
            },
            "generated.toml": {
                "ownership": "generated-config",
                "baselineSha256": old_generated,
            },
        },
    )
    (project / ".agent-harness.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    initial = inspect_status(project)
    assert initial["installedVersion"] == "0.5.0"
    assert initial["installationStatus"] == "Installed"
    assert initial["integrity"]["modified"] == []
    boolean_state_metadata = json.loads(json.dumps(metadata))
    boolean_state_metadata["stateSchemaVersion"] = True
    (project / ".agent-harness.json").write_text(
        json.dumps(boolean_state_metadata, indent=2) + "\n", encoding="utf-8"
    )
    try:
        inspect_status(project)
    except LifecycleError as error:
        assert "unsupported state schema version" in str(error)
    else:
        raise AssertionError("Boolean metadata stateSchemaVersion was accepted")
    (project / ".agent-harness.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    write(project / "generated.toml", "user changed again\n")
    status = inspect_status(project)
    assert status["integrity"]["modified"] == ["generated.toml"]

    update_plan = plan_files(
        mode="update",
        project_root=project,
        source_root=source,
        target_manifest=manifest,
        installed_metadata=metadata,
    )
    assert [item["path"] for item in update_plan["replace"]] == ["managed.txt"]
    assert [item["path"] for item in update_plan["add"]] == ["new.txt"]
    assert [item["path"] for item in update_plan["preserve"]] == ["project.json"]
    assert [item["path"] for item in update_plan["conflicts"]] == ["generated.toml"]
    assert update_plan["atomicBlocked"] is True

    adoption = temp / "adoption"
    adoption.mkdir()
    write(adoption / "managed.txt", "existing project file\n")
    adoption_plan = plan_files(
        mode="adoption",
        project_root=adoption,
        source_root=source,
        target_manifest=manifest,
        installed_metadata=None,
    )
    assert [item["path"] for item in adoption_plan["conflicts"]] == ["managed.txt"]
    assert {item["path"] for item in adoption_plan["add"]} == {
        "generated.toml",
        "new.txt",
        "project.json",
    }
    assert adoption_plan["atomicBlocked"] is False

    transaction = transaction_directory(project, "tx-test")
    assert not transaction.is_relative_to(project)
    os.environ["XDG_STATE_HOME"] = str(project / ".state")
    try:
        try:
            transaction_directory(project, "tx-inside")
        except LifecycleError as error:
            assert "outside the working tree" in str(error)
        else:
            raise AssertionError("in-worktree transaction storage was accepted")
    finally:
        os.environ.pop("XDG_STATE_HOME", None)

    clean_project = temp / "clean-project"
    clean_project.mkdir()
    clean_plan = plan_files(
        mode="adoption",
        project_root=clean_project,
        source_root=source,
        target_manifest=manifest,
        installed_metadata=None,
    )
    report = apply_file_plan(
        project_root=clean_project,
        source_root=source,
        plan=clean_plan,
        transaction_root=transaction_directory(clean_project, "tx-apply"),
    )
    assert report["result"] == "applied"
    assert (clean_project / "managed.txt").read_text() == "target managed\n"

    rollback_project = temp / "rollback-project"
    rollback_project.mkdir()
    write(rollback_project / "managed.txt", "before\n")
    rollback_plan = {
        "mode": "update",
        "add": [{"path": "new.txt"}],
        "replace": [{"path": "managed.txt"}],
        "retire": [],
        "preserve": [],
        "conflicts": [],
        "atomicBlocked": False,
    }
    os.environ["APH_TEST_FAIL_AFTER_WRITES"] = "1"
    try:
        try:
            apply_file_plan(
                project_root=rollback_project,
                source_root=source,
                plan=rollback_plan,
                transaction_root=transaction_directory(rollback_project, "tx-rollback"),
            )
        except LifecycleError:
            pass
        else:
            raise AssertionError("injected transactional failure was accepted")
    finally:
        os.environ.pop("APH_TEST_FAIL_AFTER_WRITES", None)
    assert (rollback_project / "managed.txt").read_text() == "before\n"
    assert not (rollback_project / "new.txt").exists()

    retired_project_owned = temp / "retired-project-owned"
    retired_project_owned.mkdir()
    write(retired_project_owned / "owned.txt", "project facts\n")
    retired_plan = plan_files(
        mode="update",
        project_root=retired_project_owned,
        source_root=source,
        target_manifest=manifest,
        installed_metadata={
            "managedFiles": {
                "owned.txt": {
                    "ownership": "project-owned",
                    "baselineSha256": digest(retired_project_owned / "owned.txt"),
                }
            }
        },
    )
    assert "owned.txt" not in {item["path"] for item in retired_plan["retire"]}
    assert "owned.txt" in {item["path"] for item in retired_plan["preserve"]}

    symlink_source = temp / "symlink-source"
    symlink_source.mkdir()
    write(symlink_source / "nested/managed.txt", "managed\n")
    symlink_manifest = manifest_for(
        symlink_source, {"nested/managed.txt": "harness-managed"}
    )
    symlink_project = temp / "symlink-project"
    symlink_project.mkdir()
    (symlink_project / "user-area").mkdir()
    (symlink_project / "nested").symlink_to("user-area")
    try:
        plan_files(
            mode="adoption",
            project_root=symlink_project,
            source_root=symlink_source,
            target_manifest=symlink_manifest,
            installed_metadata=None,
        )
    except LifecycleError as error:
        assert "symbolic link" in str(error)
    else:
        raise AssertionError("managed path through a project symlink was accepted")

    prompt = build_cleanup_prompt(
        {
            "projectName": "Lifecycle Test",
            "fromVersion": "0.4.0",
            "toVersion": "0.5.0",
            "fromStateSchema": 0,
            "toStateSchema": 1,
            "transactionId": "tx-prompt",
            "reportPath": "/tmp/report.json",
            "backupPath": "/tmp/backup",
            "preservedLegacyFiles": ["docs/backlog.md"],
            "conflicts": ["AGENTS.md"],
            "manualActions": ["Merge the AGENTS map"],
            "releaseUrl": "https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.5.0",
            "compareUrl": "https://github.com/FabienGreard/agentic-project-harness/compare/v0.4.0...v0.5.0",
            "fileLinks": [
                "https://github.com/FabienGreard/agentic-project-harness/blob/v0.5.0/AGENTS.md"
            ],
        }
    )
    for expected in (
        "tx-prompt",
        "docs/backlog.md",
        "AGENTS.md",
        "v0.4.0...v0.5.0",
        "Do not delete legacy files or the rollback backup",
    ):
        assert expected in prompt


help_result = subprocess.run(
    ["bash", str(ROOT / "install.sh"), "--help"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
)
for command in ("install.sh", "install.sh status", "install.sh update"):
    assert command in help_result.stdout
for removed in ("--project-name", "--target", "--ref", "--dry-run", "finalize", "cleanup"):
    assert removed not in help_result.stdout

print("PASS: lifecycle metadata, planning, rollback, prompt, and CLI smoke completed")
