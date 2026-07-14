#!/usr/bin/env python3
"""End-to-end local, stable, adoption, migration, and rollback smoke."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_TOOL = ROOT / "tools/release_bundle.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))
from codex_config_contract import assert_codex_config  # type: ignore[import-not-found]


def run(
    *args: str | Path,
    cwd: Path,
    env: dict[str, str] | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {process.returncode}: {' '.join(map(str, args))}\n"
            f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    return process


def payload(process: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(process.stdout)


def copy_candidate(
    destination: Path,
    version: str,
    marker: str,
    *,
    legacy_layout: bool = False,
    team_renderer_marker: str | None = None,
) -> Path:
    ignored = shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc")
    shutil.copytree(ROOT, destination, symlinks=True, ignore=ignored)
    (destination / "VERSION").write_text(version + "\n", encoding="utf-8")
    metadata = json.loads((destination / ".agent-harness.json").read_text(encoding="utf-8"))
    metadata["harnessVersion"] = version
    (destination / ".agent-harness.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "HARNESS.md").write_text(
        (destination / "HARNESS.md").read_text(encoding="utf-8")
        + f"\nSynthetic release marker: {marker}\n",
        encoding="utf-8",
    )
    if team_renderer_marker:
        team_tool = destination / "tools/harness_team.py"
        team_tool.write_text(
            team_tool.read_text(encoding="utf-8").replace(
                "You are a Consultant serving as",
                f"Team renderer {team_renderer_marker}. You are a Consultant serving as",
            ),
            encoding="utf-8",
        )
        run(
            sys.executable,
            "-c",
            "import json,sys; from pathlib import Path; sys.path.insert(0, 'tools'); "
            "from harness_team import configure_existing_team; root=Path('.').resolve(); "
            "team=json.loads((root/'docs/state/team.json').read_text()); "
            "metadata=json.loads((root/'.agent-harness.json').read_text()); "
            "configure_existing_team(project_root=root, team=team, reasoning=metadata['reasoning'])",
            cwd=destination,
        )
    if legacy_layout:
        shutil.rmtree(destination / "docs/state")
        (destination / "docs/index.html").unlink()
        (destination / "tools/harness_lifecycle.py").unlink()
        agents = destination / ".codex/agents"
        for path in agents.glob("*.toml"):
            path.unlink()
        legacy_roles = {
            "project-director.toml": ("project_director", "high"),
            "delivery-lead.toml": ("delivery_lead", "high"),
            "specialist-lead.toml": ("specialist_lead", "high"),
            "execution-worker.toml": ("execution_worker", "medium"),
            "harness-evaluator.toml": ("harness_evaluator", "xhigh"),
        }
        for filename, (name, reasoning) in legacy_roles.items():
            (agents / filename).write_text(
                f'name = "{name}"\n'
                f'description = "Synthetic legacy role fixture"\n'
                f'model_reasoning_effort = "{reasoning}"\n'
                'developer_instructions = """Legacy fixture only."""\n',
                encoding="utf-8",
            )
        legacy_state = {
            "templateMode": True,
            "project": {
                "name": "Project name",
                "agentProvider": "codex",
                "phase": "Needs Definition",
                "lastVerified": "",
            },
            "baton": {
                "owner": "Management",
                "action": "Define the first Ready ticket",
                "returnTrigger": "A bounded Ready ticket is recorded",
            },
            "tickets": [
                {
                    "id": "LEGACY-001",
                    "title": "Preserve a legacy human review",
                    "status": "Backlog",
                    "priority": "P2",
                    "owner": "Management",
                    "dependencies": [],
                    "requiresHumanReview": True,
                    "blockers": [],
                    "openDecisions": [],
                }
            ],
            "activeWork": [],
            "humanReviews": [],
        }
        (destination / "docs/project-state.json").write_text(
            json.dumps(legacy_state, indent=2) + "\n", encoding="utf-8"
        )
    run("git", "init", "-q", "-b", "main", cwd=destination)
    run("git", "config", "user.email", "smoke@example.test", cwd=destination)
    run("git", "config", "user.name", "Harness Smoke", cwd=destination)
    run("git", "add", ".", cwd=destination)
    run("git", "commit", "-qm", f"fixture {version}", cwd=destination)
    run("git", "tag", f"v{version}", cwd=destination)
    return destination


def build_bundle(
    source: Path,
    output: Path,
    version: str,
    origins: list[tuple[str, Path, Path | None]],
) -> None:
    arguments: list[str | Path] = [
        sys.executable,
        BUNDLE_TOOL,
        "build",
        "--source",
        source,
        "--output",
        output,
        "--tag",
        f"v{version}",
        "--state-schema-version",
        "1",
    ]
    for origin_version, origin_source, origin_bundle in origins:
        commit = run(
            "git", "-C", origin_source, "rev-parse", "HEAD", cwd=ROOT
        ).stdout.strip()
        specification = f"v{origin_version}={commit}"
        if origin_bundle is not None:
            manifest_digest = hashlib.sha256(
                (origin_bundle / "harness-manifest.json").read_bytes()
            ).hexdigest()
            specification += f",{manifest_digest}"
        arguments.extend(("--supported-upgrade-origin", specification))
    run(*arguments, cwd=ROOT)


def assert_install(root: Path, version: str, status: str = "Installed") -> dict:
    metadata = json.loads((root / ".agent-harness.json").read_text(encoding="utf-8"))
    assert metadata["schemaVersion"] == 2
    assert metadata["harnessVersion"] == version
    assert metadata["installationStatus"] == status
    assert metadata["stateSchemaVersion"] == 1
    assert metadata["provider"] == "codex"
    assert_codex_config(root / ".codex/config.toml")
    assert (root / ".codex/skills").is_symlink()
    assert (root / ".codex/skills").resolve() == (root / ".agents/skills").resolve()
    assert (root / "docs/index.html").is_file()
    project = json.loads(
        (root / "docs/state/project.json").read_text(encoding="utf-8")
    )["project"]
    assert project["assuranceDefaults"] == {
        "testRigor": "Standard",
        "humanReviewStages": [],
    }
    team = json.loads((root / "docs/state/team.json").read_text(encoding="utf-8"))
    assert team["preset"] in {
        "game-development", "software-product", "business-operations", "research"
    }
    team_check = run(
        sys.executable, root / "tools/harness_team.py", "check", "--json", cwd=root
    )
    assert payload(team_check)["ok"] is True
    state_check = run(
        sys.executable, root / "tools/harness_state.py", "check", "--json", cwd=root
    )
    assert payload(state_check)["ok"] is True
    assert not (root / "hire").exists() and not (root / "fire").exists()
    assert (root / ".agents/skills/hire-consultant/SKILL.md").is_file()
    assert (root / ".agents/skills/fire-consultant/SKILL.md").is_file()
    assert not (root / "BOOTSTRAP_PROMPT.md").exists()
    return metadata


def file_snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or path.is_dir():
            continue
        if path.is_symlink():
            content = os.readlink(path).encode()
        else:
            content = path.read_bytes()
        result[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    return result


def install_from_bundle(bundle: Path, target: Path) -> dict:
    target.mkdir()
    result = run(
        "bash",
        bundle / "install.sh",
        "--yes",
        "--json",
        cwd=target,
        env={"APH_RELEASE_DIR": str(bundle)},
    )
    return payload(result)


def write_legacy_metadata(project: Path, version: str) -> None:
    current = json.loads((project / ".agent-harness.json").read_text(encoding="utf-8"))
    current_reasoning = current["reasoning"]
    legacy = {
        "schemaVersion": 1,
        "harnessVersion": version,
        "provider": "codex",
        "source": "FabienGreard/agentic-project-harness",
        "ref": f"v{version}",
        "sourceMode": "remote",
        "installed": True,
        "installedAt": current["installedAt"],
        "projectType": current["projectType"],
        "reasoningPreset": current["reasoningPreset"],
        "reasoning": {
            "projectDirector": current_reasoning["management"],
            "deliveryLead": current_reasoning["operations"],
            "specialistLead": current_reasoning["consultants"],
            "executionWorker": current_reasoning["contractors"],
            "harnessEvaluator": current_reasoning["internalAudit"],
        },
    }
    (project / ".agent-harness.json").write_text(
        json.dumps(legacy, indent=2) + "\n", encoding="utf-8"
    )


with tempfile.TemporaryDirectory(prefix="aph-install-update-") as raw:
    temp = Path(raw)
    os.environ["XDG_STATE_HOME"] = str(temp / "external-state")

    local = temp / "local-folder-name"
    local.mkdir()
    local_result = payload(
        run("bash", ROOT / "install.sh", "--yes", "--json", cwd=local)
    )
    assert local_result["mode"] == "install"
    local_metadata = assert_install(local, "0.5.0")
    assert local_metadata["projectName"] == "local-folder-name"
    assert local_metadata["source"]["channel"] == "local-development"
    assert local_metadata["reasoningPreset"] == "medium"
    assert local_metadata["reasoning"] == {
        "management": "high",
        "operations": "high",
        "consultants": "high",
        "contractors": "medium",
        "internalAudit": "xhigh",
    }
    status = payload(run("bash", local / "install.sh", "status", "--json", cwd=local))
    assert status["installedVersion"] == "0.5.0"
    assert status["integrity"]["modified"] == []
    assert status["team"] == {
        "preset": "software-product",
        "presetLabel": "Software Product",
        "management": "Product Manager",
        "operations": "Engineering Manager",
        "activeConsultants": ["Product Designer"],
    }

    failed_install = temp / "failed-install"
    failed_install.mkdir()
    install_failure = run(
        "bash", ROOT / "install.sh", "--yes", "--json",
        cwd=failed_install, env={"APH_TEST_FAIL_AFTER_WRITES": "2"}, expected=1,
    )
    assert "injected lifecycle failure" in payload(install_failure)["error"]
    assert list(failed_install.iterdir()) == []

    failed_install_finalization = temp / "failed-install-finalization"
    failed_install_finalization.mkdir()
    finalization_failure = run(
        "bash", ROOT / "install.sh", "--yes", "--json",
        cwd=failed_install_finalization,
        env={"APH_TEST_FAIL_FINAL_REPORT": "1"},
        expected=1,
    )
    assert "final transaction report failure" in payload(finalization_failure)["error"]
    assert list(failed_install_finalization.iterdir()) == []

    failed_adoption = temp / "failed-adoption"
    failed_adoption.mkdir()
    (failed_adoption / "user.txt").write_text("preserve\n", encoding="utf-8")
    before_failed_adoption = file_snapshot(failed_adoption)
    adoption_failure = run(
        "bash", ROOT / "install.sh", "--yes", "--json",
        cwd=failed_adoption, env={"APH_TEST_FAIL_AFTER_WRITES": "2"}, expected=1,
    )
    assert "injected lifecycle failure" in payload(adoption_failure)["error"]
    assert file_snapshot(failed_adoption) == before_failed_adoption
    assert {path.name for path in failed_adoption.iterdir()} == {"user.txt"}

    source04 = copy_candidate(temp / "source-04", "0.4.0", "baseline")
    source03 = copy_candidate(
        temp / "source-03", "0.3.0", "legacy", legacy_layout=True
    )
    source05 = copy_candidate(
        temp / "source-05", "0.5.0", "target", team_renderer_marker="v2"
    )
    source06 = copy_candidate(
        temp / "source-06", "0.6.0", "next", team_renderer_marker="v2"
    )
    bundle03, bundle04 = temp / "bundle-03", temp / "bundle-04"
    bundle05, bundle06 = temp / "bundle-05", temp / "bundle-06"
    build_bundle(source03, bundle03, "0.3.0", [("0.2.0", source03, None)])
    build_bundle(source04, bundle04, "0.4.0", [("0.3.0", source03, bundle03)])
    build_bundle(
        source05,
        bundle05,
        "0.5.0",
        [
            ("0.3.0", source03, bundle03),
            ("0.4.0", source04, bundle04),
        ],
    )
    build_bundle(source06, bundle06, "0.6.0", [("0.5.0", source05, bundle05)])

    piped = temp / "piped-stable"
    result = install_from_bundle(bundle04, piped)
    assert result["mode"] == "install" and result["version"] == "0.4.0"
    assert_install(piped, "0.4.0")
    hired_before_update = payload(
        run(
            sys.executable, piped / "tools/harness_team.py", "hire", "--project-root", piped,
            "--consultant", "security-lead", "--yes", "--json",
            cwd=piped,
        )
    )
    assert hired_before_update["consultant"]["id"] == "security-lead"
    project_record = json.loads(
        (piped / "docs/state/project.json").read_text(encoding="utf-8")
    )
    project_record["project"]["phase"] = "Configured for update smoke"
    state_operation = temp / "state-operation.json"
    state_operation.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "operation": "replace-records",
                "records": {"project": project_record},
            }
        ),
        encoding="utf-8",
    )
    payload(
        run(
            sys.executable,
            piped / "tools/harness_state.py",
            "apply",
            state_operation,
            "--json",
            cwd=piped,
        )
    )
    update_review_packet = piped / "docs/review-packets/UPDATE-REVIEW.md"
    update_review_packet.write_text(
        "# Approved release review\n\nPreserved project-owned evidence.\n",
        encoding="utf-8",
    )
    project_proof = piped / "project-proof.txt"
    project_proof.write_text(
        "Custom target-absent project evidence.\n", encoding="utf-8"
    )
    project_proof_before = project_proof.read_bytes()
    update_tickets = json.loads(
        (piped / "docs/state/tickets.json").read_text(encoding="utf-8")
    )
    update_goals = json.loads(
        (piped / "docs/state/goals.json").read_text(encoding="utf-8")
    )
    update_goals["goals"].append(
        {
            "id": "UPDATE-EVIDENCE-GOAL",
            "title": "Preserve linked update evidence",
            "status": "Done",
            "priority": "P2",
            "owner": "Management",
            "objective": "Verify linked evidence survives stable update validation",
            "context": "Update hydration must not replace managed target bytes",
            "dependencies": [],
            "blockers": [],
            "decisionPaths": [],
            "evidencePaths": [
                "HARNESS.md",
                "docs/review-packets/README.md",
                "project-proof.txt",
            ],
            "resultSummary": "The installed project recorded update evidence",
            "completedAt": "2026-07-14",
        }
    )
    update_tickets["tickets"].append(
        {
            "id": "UPDATE-EVIDENCE",
            "title": "Preserve approved update evidence",
            "status": "Backlog",
            "priority": "P2",
            "owner": "Management",
            "dependencies": [],
            "requiredConsultantIds": [],
            "assurance": {
                "testRigor": "Standard",
                "humanReviewStages": ["Release"],
                "overrideReason": "Human approval is required before release",
            },
            "blockers": [],
            "openDecisions": [],
        }
    )
    update_reviews = json.loads(
        (piped / "docs/state/reviews.json").read_text(encoding="utf-8")
    )
    update_reviews["reviews"].append(
        {
            "id": "UPDATE-EVIDENCE-release",
            "ticket": "UPDATE-EVIDENCE",
            "stage": "Release",
            "status": "Approved",
            "path": "docs/review-packets/UPDATE-REVIEW.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-14",
        }
    )
    update_evidence_operation = temp / "update-evidence-operation.json"
    update_evidence_operation.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "operation": "replace-records",
                "records": {
                    "goals": update_goals,
                    "tickets": update_tickets,
                    "reviews": update_reviews,
                },
            }
        ),
        encoding="utf-8",
    )
    payload(
        run(
            sys.executable,
            piped / "tools/harness_state.py",
            "apply",
            update_evidence_operation,
            "--json",
            cwd=piped,
        )
    )
    update_review_packet_before = update_review_packet.read_bytes()
    missing_evidence = temp / "missing-installed-evidence"
    shutil.copytree(piped, missing_evidence, symlinks=True)
    missing_packet = missing_evidence / "docs/review-packets/README.md"
    missing_packet.unlink()
    missing_metadata_before = (missing_evidence / ".agent-harness.json").read_bytes()
    rejected_missing_evidence = run(
        "bash",
        missing_evidence / "install.sh",
        "update",
        "--yes",
        "--json",
        cwd=missing_evidence,
        env={
            "APH_RELEASE_DIR": str(bundle05),
            "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
        },
        expected=1,
    )
    assert "installed state evidence is missing or not a regular file" in (
        rejected_missing_evidence.stdout + rejected_missing_evidence.stderr
    )
    assert not missing_packet.exists()
    assert (
        missing_evidence / ".agent-harness.json"
    ).read_bytes() == missing_metadata_before
    post_state_status = payload(
        run("bash", piped / "install.sh", "status", "--json", cwd=piped)
    )
    assert post_state_status["integrity"]["modified"] == []
    original_readme = (piped / "README.md").read_bytes()
    updated = payload(
        run(
            "bash", piped / "install.sh", "update", "--yes", "--json",
            cwd=piped,
            env={
                "APH_RELEASE_DIR": str(bundle05),
                "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
            },
        )
    )
    assert updated["mode"] == "update" and updated["version"] == "0.5.0"
    assert updated["upToDate"] is False
    assert (piped / "README.md").read_bytes() == original_readme
    assert "Synthetic release marker: target" in (piped / "HARNESS.md").read_text(encoding="utf-8")
    assert update_review_packet.read_bytes() == update_review_packet_before
    assert project_proof.read_bytes() == project_proof_before
    updated_reviews = json.loads(
        (piped / "docs/state/reviews.json").read_text(encoding="utf-8")
    )
    assert any(
        review.get("id") == "UPDATE-EVIDENCE-release"
        and review.get("status") == "Approved"
        for review in updated_reviews["reviews"]
    )
    updated_goals = json.loads(
        (piped / "docs/state/goals.json").read_text(encoding="utf-8")
    )
    assert any(
        goal.get("id") == "UPDATE-EVIDENCE-GOAL"
        and goal.get("evidencePaths")
        == [
            "HARNESS.md",
            "docs/review-packets/README.md",
            "project-proof.txt",
        ]
        for goal in updated_goals["goals"]
    )
    assert_install(piped, "0.5.0")
    updated_team = json.loads(
        (piped / "docs/state/team.json").read_text(encoding="utf-8")
    )
    assert {
        item["id"] for item in updated_team["consultants"] if item["status"] == "active"
    } == {"product-designer", "security-lead"}
    assert (piped / ".codex/agents/consultant-security-lead.toml").is_file()
    for consultant in updated_team["consultants"]:
        if consultant["status"] != "active":
            continue
        config = piped / consultant["configPath"]
        assert "Team renderer v2" in config.read_text(encoding="utf-8")
        assert consultant["configBaselineSha256"] == hashlib.sha256(
            config.read_bytes()
        ).hexdigest()
    rerun = payload(
        run(
            "bash", bundle05 / "install.sh", "--yes", "--json",
            cwd=piped, env={"APH_RELEASE_DIR": str(bundle05)},
        )
    )
    assert rerun["upToDate"] is True and rerun["version"] == "0.5.0"
    preserved_security_config = piped / ".codex/agents/consultant-security-lead.toml"
    preserved_security_config.write_text(
        preserved_security_config.read_text(encoding="utf-8")
        + "\n# Project-owned post-hire policy\n",
        encoding="utf-8",
    )
    fired_security = payload(
        run(
            sys.executable, piped / "tools/harness_team.py", "fire", "--project-root", piped,
            "--consultant", "security-lead", "--yes", "--json",
            cwd=piped,
        )
    )
    assert fired_security["manualCleanupRequired"] is True
    post_fire_metadata = json.loads(
        (piped / ".agent-harness.json").read_text(encoding="utf-8")
    )
    assert post_fire_metadata["managedFiles"][
        ".codex/agents/consultant-security-lead.toml"
    ]["ownership"] == "project-owned"
    payload(
        run(
            "bash", piped / "install.sh", "update", "--yes", "--json",
            cwd=piped,
            env={
                "APH_RELEASE_DIR": str(bundle06),
                "APH_PINNED_STABLE_SOURCE_DIR": str(source05),
            },
        )
    )
    assert_install(piped, "0.6.0")
    assert "Project-owned post-hire policy" in preserved_security_config.read_text(
        encoding="utf-8"
    )

    adopted = temp / "adopted"
    adopted.mkdir()
    user_readme = b"# Existing project\n\nUser-owned facts.\n"
    (adopted / "README.md").write_bytes(user_readme)
    (adopted / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    (adopted / "user.txt").write_text("keep me\n", encoding="utf-8")
    adoption = payload(
        run(
            "bash", bundle05 / "install.sh", "--yes", "--json",
            cwd=adopted, env={"APH_RELEASE_DIR": str(bundle05)},
        )
    )
    assert adoption["mode"] == "adoption"
    assert set(adoption["conflicts"]) >= {"AGENTS.md", "README.md"}
    assert (adopted / "README.md").read_bytes() == user_readme
    assert (adopted / "user.txt").read_text(encoding="utf-8") == "keep me\n"
    adoption_metadata = assert_install(adopted, "0.5.0", "Needs Integration")
    assert {item["path"] for item in adoption_metadata["pendingIntegration"]} >= {"AGENTS.md", "README.md"}
    shutil.copy2(source05 / "AGENTS.md", adopted / "AGENTS.md")
    finalized = payload(
        run(
            "bash", adopted / "install.sh", "update", "--yes", "--json",
            cwd=adopted, env={"APH_RELEASE_DIR": str(bundle05)},
        )
    )
    assert finalized["mode"] == "integration-finalize"
    finalized_metadata = assert_install(adopted, "0.5.0")
    assert finalized_metadata["managedFiles"]["README.md"]["ownership"] == "project-owned"
    assert finalized_metadata["managedFiles"]["AGENTS.md"]["ownership"] == "project-owned"
    (adopted / "README.md").write_bytes(user_readme + b"More user facts.\n")
    payload(
        run(
            "bash", adopted / "install.sh", "update", "--yes", "--json",
            cwd=adopted,
            env={
                "APH_RELEASE_DIR": str(bundle06),
                "APH_PINNED_STABLE_SOURCE_DIR": str(source05),
            },
        )
    )
    assert (adopted / "README.md").read_bytes() == user_readme + b"More user facts.\n"
    adopted_v06 = assert_install(adopted, "0.6.0")
    assert adopted_v06["managedFiles"]["AGENTS.md"]["ownership"] == "project-owned"

    conflict = temp / "conflict"
    install_from_bundle(bundle04, conflict)
    (conflict / "HARNESS.md").write_text("project customization\n", encoding="utf-8")
    before_conflict = file_snapshot(conflict)
    blocked = run(
        "bash", conflict / "install.sh", "update", "--yes", "--json",
        cwd=conflict,
        env={
            "APH_RELEASE_DIR": str(bundle05),
            "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
        },
        expected=1,
    )
    assert "update blocked" in payload(blocked)["error"]
    assert file_snapshot(conflict) == before_conflict

    tampered_baseline = temp / "tampered-baseline"
    install_from_bundle(bundle04, tampered_baseline)
    (tampered_baseline / "HARNESS.md").write_text(
        "local work falsely blessed by metadata\n", encoding="utf-8"
    )
    tampered_metadata = json.loads(
        (tampered_baseline / ".agent-harness.json").read_text(encoding="utf-8")
    )
    tampered_metadata["managedFiles"]["HARNESS.md"]["baselineSha256"] = hashlib.sha256(
        (tampered_baseline / "HARNESS.md").read_bytes()
    ).hexdigest()
    (tampered_baseline / ".agent-harness.json").write_text(
        json.dumps(tampered_metadata, indent=2) + "\n", encoding="utf-8"
    )
    before_tampered_baseline = file_snapshot(tampered_baseline)
    rejected_tampered_baseline = run(
        "bash", tampered_baseline / "install.sh", "update", "--yes", "--json",
        cwd=tampered_baseline,
        env={
            "APH_RELEASE_DIR": str(bundle05),
            "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
        },
        expected=1,
    )
    assert "baseline provenance cannot be verified" in payload(
        rejected_tampered_baseline
    )["error"]
    assert file_snapshot(tampered_baseline) == before_tampered_baseline

    rollback = temp / "rollback"
    install_from_bundle(bundle04, rollback)
    before_rollback = file_snapshot(rollback)
    failed = run(
        "bash", rollback / "install.sh", "update", "--yes", "--json",
        cwd=rollback,
        env={
            "APH_RELEASE_DIR": str(bundle05),
            "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
            "APH_TEST_FAIL_AFTER_WRITES": "2",
        },
        expected=1,
    )
    assert "injected lifecycle failure" in payload(failed)["error"]
    assert file_snapshot(rollback) == before_rollback

    final_report_rollback = temp / "final-report-rollback"
    install_from_bundle(bundle04, final_report_rollback)
    before_final_report_rollback = file_snapshot(final_report_rollback)
    failed_final_report = run(
        "bash", final_report_rollback / "install.sh", "update", "--yes", "--json",
        cwd=final_report_rollback,
        env={
            "APH_RELEASE_DIR": str(bundle05),
            "APH_PINNED_STABLE_SOURCE_DIR": str(source04),
            "APH_TEST_FAIL_FINAL_REPORT": "1",
        },
        expected=1,
    )
    assert "update finalization failed" in payload(failed_final_report)["error"]
    after_final_report_rollback = file_snapshot(final_report_rollback)
    assert after_final_report_rollback == before_final_report_rollback, {
        "added": sorted(after_final_report_rollback.keys() - before_final_report_rollback.keys()),
        "removed": sorted(before_final_report_rollback.keys() - after_final_report_rollback.keys()),
        "changed": sorted(
            path
            for path in before_final_report_rollback.keys() & after_final_report_rollback.keys()
            if before_final_report_rollback[path] != after_final_report_rollback[path]
        ),
    }

    legacy = temp / "legacy"
    shutil.copytree(
        source03,
        legacy,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
    )
    write_legacy_metadata(legacy, "0.3.0")
    legacy_state_before = (legacy / "docs/project-state.json").read_bytes()
    migrated = payload(
        run(
            "bash", bundle05 / "install.sh", "--yes", "--json",
            cwd=legacy,
            env={
                "APH_RELEASE_DIR": str(bundle05),
                "APH_PINNED_STABLE_SOURCE_DIR": str(source03),
            },
        )
    )
    assert migrated["version"] == "0.5.0"
    assert "docs/project-state.json" in migrated["preservedLegacyFiles"]
    assert (legacy / "docs/project-state.json").read_bytes() == legacy_state_before
    assert_install(legacy, "0.5.0")
    migrated_ticket = json.loads(
        (legacy / "docs/state/tickets.json").read_text(encoding="utf-8")
    )["tickets"][0]
    assert migrated_ticket["assurance"] == {
        "testRigor": "Standard",
        "humanReviewStages": ["Acceptance"],
        "overrideReason": "Migrated legacy human-review requirement",
    }
    state_check = payload(
        run(sys.executable, legacy / "tools/harness_state.py", "check", "--json", cwd=legacy)
    )
    assert state_check["ok"] is True

    legacy_without_specialist = temp / "legacy-without-specialist"
    shutil.copytree(
        source03,
        legacy_without_specialist,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
    )
    write_legacy_metadata(legacy_without_specialist, "0.3.0")
    no_specialist_metadata = json.loads(
        (legacy_without_specialist / ".agent-harness.json").read_text(encoding="utf-8")
    )
    no_specialist_metadata["reasoning"]["specialistLead"] = None
    (legacy_without_specialist / ".agent-harness.json").write_text(
        json.dumps(no_specialist_metadata, indent=2) + "\n", encoding="utf-8"
    )
    (legacy_without_specialist / ".codex/agents/specialist-lead.toml").unlink()
    payload(
        run(
            "bash", bundle05 / "install.sh", "--yes", "--json",
            cwd=legacy_without_specialist,
            env={
                "APH_RELEASE_DIR": str(bundle05),
                "APH_PINNED_STABLE_SOURCE_DIR": str(source03),
            },
        )
    )
    migrated_without_specialist = assert_install(legacy_without_specialist, "0.5.0")
    assert (legacy_without_specialist / ".codex/agents/consultant-product-designer.toml").is_file()
    assert "preset-team-v1" in {
        item["id"] for item in migrated_without_specialist["appliedMigrations"]
    }

print("PASS: local, stable, adoption, update, migration, conflict, and rollback smoke completed")
