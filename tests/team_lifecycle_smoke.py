#!/usr/bin/env python3
"""Contract smoke for preset-driven teams and transactional Consultant lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from harness_team import parse_role_config  # type: ignore[import-not-found]


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tools" / "team-presets.json"
EXPECTED_PRESETS = {
    "game-development": ("Game Director", "Producer", "art-director"),
    "software-product": ("Product Manager", "Engineering Manager", "product-designer"),
    "business-operations": ("Program Director", "Operations Manager", "change-manager"),
    "research": ("Principal Investigator", "Research Program Manager", "research-methodologist"),
}
REQUIRED_NON_AUTHORITIES = {
    "overall priority",
    "Contractor dispatch",
    "technical integration",
    "publication",
}


def run(
    *args: str,
    cwd: Path,
    expected: int = 0,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {completed.returncode}: {' '.join(args)}\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
        )
    return completed


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_consultants(team: dict) -> dict[str, dict]:
    return {
        consultant["id"]: consultant
        for consultant in team["consultants"]
        if consultant["status"] == "active"
    }


def team_command(project: Path, action: str, *args: str) -> tuple[str, ...]:
    return (
        sys.executable,
        str(project / "tools/harness_team.py"),
        action,
        "--project-root",
        str(project),
        *args,
    )


def assert_catalog() -> None:
    catalog = read_json(CATALOG)
    assert catalog["schemaVersion"] == 1
    assert set(catalog["presets"]) == set(EXPECTED_PRESETS)
    assert "other" not in catalog["presets"] and "custom" not in catalog["presets"]
    for preset_id, (management, operations, default_consultant) in EXPECTED_PRESETS.items():
        preset = catalog["presets"][preset_id]
        assert preset["management"]["title"] == management
        assert preset["operations"]["title"] == operations
        assert preset["defaultConsultants"] == [default_consultant]
        assert len(preset["contractorBench"]) >= 3
        consultant_ids = {consultant["id"] for consultant in preset["consultants"]}
        assert default_consultant in consultant_ids
        for consultant in preset["consultants"]:
            assert consultant["title"] and consultant["headline"] and consultant["domain"]
            assert consultant["readinessRequirements"] and consultant["evidenceRequirements"]
            assert consultant["acceptanceAuthority"]


def assert_installed_team(project: Path) -> None:
    team = read_json(project / "docs/state/team.json")
    assert team["schemaVersion"] == 1 and team["recordType"] == "team"
    assert team["preset"] == "software-product"
    assert team["management"]["title"] == "Product Manager"
    assert team["operations"]["title"] == "Engineering Manager"
    assert set(active_consultants(team)) == {"product-designer"}
    assert team["internalAudit"]["projectTeamMember"] is False
    assert len(team["contractorBench"]) >= 3
    expected_configs = {
        "management.toml",
        "operations.toml",
        "contractor.toml",
        "internal-audit.toml",
        "consultant-product-designer.toml",
    }
    configs = {path.name for path in (project / ".codex/agents").glob("*.toml")}
    assert configs == expected_configs
    assert "Product Manager" in (project / ".codex/agents/management.toml").read_text(encoding="utf-8")
    assert "Engineering Manager" in (project / ".codex/agents/operations.toml").read_text(encoding="utf-8")
    assert "Product Designer" in (
        project / ".codex/agents/consultant-product-designer.toml"
    ).read_text(encoding="utf-8")
    assert not (project / ".codex/agents/specialist-lead.toml").exists()


def main() -> int:
    assert_catalog()
    with tempfile.TemporaryDirectory(prefix="aph-team-smoke-") as temporary:
        state_home = Path(temporary) / "external-state"
        os.environ["XDG_STATE_HOME"] = str(state_home)
        project = Path(temporary) / "product"
        project.mkdir()
        install = run("bash", str(ROOT / "install.sh"), "--yes", "--json", cwd=project)
        assert json.loads(install.stdout)["ok"] is True
        assert_installed_team(project)
        assert not (project / "hire").exists() and not (project / "fire").exists()

        lock_id = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:16]
        lock_path = (
            Path("/tmp").resolve()
            / f"agentic-project-harness-{os.getuid()}"
            / lock_id
            / "mutation.lock"
        )
        lock_path.unlink()
        sentinel = Path(temporary) / "do-not-truncate.txt"
        sentinel.write_text("preserve me\n", encoding="utf-8")
        lock_path.symlink_to(sentinel)
        team_before_symlink_lock = digest(project / "docs/state/team.json")
        rejected_symlink_lock = run(
            *team_command(
                project, "hire", "--consultant", "security-lead", "--yes", "--json"
            ),
            cwd=project,
            expected=1,
        )
        assert "symbolic link" in json.loads(rejected_symlink_lock.stdout)["error"]
        assert sentinel.read_text(encoding="utf-8") == "preserve me\n"
        assert digest(project / "docs/state/team.json") == team_before_symlink_lock
        lock_path.unlink()

        project_record = read_json(project / "docs/state/project.json")
        project_record["project"]["phase"] = "Cross-surface lock verified"
        state_operation = project / "cross-surface-operation.json"
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
        state_env = {
            **os.environ,
            "APH_TEST_HOLD_MUTATION_LOCK_MS": "300",
        }
        state_apply = subprocess.Popen(
            (
                sys.executable,
                str(project / "tools/harness_state.py"),
                "apply",
                str(state_operation),
                "--json",
            ),
            cwd=project,
            env=state_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.05)
        first_hire = subprocess.Popen(
            team_command(
                project, "hire", "--consultant", "security-lead", "--yes", "--json"
            ),
            cwd=project,
            env={**os.environ, "XDG_STATE_HOME": str(Path(temporary) / "state-a")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        second_hire = subprocess.Popen(
            team_command(
                project, "hire", "--consultant", "principal-engineer", "--yes", "--json"
            ),
            cwd=project,
            env={**os.environ, "XDG_STATE_HOME": str(Path(temporary) / "state-b")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        state_stdout, state_stderr = state_apply.communicate(timeout=10)
        first_stdout, first_stderr = first_hire.communicate(timeout=10)
        second_stdout, second_stderr = second_hire.communicate(timeout=10)
        assert state_apply.returncode == 0, state_stderr
        assert first_hire.returncode == 0, first_stderr
        assert second_hire.returncode == 0, second_stderr
        assert json.loads(state_stdout)["ok"] is True
        hired = json.loads(first_stdout)
        hired_second = json.loads(second_stdout)
        assert hired["ok"] is True and hired["consultant"]["id"] == "security-lead"
        assert hired_second["ok"] is True
        assert hired_second["consultant"]["id"] == "principal-engineer"
        security_config = project / ".codex/agents/consultant-security-lead.toml"
        assert security_config.is_file()
        team = read_json(project / "docs/state/team.json")
        assert set(active_consultants(team)) == {
            "product-designer", "security-lead", "principal-engineer"
        }
        assert read_json(project / "docs/state/project.json")["project"]["phase"] == (
            "Cross-surface lock verified"
        )

        custom_path = project / "accessibility-consultant.json"
        custom_path.write_text(
            json.dumps(
                {
                    "id": "inclusive-design-lead",
                    "title": "Inclusive Design Lead",
                    "headline": "Protects C:\\queue paths, quoted states, and accessible interaction quality.",
                    "domain": "inclusive design and accessibility",
                    "readinessRequirements": ["Affected users and applicable accessibility standards are named."],
                    "evidenceRequirements": ["Representative keyboard and assistive-technology evidence."],
                    "acceptanceAuthority": "Accepts or rejects work inside the approved inclusive-design boundary.",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        custom = json.loads(
            run(
                *team_command(
                    project, "hire", "--custom", str(custom_path), "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        assert custom["ok"] is True and custom["consultant"]["source"] == "custom"
        team = read_json(project / "docs/state/team.json")
        custom_record = active_consultants(team)["inclusive-design-lead"]
        assert set(custom_record["nonAuthorities"]) == REQUIRED_NON_AUTHORITIES
        custom_toml = parse_role_config(
            (project / custom_record["configPath"]).read_text(encoding="utf-8"),
            Path(custom_record["configPath"]).name,
        )
        assert "C:\\queue" in custom_toml["description"]

        before_duplicate = digest(project / "docs/state/team.json")
        duplicate = run(
            *team_command(
                project, "hire", "--consultant", "security-lead", "--yes", "--json"
            ),
            cwd=project,
            expected=1,
        )
        assert json.loads(duplicate.stdout)["ok"] is False
        assert digest(project / "docs/state/team.json") == before_duplicate

        fired = json.loads(
            run(
                *team_command(
                    project, "fire", "--consultant", "security-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        assert fired["ok"] is True and fired["manualCleanupRequired"] is False
        assert not security_config.exists()
        team = read_json(project / "docs/state/team.json")
        security_record = next(item for item in team["consultants"] if item["id"] == "security-lead")
        assert security_record["status"] == "inactive" and security_record["firedAt"]

        custom_config = project / ".codex/agents/consultant-inclusive-design-lead.toml"
        custom_config.write_text(
            custom_config.read_text(encoding="utf-8") + "\n# Project-owned note\n",
            encoding="utf-8",
        )
        preserved = json.loads(
            run(
                *team_command(
                    project, "fire", "--consultant", "inclusive-design-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        assert preserved["ok"] is True and preserved["manualCleanupRequired"] is True
        assert custom_config.is_file() and "Project-owned note" in custom_config.read_text(encoding="utf-8")
        team = read_json(project / "docs/state/team.json")
        custom_record = next(item for item in team["consultants"] if item["id"] == "inclusive-design-lead")
        assert custom_record["status"] == "inactive"
        assert custom_record["preservedConfig"] is True and custom_record["manualAction"]
        metadata = read_json(project / ".agent-harness.json")
        preserved_baseline = metadata["managedFiles"][
            ".codex/agents/consultant-inclusive-design-lead.toml"
        ]
        assert preserved_baseline["ownership"] == "project-owned"
        assert preserved_baseline["baselineSha256"] == digest(custom_config)
        assert metadata["managedFiles"]["docs/index.html"] == {
            "ownership": "generated-config",
            "baselineSha256": digest(project / "docs/index.html"),
        }

        json.loads(
            run(
                *team_command(
                    project, "hire", "--consultant", "platform-sre-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        missing_config = project / ".codex/agents/consultant-platform-sre-lead.toml"
        missing_config.unlink()
        reconciled = json.loads(
            run(
                *team_command(
                    project, "fire", "--consultant", "platform-sre-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        assert reconciled["reconciledMissingFiles"] == [
            ".codex/agents/consultant-platform-sre-lead.toml"
        ]
        assert ".codex/agents/consultant-platform-sre-lead.toml" not in read_json(
            project / ".agent-harness.json"
        )["managedFiles"]

        json.loads(
            run(
                *team_command(
                    project, "hire", "--consultant", "data-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        symlink_config = project / ".codex/agents/consultant-data-lead.toml"
        generated_data_config = symlink_config.read_bytes()
        symlink_config.unlink()
        symlink_config.symlink_to(custom_path)
        before_symlink_fire = digest(project / "docs/state/team.json")
        rejected_symlink = run(
            *team_command(
                project, "fire", "--consultant", "data-lead", "--yes", "--json"
            ),
            cwd=project,
            expected=1,
        )
        assert json.loads(rejected_symlink.stdout)["ok"] is False
        assert symlink_config.is_symlink()
        assert digest(project / "docs/state/team.json") == before_symlink_fire
        symlink_config.unlink()
        symlink_config.write_bytes(generated_data_config)
        json.loads(
            run(
                *team_command(
                    project, "fire", "--consultant", "data-lead", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )

        unexpected = project / ".codex/agents/consultant-ghost.toml"
        unexpected.write_text('name = "ghost"\n', encoding="utf-8")
        rejected_unexpected = run(
            *team_command(project, "check", "--json"),
            cwd=project,
            expected=1,
        )
        assert any(
            "unexpected Consultant agent config" in error
            for error in json.loads(rejected_unexpected.stdout)["errors"]
        )
        unexpected.unlink()

        report_path = project / "docs/implementation-reports/TEAM-1.md"
        report_path.write_text("# TEAM-1\n\nVerified historical work.\n", encoding="utf-8")
        evidence = "docs/implementation-reports/TEAM-1.md"
        historical_operation = project / "historical-consultant-operation.json"
        historical_operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {
                        "goals": {
                            "schemaVersion": 1,
                            "recordType": "goals",
                            "goals": [
                                {
                                    "id": "TEAM-GOAL",
                                    "title": "Prove historical Consultant records",
                                    "status": "Done",
                                    "priority": "P2",
                                    "owner": "Management",
                                    "objective": "Keep accepted Consultant evidence valid after offboarding",
                                    "context": "Historical acceptance must outlive an active Consultant task",
                                    "dependencies": [],
                                    "blockers": [],
                                    "decisionPaths": [],
                                    "evidencePaths": [evidence],
                                    "resultSummary": "The Consultant reviewed and accepted the bounded work",
                                    "completedAt": "2026-07-14",
                                }
                            ],
                        },
                        "tickets": {
                            "schemaVersion": 1,
                            "recordType": "tickets",
                            "tickets": [
                                {
                                    "id": "TEAM-1",
                                    "title": "Record Consultant acceptance",
                                    "status": "Done",
                                    "priority": "P2",
                                    "owner": "Operations",
                                    "goal": "TEAM-GOAL",
                                    "dependencies": [],
                                    "objective": "Preserve a typed historical approval",
                                    "scope": ["Consultant review record"],
                                    "nonGoals": ["Keeping the Consultant active forever"],
                                    "affectedSystems": ["docs/state"],
                                    "acceptanceCriteria": ["Historical approval remains valid"],
                                    "requiredVerification": ["Run team and state checks"],
                                    "expectedEvidence": [evidence],
                                    "risks": ["Offboarding could invalidate history"],
                                    "requiredConsultantIds": ["product-designer"],
                                    "assurance": {
                                        "testRigor": "Standard",
                                        "humanReviewStages": [],
                                        "overrideReason": "",
                                    },
                                    "blockers": [],
                                    "openDecisions": [],
                                    "reportPath": evidence,
                                }
                            ],
                        },
                        "reviews": {
                            "schemaVersion": 1,
                            "recordType": "reviews",
                            "reviews": [],
                            "consultantReviews": [
                                {
                                    "id": "TEAM-1-readiness",
                                    "ticket": "TEAM-1",
                                    "consultantId": "product-designer",
                                    "stage": "Readiness",
                                    "status": "Approved",
                                    "evidencePaths": [evidence],
                                },
                                {
                                    "id": "TEAM-1-acceptance",
                                    "ticket": "TEAM-1",
                                    "consultantId": "product-designer",
                                    "stage": "Acceptance",
                                    "status": "Approved",
                                    "evidencePaths": [evidence],
                                },
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        applied_history = run(
            sys.executable,
            str(project / "tools/harness_state.py"),
            "apply",
            str(historical_operation),
            "--json",
            cwd=project,
        )
        assert json.loads(applied_history.stdout)["ok"] is True
        offboarded_historical = json.loads(
            run(
                *team_command(
                    project, "fire", "--consultant", "product-designer", "--yes", "--json"
                ),
                cwd=project,
            ).stdout
        )
        assert offboarded_historical["ok"] is True
        historical_team = read_json(project / "docs/state/team.json")
        historical_product = next(
            item for item in historical_team["consultants"] if item["id"] == "product-designer"
        )
        assert historical_product["status"] == "inactive"

        checked = json.loads(
            run(
                sys.executable,
                str(project / "tools/harness_team.py"),
                "check",
                "--project-root",
                str(project),
                "--json",
                cwd=project,
            ).stdout
        )
        assert checked == {"ok": True, "errors": []}
        shutil.rmtree(lock_path.parent, ignore_errors=True)

    print("team lifecycle smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
