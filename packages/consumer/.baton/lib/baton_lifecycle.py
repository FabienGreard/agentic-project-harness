#!/usr/bin/env python3
"""Fail-closed Baton installation, adoption, status, update, and activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Callable
import uuid

sys.dont_write_bytecode = True

from harness_lock import MutationLockError, mutation_lock
from harness_state import render_dashboard, validate_records
from codex_config_contract import base_semantics, parse_codex_config_text, render_codex_config
from harness_team import (
    TeamError,
    initialize_team,
    load_catalog,
    normalized_reasoning,
    render_team_configs,
    team_record,
    validate_team,
)


METADATA_PATH = ".baton/metadata.json"
LEGACY_METADATA_PATH = ".agent-harness.json"
MANIFEST_SCHEMA = "baton.release-bundle/v1"
OFFICIAL_REPOSITORIES = {"FabienGreard/baton", "FabienGreard/agentic-project-harness"}
LEGACY_RELEASE_ANCHORS = {
    "0.2.0": {
        "repository": "FabienGreard/baton",
        "tag": "v0.2.0",
        "commit": "8c3f9da8b08fca2408fa37bbf2a52d94e3fe8ad8",
    },
    "0.3.0": {
        "repository": "FabienGreard/baton",
        "tag": "v0.3.0",
        "commit": "a8c041c2737f0cdec0834e5307906a4f9f15fabf",
    },
}
SKILL_NAMES = (
    "brainstorm",
    "code-review",
    "fire-consultant",
    "hire-consultant",
    "improve-codebase-architecture",
)
AGENTS_START = "<!-- BATON:START -->"
AGENTS_END = "<!-- BATON:END -->"
MANAGED_OWNERSHIP = {"baton-managed", "generated-config", "integration-link"}
REASONING_KEYS = {"management", "operations", "consultants", "contractors", "internalAudit"}


class LifecycleError(RuntimeError):
    """A Baton lifecycle action could not continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def safe_relative(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\0" in raw:
        raise LifecycleError(f"unsafe project path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise LifecycleError(f"unsafe project path: {raw!r}")
    return raw


def inside(root: Path, relative: str, *, allow_leaf_symlink: bool = True) -> Path:
    relative = safe_relative(relative)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current /= part
        if current.is_symlink():
            raise LifecycleError(f"project path passes through a symbolic link: {relative}")
    resolved_root = root.resolve()
    resolved_parent = candidate.parent.resolve(strict=False)
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise LifecycleError(f"project path escapes the target: {relative}")
    if not allow_leaf_symlink and candidate.is_symlink():
        raise LifecycleError(f"project path may not be a symbolic link: {relative}")
    return candidate


def entry_digest(path: Path) -> str | None:
    if path.is_symlink():
        return sha256_bytes(os.readlink(path).encode("utf-8"))
    if path.is_file():
        return sha256_file(path)
    return None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LifecycleError(f"required JSON file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise LifecycleError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"expected a JSON object in {path}")
    return value


def read_project_json(root: Path, relative: str) -> dict[str, Any]:
    path = inside(root, relative, allow_leaf_symlink=False)
    if not path.is_file():
        raise LifecycleError(f"required project JSON file is missing or unsafe: {relative}")
    return read_json(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def validate_target(root: Path) -> None:
    absolute = root.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise LifecycleError(f"target path may not be or pass through a symbolic link: {root}")
    if root.exists() and not root.is_dir():
        raise LifecycleError(f"target exists and is not a directory: {root}")


def manifest_payload(manifest: dict[str, Any], payload: str) -> dict[str, Any]:
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("channel") != "stable":
        raise LifecycleError("release manifest is not a stable Baton manifest")
    version = manifest.get("version")
    if not isinstance(version, str) or manifest.get("stableTag") != f"v{version}":
        raise LifecycleError("release manifest version and tag do not match")
    source = manifest.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") not in OFFICIAL_REPOSITORIES
        or re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit"))) is None
    ):
        raise LifecycleError("release manifest source is not official and immutable")
    payloads = manifest.get("payloads")
    if not isinstance(payloads, dict) or payload not in payloads:
        raise LifecycleError(f"release manifest lacks payload {payload!r}")
    record = payloads[payload]
    if not isinstance(record, dict) or not isinstance(record.get("files"), list):
        raise LifecycleError(f"release payload is invalid: {payload}")
    return record


def validate_payload_tree(payload_root: Path, manifest: dict[str, Any], payload: str) -> dict[str, dict[str, Any]]:
    record = manifest_payload(manifest, payload)
    indexed: dict[str, dict[str, Any]] = {}
    for item in record["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sourcePath", "classification", "kind", "sha256"}:
            raise LifecycleError(f"invalid payload file record: {payload}")
        relative = safe_relative(item["path"])
        if relative in indexed or not relative.startswith(".baton/"):
            raise LifecycleError(f"invalid or duplicate payload path: {relative}")
        path = inside(payload_root, relative)
        digest = entry_digest(path)
        kind = "symlink" if path.is_symlink() else "file" if path.is_file() else None
        if digest != item["sha256"] or kind != item["kind"]:
            raise LifecycleError(f"payload tree does not match the signed manifest: {relative}")
        indexed[relative] = item
    actual: set[str] = set()
    for path in payload_root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        actual.add(path.relative_to(payload_root).as_posix())
    if actual != set(indexed):
        raise LifecycleError("payload tree has unsigned or missing files")
    return indexed


def github_evidence(
    manifest: dict[str, Any],
    payload_records: dict[str, dict[str, Any]],
    previous_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repository = manifest["source"]["repository"]
    commit = manifest["source"]["commit"]
    base = f"https://github.com/{repository}"
    result: dict[str, Any] = {
        "release": f"{base}/releases/tag/{manifest['stableTag']}",
        "manifest": f"{base}/releases/download/{manifest['stableTag']}/baton-manifest.json",
        "sourceTree": f"{base}/tree/{commit}/packages/consumer",
        "sourceFiles": {
            relative: f"{base}/blob/{commit}/{record['sourcePath']}"
            for relative, record in sorted(payload_records.items())
        },
    }
    if (
        isinstance(previous_source, dict)
        and previous_source.get("repository") == repository
        and re.fullmatch(r"[0-9a-f]{40}", str(previous_source.get("commit")))
        and previous_source["commit"] != commit
    ):
        result["compare"] = f"{base}/compare/{previous_source['commit']}...{commit}"
    return result


def copy_entry(source_root: Path, relative: str, destination_root: Path) -> None:
    source = inside(source_root, relative)
    destination = inside(destination_root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    remove_entry(destination)
    if source.is_symlink():
        target = os.readlink(source)
        resolved = (destination.parent / target).resolve(strict=False)
        root = destination_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise LifecycleError(f"copied symlink would escape target: {relative}")
        destination.symlink_to(target)
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise LifecycleError(f"unsupported payload entry: {relative}")


def remove_entry(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def copy_payload(payload_root: Path, destination: Path, records: dict[str, dict[str, Any]]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for relative in records:
        copy_entry(payload_root, relative, destination)


def default_agents_block(status: str) -> str:
    status_line = (
        "Baton is active. Read [`.baton/AGENTS.md`](.baton/AGENTS.md) before acting."
        if status == "Installed"
        else "Baton is installed in `Needs Integration` mode. Read [`.baton/integration/README.md`](.baton/integration/README.md) and `.baton/metadata.json`; do not treat starter state as authoritative."
    )
    return f"{AGENTS_START}\n{status_line}\n{AGENTS_END}"


def merge_agents(existing: str | None, status: str) -> tuple[str, bool]:
    block = default_agents_block(status)
    if existing is None:
        return f"# Repository agents\n\n{block}\n", True
    start = existing.find(AGENTS_START)
    end = existing.find(AGENTS_END)
    if start == -1 and end == -1:
        separator = "" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
        return existing + separator + block + "\n", True
    if start == -1 or end == -1 or end < start or existing.find(AGENTS_START, start + 1) != -1 or existing.find(AGENTS_END, end + 1) != -1:
        raise LifecycleError("AGENTS.md contains an ambiguous Baton managed block")
    end += len(AGENTS_END)
    return existing[:start] + block + existing[end:], existing[start:end] != block


def integration_plan(
    prepared: Path, project_root: Path, status: str, agent_names: list[str]
) -> tuple[list[str], list[str], list[str]]:
    managed: list[str] = []
    generated: list[str] = []
    manual: list[str] = []
    agents_path = project_root / "AGENTS.md"
    if agents_path.is_symlink() or (agents_path.exists() and not agents_path.is_file()):
        proposal = prepared / ".baton/integration/AGENTS.md"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text(default_agents_block(status) + "\n", encoding="utf-8")
        generated.append(".baton/integration/AGENTS.md")
        manual.append(
            "Existing AGENTS.md is not a safe regular file and was preserved. "
            "Merge the Baton block from .baton/integration/AGENTS.md manually."
        )
    else:
        existing_agents = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else None
        merged_agents, _ = merge_agents(existing_agents, status)
        (prepared / "AGENTS.md").write_text(merged_agents, encoding="utf-8")
        managed.append("AGENTS.md")

    desired_config = render_codex_config(agent_names)
    config_path = project_root / ".codex/config.toml"
    if not config_path.exists():
        path = prepared / ".codex/config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired_config, encoding="utf-8")
        managed.append(".codex/config.toml")
    else:
        try:
            compatible = config_path.is_file() and base_semantics(
                parse_codex_config_text(config_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError):
            compatible = False
        wording = (
            "Existing .codex/config.toml has Baton-compatible permissions but remains project-owned. "
            if compatible
            else "Existing .codex/config.toml is project-owned or incompatible. "
        )
        manual.append(wording + "Merge .baton/integration/codex-config.toml manually to register Baton agents; the existing file was preserved.")
        desired = prepared / ".baton/integration/codex-config.toml"
        desired.parent.mkdir(parents=True, exist_ok=True)
        desired.write_text(desired_config, encoding="utf-8")
        generated.append(".baton/integration/codex-config.toml")

    for name in SKILL_NAMES:
        relative = f".agents/skills/{name}"
        current = project_root / relative
        target = f"../../.baton/skills/{name}"
        if not current.exists() and not current.is_symlink():
            path = prepared / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target)
            managed.append(relative)
        elif current.is_symlink() and os.readlink(current) == target:
            continue
        else:
            manual.append(f"Preserved skill-discovery collision at {relative}; link it to {target} manually if appropriate.")
    return managed, generated, manual


def configure_new_project(
    prepared: Path,
    *,
    project_name: str,
    project_type: str,
    reasoning: dict[str, str],
    selected_consultants: list[str],
) -> tuple[list[str], list[str]]:
    project_path = prepared / ".baton/state/project.json"
    project_record = read_json(project_path)
    project_record["project"]["name"] = project_name
    project_record["project"]["lastVerified"] = datetime.now(timezone.utc).date().isoformat()
    write_json(project_path, project_record)
    team = initialize_team(
        project_root=prepared,
        preset_id=project_type,
        selected=selected_consultants,
        reasoning=reasoning,
    )
    records = {
        name: read_json(prepared / f".baton/state/{name}.json")
        for name in ("project", "goals", "tickets", "ownership", "reviews", "team")
    }
    errors: list[str] = []
    validate_records(records, errors)
    if errors:
        raise LifecycleError("generated project state is invalid: " + "; ".join(errors))
    dashboard = prepared / ".baton/dashboard/index.html"
    dashboard.parent.mkdir(parents=True, exist_ok=True)
    dashboard.write_text(render_dashboard(records), encoding="utf-8")
    agent_names = ["management", "operations", "contractor", "internal_audit"]
    agent_names.extend(
        f"consultant_{item['id'].replace('-', '_')}"
        for item in team["consultants"]
        if item["status"] == "active"
    )
    return agent_names, [".baton/dashboard/index.html"]


def configure_adoption(
    prepared: Path,
    *,
    project_name: str,
    project_type: str,
    reasoning: dict[str, str],
    selected_consultants: list[str],
) -> list[str]:
    starter = prepared / ".baton/integration/starter"
    project_path = starter / "state/project.json"
    project_record = read_json(project_path)
    project_record["project"]["name"] = project_name
    project_record["project"]["lastVerified"] = datetime.now(timezone.utc).date().isoformat()
    write_json(project_path, project_record)
    catalog = load_catalog(prepared)
    team = team_record(
        catalog=catalog,
        preset_id=project_type,
        selected=selected_consultants,
        reasoning=reasoning,
    )
    configs = render_team_configs(team=team, catalog=catalog)
    for consultant in team["consultants"]:
        if consultant["status"] == "active":
            content = configs[f"consultant-{consultant['id']}.toml"].encode("utf-8")
            consultant["configBaselineSha256"] = sha256_bytes(content)
    write_json(starter / "state/team.json", team)
    agents = starter / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    for filename, content in configs.items():
        (agents / filename).write_text(content, encoding="utf-8")
    prompt = f"""Integrate Baton into {project_name} without replacing existing project identity or records.

Read AGENTS.md, `.baton/metadata.json` including `legacyMigration`, this transaction's report and backup, and every file under .baton/integration/starter/. Inspect the live repository and translate its mature direction, goals, tickets, ownership, reviews, and team into schema-valid records under a temporary directory. Do not parse Markdown mechanically or invent facts. Keep legacy files unchanged.

Validate the proposed records and, only after the human confirms that the migrated state is complete, run `.baton/bin/baton _activate --from /absolute/path/to/reviewed-proposal --json`. Then run `.baton/bin/baton status --json` and `.baton/bin/baton check --json`.

Report preserved legacy files, conflicts or manual actions, and the external transactional backup and rollback location. For every cleanup or migration candidate, include its local path plus direct GitHub `blob/<immutable-commit>/<source-path>` links derived from `.baton/metadata.json` and the verified release manifest; include a GitHub compare link when both immutable commits are known. Never link a moving branch as evidence. Never delete a legacy file or backup without explicit human approval.
"""
    (prepared / ".baton/integration/cleanup-prompt.txt").write_text(prompt, encoding="utf-8")
    agent_names = ["management", "operations", "contractor", "internal_audit"]
    agent_names.extend(
        f"consultant_{item['id'].replace('-', '_')}"
        for item in team["consultants"]
        if item["status"] == "active"
    )
    return agent_names


def transaction_directory(project_root: Path, transaction_id: str) -> Path:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", transaction_id) is None:
        raise LifecycleError("invalid transaction ID")
    state_home = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser()
    project_id = sha256_bytes(str(project_root.resolve()).encode("utf-8"))[:16]
    path = (state_home / "baton" / project_id / "transactions" / transaction_id).resolve(strict=False)
    root = project_root.resolve()
    if path == root or root in path.parents:
        raise LifecycleError("transaction storage must stay outside the project")
    return path


def all_entries(root: Path) -> list[str]:
    result: list[str] = []
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        result.append(path.relative_to(root).as_posix())
    return sorted(result)


def backup_entry(project_root: Path, relative: str, backup: Path) -> bool:
    source = inside(project_root, relative)
    if not source.exists() and not source.is_symlink():
        return False
    destination = inside(backup, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise LifecycleError(f"refusing to replace directory collision: {relative}")
    return True


def missing_parent_directories(project_root: Path, relatives: list[str]) -> list[Path]:
    """Return destination parents that did not exist before a transaction."""
    missing: set[Path] = set()
    root = project_root.resolve()
    for relative in relatives:
        current = inside(root, relative).parent
        while current != root:
            if current.exists() or current.is_symlink():
                break
            missing.add(current)
            current = current.parent
    return sorted(missing, key=lambda path: len(path.parts), reverse=True)


def restore_entries(
    project_root: Path,
    backup: Path,
    touched: list[tuple[str, bool]],
    missing_parents: list[Path],
) -> list[str]:
    failures: list[str] = []
    for relative, existed in reversed(touched):
        try:
            destination = inside(project_root, relative)
            remove_entry(destination)
            if existed:
                copy_entry(backup, relative, project_root)
        except (OSError, LifecycleError) as error:
            failures.append(f"{relative}: {error}")
    for path in missing_parents:
        try:
            if not path.exists() and not path.is_symlink():
                continue
            if path.is_symlink() or not path.is_dir():
                raise LifecycleError("transaction-created parent is no longer an empty directory")
            path.rmdir()
        except (OSError, LifecycleError) as error:
            failures.append(f"{path.relative_to(project_root).as_posix()}/: {error}")
    return failures


def apply_plan(
    project_root: Path,
    prepared: Path,
    add: list[str],
    replace: list[str],
    transaction: Path,
    baselines: dict[str, dict[str, Any]] | None = None,
    finalize: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    backup = transaction / "backup"
    proposed = transaction / "proposed"
    backup.mkdir(parents=True, exist_ok=True)
    proposed.mkdir(parents=True, exist_ok=True)
    touched: list[tuple[str, bool]] = []
    planned = [*add, *replace]
    missing_parents = missing_parent_directories(project_root, planned)
    writes = 0
    fail_after_raw = os.environ.get("BATON_TEST_FAIL_AFTER_WRITES")
    fail_after = int(fail_after_raw) if fail_after_raw else None
    changes = [
        {
            "path": relative,
            "action": "add" if relative in add else "replace",
            "baselineSha256": (baselines or {}).get(relative, {}).get("baselineSha256"),
            "beforeSha256": entry_digest(inside(project_root, relative)),
            "targetSha256": entry_digest(inside(prepared, relative)),
        }
        for relative in [*add, *replace]
    ]
    try:
        for relative in planned:
            existed = backup_entry(project_root, relative, backup)
            touched.append((relative, existed))
            copy_entry(prepared, relative, proposed)
            copy_entry(prepared, relative, project_root)
            writes += 1
            if fail_after is not None and writes >= fail_after:
                raise LifecycleError("injected Baton transaction failure")
        result = {
            "result": "applied",
            "backupPath": str(backup),
            "proposedPath": str(proposed),
            "add": add,
            "replace": replace,
            "changes": changes,
        }
        if os.environ.get("BATON_TEST_FAIL_DURING_FINALIZE"):
            raise LifecycleError("injected Baton finalization failure")
        if finalize is not None:
            finalize(result)
    except BaseException as error:
        failures = restore_entries(project_root, backup, touched, missing_parents)
        (transaction / "cleanup-prompt.txt").unlink(missing_ok=True)
        report = {
            "result": "rolled-back",
            "error": str(error),
            "backupPath": str(backup),
            "touched": [item[0] for item in touched],
            "changes": changes,
            "restoreFailures": failures,
        }
        write_json(transaction / "update-report.json", report)
        if failures:
            raise LifecycleError("transaction failed and rollback was incomplete: " + "; ".join(failures)) from error
        raise LifecycleError(f"transaction failed and was rolled back: {error}") from error
    return result


def legacy_cleanup_plan(root: Path) -> tuple[list[str], dict[str, Any] | None]:
    legacy = root / LEGACY_METADATA_PATH
    if legacy.is_symlink():
        raise LifecycleError("legacy metadata may not be a symbolic link")
    if not legacy.is_file():
        return [], None
    candidates: set[str] = {LEGACY_METADATA_PATH}
    try:
        metadata = read_project_json(root, LEGACY_METADATA_PATH)
    except LifecycleError:
        return [LEGACY_METADATA_PATH], {
            "metadataPath": LEGACY_METADATA_PATH,
            "baselineMode": "unavailable",
            "reason": "legacy metadata could not be parsed; no legacy project path was inferred",
            "files": [],
        }
    source = metadata.get("source")
    repository = source if isinstance(source, str) else source.get("repository") if isinstance(source, dict) else None
    commit = metadata.get("sourceRevision")
    if not isinstance(commit, str) and isinstance(source, dict):
        commit = source.get("commit")
    evidence: dict[str, Any] = {
        "metadataPath": LEGACY_METADATA_PATH,
        "schemaVersion": metadata.get("schemaVersion"),
        "harnessVersion": metadata.get("harnessVersion"),
        "baselineMode": "unavailable",
        "source": {
            "repository": repository,
            "commit": commit if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) else None,
            "ref": metadata.get("ref"),
        },
        "files": [],
    }
    if (
        isinstance(repository, str)
        and evidence["source"]["commit"] is not None
        and repository in OFFICIAL_REPOSITORIES
    ):
        evidence["source"]["tree"] = (
            f"https://github.com/{repository}/tree/{evidence['source']['commit']}"
        )
    anchor = LEGACY_RELEASE_ANCHORS.get(metadata.get("harnessVersion"))
    if (
        evidence["source"]["commit"] is None
        and metadata.get("schemaVersion") == 1
        and metadata.get("sourceMode") == "remote"
        and repository in OFFICIAL_REPOSITORIES
        and anchor is not None
    ):
        anchor_repository = anchor["repository"]
        anchor_tag = anchor["tag"]
        anchor_commit = anchor["commit"]
        evidence["source"]["versionAnchor"] = {
            **anchor,
            "release": f"https://github.com/{anchor_repository}/releases/tag/{anchor_tag}",
            "tree": f"https://github.com/{anchor_repository}/tree/{anchor_commit}",
            "note": "official stable version anchor; the legacy remote installer did not record its installed commit",
        }
    managed = metadata.get("managedFiles")
    if isinstance(managed, dict):
        evidence["baselineMode"] = "managed-files"
        for raw, record in sorted(managed.items()):
            try:
                relative = safe_relative(raw)
            except LifecycleError:
                continue
            ownership = record.get("ownership") if isinstance(record, dict) else None
            baseline = record.get("baselineSha256") if isinstance(record, dict) else None
            current = entry_digest(inside(root, relative))
            eligible = (
                ownership in {"harness-managed", "generated-config"}
                and is_sha256(baseline)
                and current == baseline
            )
            status = (
                "unchanged-managed-candidate"
                if eligible
                else "project-owned-preserved"
                if ownership == "project-owned"
                else "missing-preserved"
                if current is None
                else "modified-preserved"
            )
            if eligible:
                candidates.add(relative)
            evidence["files"].append(
                {
                    "path": relative,
                    "ownership": ownership,
                    "baselineSha256": baseline if is_sha256(baseline) else None,
                    "currentSha256": current,
                    "status": status,
                }
            )
    else:
        evidence["reason"] = (
            "legacy schema has no per-file baselines; every non-metadata project path is preserved "
            "for LLM/human comparison against immutable source evidence"
        )
    return sorted(candidates), evidence


def build_metadata(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    status: str,
    prepared: Path,
    payload_records: dict[str, dict[str, Any]],
    integration_paths: list[str],
    generated_paths: list[str],
    project_owned_paths: list[str],
    manual_actions: list[str],
    cleanup_candidates: list[str],
    legacy_migration: dict[str, Any] | None,
    transaction_id: str,
) -> dict[str, Any]:
    managed: dict[str, dict[str, str]] = {}
    for relative, record in payload_records.items():
        if record["classification"] == "template-only" and status != "Needs Integration":
            continue
        digest = entry_digest(inside(prepared, relative))
        if digest is not None:
            managed[relative] = {
                "ownership": "generated-config" if record["classification"] == "template-only" else "baton-managed",
                "baselineSha256": digest,
            }
    for relative in sorted(set(integration_paths)):
        if relative == "AGENTS.md":
            continue
        digest = entry_digest(inside(prepared, relative))
        if digest is not None:
            managed[relative] = {"ownership": "integration-link", "baselineSha256": digest}
    for relative in sorted(set(generated_paths)):
        digest = entry_digest(inside(prepared, relative))
        if digest is not None:
            managed[relative] = {"ownership": "generated-config", "baselineSha256": digest}
    source = manifest["source"]
    return {
        "schemaVersion": 3,
        "batonVersion": manifest["version"],
        "projectVersion": None,
        "stateSchemaVersion": manifest["stateSchemaVersion"],
        "provider": "codex",
        "installationStatus": status,
        "projectName": project_name,
        "projectType": project_type,
        "reasoningPreset": reasoning_preset,
        "reasoning": dict(sorted(reasoning.items())),
        "source": {
            "repository": source["repository"],
            "channel": "stable",
            "tag": manifest["stableTag"],
            "commit": source["commit"],
            "manifestSha256": manifest_sha256,
        },
        "installedAt": utc_now(),
        "updatedAt": utc_now(),
        "lastTransactionId": transaction_id,
        "managedFiles": dict(sorted(managed.items())),
        "managedBlocks": (
            {"AGENTS.md": sha256_bytes(default_agents_block(status).encode("utf-8"))}
            if "AGENTS.md" in integration_paths
            else {}
        ),
        "projectOwnedFiles": sorted(set(project_owned_paths)),
        "legacyCleanupCandidates": cleanup_candidates,
        "legacyMigration": legacy_migration,
        "pendingIntegration": manual_actions,
    }


def plan_install(project_root: Path, prepared: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    add: list[str] = []
    replace: list[str] = []
    conflicts: list[str] = []
    preserve: list[str] = []
    for relative in all_entries(prepared):
        current = inside(project_root, relative)
        desired = entry_digest(inside(prepared, relative))
        actual = entry_digest(current)
        if actual is None and not current.exists():
            add.append(relative)
        elif actual == desired:
            preserve.append(relative)
        elif relative == "AGENTS.md":
            replace.append(relative)
        else:
            conflicts.append(relative)
    return add, replace, conflicts, preserve


def extract_agents_block(text: str) -> str | None:
    start = text.find(AGENTS_START)
    end = text.find(AGENTS_END)
    if (
        start == -1
        or end == -1
        or end < start
        or text.find(AGENTS_START, start + 1) != -1
        or text.find(AGENTS_END, end + 1) != -1
    ):
        return None
    return text[start : end + len(AGENTS_END)]


def inspect_status(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    metadata_path = root / METADATA_PATH
    if not metadata_path.is_file():
        if (root / LEGACY_METADATA_PATH).is_file():
            legacy = read_project_json(root, LEGACY_METADATA_PATH)
            return {
                "ok": True,
                "installationStatus": "Legacy",
                "batonVersion": None,
                "legacyHarnessVersion": legacy.get("harnessVersion"),
                "updateAvailable": True,
            }
        raise LifecycleError("this repository has no Baton installation")
    metadata = read_project_json(root, METADATA_PATH)
    if metadata.get("schemaVersion") != 3:
        raise LifecycleError(f"unsupported Baton metadata schema: {metadata.get('schemaVersion')!r}")
    managed = metadata.get("managedFiles")
    if not isinstance(managed, dict):
        raise LifecycleError("Baton metadata has no managed-file baselines")
    modified: list[str] = []
    missing: list[str] = []
    for relative, record in sorted(managed.items()):
        if not isinstance(record, dict) or record.get("ownership") not in MANAGED_OWNERSHIP or not is_sha256(record.get("baselineSha256")):
            raise LifecycleError(f"invalid managed-file baseline: {relative}")
        path = inside(root, relative)
        digest = entry_digest(path)
        if digest is None:
            missing.append(relative)
        elif digest != record["baselineSha256"]:
            modified.append(relative)
    block_status = "missing"
    agents_path = root / "AGENTS.md"
    expected_block = metadata.get("managedBlocks", {}).get("AGENTS.md")
    pending_agents = expected_block is None and any(
        "AGENTS.md" in item for item in metadata.get("pendingIntegration", [])
    )
    if pending_agents:
        block_status = "pending-manual"
    elif agents_path.is_symlink():
        block_status = "modified"
    elif agents_path.is_file():
        block = extract_agents_block(agents_path.read_text(encoding="utf-8"))
        if metadata.get("installationStatus") == "Source Repository" and expected_block is None:
            block_status = "ok" if block else "missing"
        else:
            block_status = "ok" if block and sha256_bytes(block.encode("utf-8")) == expected_block else "modified"
    return {
        "ok": not modified and not missing and block_status in {"ok", "pending-manual"},
        "batonVersion": metadata.get("batonVersion"),
        "projectVersion": metadata.get("projectVersion"),
        "stateSchemaVersion": metadata.get("stateSchemaVersion"),
        "installationStatus": metadata.get("installationStatus"),
        "source": metadata.get("source"),
        "integrity": {
            "modified": modified,
            "missing": missing,
            "agentsBlock": block_status,
        },
        "pendingIntegration": metadata.get("pendingIntegration", []),
        "legacyCleanupCandidates": metadata.get("legacyCleanupCandidates", []),
        "lastTransactionId": metadata.get("lastTransactionId"),
    }


def install_or_adopt(
    *,
    project_root: Path,
    payload_root: Path,
    manifest: dict[str, Any],
    manifest_sha256: str,
    payload: str,
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    selected_consultants: list[str],
) -> dict[str, Any]:
    root = project_root.absolute()
    validate_target(root)
    root.mkdir(parents=True, exist_ok=True)
    payload_records = validate_payload_tree(payload_root, manifest, payload)
    transaction_id = f"{payload}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    transaction = transaction_directory(root, transaction_id)
    created_git = False
    with mutation_lock(root, f"lifecycle-{payload}"):
        validate_target(root)
        if (root / METADATA_PATH).exists():
            raise LifecycleError("Baton is already installed; use update")
        if (root / ".baton").exists() or (root / ".baton").is_symlink():
            raise LifecycleError("target already contains an unrecognized .baton path")
        was_empty = next(root.iterdir(), None) is None
        expected_payload = "new-project" if was_empty else "adoption"
        if payload != expected_payload:
            raise LifecycleError(
                f"installer selected {payload}, but target requires {expected_payload}"
            )
        with tempfile.TemporaryDirectory(prefix="baton-prepared-") as raw:
            prepared = Path(raw) / "project"
            copy_payload(payload_root, prepared, payload_records)
            project_owned: list[str] = []
            generated: list[str] = []
            if payload == "new-project":
                agent_names, generated = configure_new_project(
                    prepared,
                    project_name=project_name,
                    project_type=project_type,
                    reasoning=reasoning,
                    selected_consultants=selected_consultants,
                )
                project_owned = [
                    relative
                    for relative, record in payload_records.items()
                    if record["classification"] == "template-only"
                ]
                project_owned.append(".baton/state/team.json")
                generated.extend(
                    relative
                    for relative in all_entries(prepared)
                    if relative.startswith(".baton/agents/")
                )
                status = "Installed"
            else:
                agent_names = configure_adoption(
                    prepared,
                    project_name=project_name,
                    project_type=project_type,
                    reasoning=reasoning,
                    selected_consultants=selected_consultants,
                )
                project_owned = []
                status = "Needs Integration"
            integration_paths, integration_generated, manual_actions = integration_plan(
                prepared, root, status, agent_names
            )
            generated.extend(integration_generated)
            if payload == "adoption":
                manual_actions.insert(
                    0,
                    "Review a complete schema-valid mature-project state, then activate it with .baton/bin/baton _activate --from PATH; quarantined starter state is not authoritative.",
                )
            cleanup_candidates, legacy_migration = legacy_cleanup_plan(root)
            if cleanup_candidates:
                manual_actions.append("Legacy harness files were preserved and listed as human-approved cleanup candidates.")
            if legacy_migration and legacy_migration.get("baselineMode") == "unavailable":
                manual_actions.append(
                    "Legacy metadata has no per-file baselines. Baton preserved every non-metadata path; "
                    "use the recorded immutable source evidence for LLM/human comparison."
                )
            metadata = build_metadata(
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                project_name=project_name,
                project_type=project_type,
                reasoning_preset=reasoning_preset,
                reasoning=reasoning,
                status=status,
                prepared=prepared,
                payload_records=payload_records,
                integration_paths=integration_paths,
                generated_paths=generated,
                project_owned_paths=project_owned,
                manual_actions=manual_actions,
                cleanup_candidates=cleanup_candidates,
                legacy_migration=legacy_migration,
                transaction_id=transaction_id,
            )
            write_json(prepared / METADATA_PATH, metadata)
            add, replace, conflicts, preserve = plan_install(root, prepared)
            if conflicts:
                raise LifecycleError("Baton payload collides with existing paths: " + ", ".join(conflicts))
            if was_empty:
                try:
                    subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True, capture_output=True)
                except (FileNotFoundError, subprocess.CalledProcessError) as error:
                    raise LifecycleError("git initialization failed before installation") from error
                created_git = True

            def finalize_install(report: dict[str, Any]) -> None:
                report.update(
                    {
                        "transactionId": transaction_id,
                        "mode": payload,
                        "version": manifest["version"],
                        "installationStatus": status,
                        "preserved": preserve,
                        "manualActions": manual_actions,
                        "legacyCleanupCandidates": cleanup_candidates,
                        "legacyMigration": legacy_migration,
                        "rollbackLocation": str(transaction / "backup"),
                        "sourceEvidence": github_evidence(manifest, payload_records),
                    }
                )
                write_json(transaction / "update-report.json", report)
                prompt_source = prepared / ".baton/integration/cleanup-prompt.txt"
                if prompt_source.is_file():
                    shutil.copy2(prompt_source, transaction / "cleanup-prompt.txt")

            try:
                report = apply_plan(
                    root,
                    prepared,
                    add,
                    replace,
                    transaction,
                    finalize=finalize_install,
                )
            except BaseException:
                if created_git:
                    shutil.rmtree(root / ".git", ignore_errors=True)
                if was_empty:
                    for path in list(root.iterdir()):
                        remove_entry(path)
                raise
            return {
                "ok": True,
                "mode": payload,
                "project": str(root),
                "version": manifest["version"],
                "installationStatus": status,
                "transactionId": transaction_id,
                "reportPath": str(transaction / "update-report.json"),
                "backupPath": str(transaction / "backup"),
                "cleanupPromptPath": str(transaction / "cleanup-prompt.txt") if (transaction / "cleanup-prompt.txt").is_file() else None,
                "manualActions": manual_actions,
                "legacyCleanupCandidates": cleanup_candidates,
                "legacyMigration": legacy_migration,
                "sourceEvidence": report["sourceEvidence"],
            }


def update_installation(
    *,
    project_root: Path,
    payload_root: Path,
    manifest: dict[str, Any],
    manifest_sha256: str,
    payload: str,
) -> dict[str, Any]:
    root = project_root.resolve()
    metadata = read_project_json(root, METADATA_PATH)
    if metadata.get("schemaVersion") != 3:
        raise LifecycleError("unsupported installed Baton metadata schema")
    if payload != "adoption":
        raise LifecycleError("updates use the adoption-runtime payload")
    current = tuple(int(item) for item in str(metadata.get("batonVersion", "")).split("."))
    target = tuple(int(item) for item in str(manifest.get("version", "")).split("."))
    if len(current) != 3 or len(target) != 3:
        raise LifecycleError("installed or target Baton version is invalid")
    if target < current:
        raise LifecycleError("automatic downgrade is not supported")
    installed_state_schema = metadata.get("stateSchemaVersion")
    target_state_schema = manifest.get("stateSchemaVersion")
    if type(installed_state_schema) is not int or type(target_state_schema) is not int:
        raise LifecycleError("installed or target state schema version is invalid")
    if target_state_schema < installed_state_schema:
        raise LifecycleError("automatic state-schema downgrade is not supported")
    if (
        target_state_schema != installed_state_schema
        and metadata.get("installationStatus") == "Installed"
    ):
        raise LifecycleError(
            "this stable update changes the project-owned state schema and requires an explicit Baton migration path"
        )
    if target == current:
        installed_source = metadata.get("source", {})
        if (
            installed_source.get("repository") != manifest["source"]["repository"]
            or installed_source.get("commit") != manifest["source"]["commit"]
            or installed_source.get("manifestSha256") != manifest_sha256
        ):
            raise LifecycleError("installed metadata does not match this immutable stable release")
        status = inspect_status(root)
        if not status["ok"]:
            raise LifecycleError("installed Baton-managed files differ from their baselines")
        return {"ok": True, "mode": "update", "upToDate": True, **status}
    installed_source = metadata.get("source")
    origin = manifest.get("supportedUpgradeOrigins", {}).get(f"v{metadata.get('batonVersion')}")
    if (
        not isinstance(installed_source, dict)
        or installed_source.get("channel") != "stable"
        or not isinstance(origin, dict)
        or origin.get("sourceCommit") != installed_source.get("commit")
        or origin.get("manifestSha256") != installed_source.get("manifestSha256")
    ):
        raise LifecycleError("installed Baton provenance is not an immutable supported upgrade origin")
    payload_records = validate_payload_tree(payload_root, manifest, payload)
    managed = metadata.get("managedFiles", {})
    if not isinstance(managed, dict):
        raise LifecycleError("installed metadata has no managed baselines")
    transaction_id = f"update-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    transaction = transaction_directory(root, transaction_id)
    with mutation_lock(root, "lifecycle-update"):
        locked_metadata = read_project_json(root, METADATA_PATH)
        if locked_metadata != metadata:
            raise LifecycleError("Baton state changed while update was waiting for the lock; retry")
        integrity = inspect_status(root)
        if not integrity["ok"]:
            raise LifecycleError("installed Baton-managed files differ from their baselines")
        with tempfile.TemporaryDirectory(prefix="baton-update-") as raw:
            prepared = Path(raw) / "project"
            copy_payload(payload_root, prepared, payload_records)
            add: list[str] = []
            replace: list[str] = []
            conflicts: list[str] = []
            new_managed: dict[str, dict[str, str]] = {}
            for relative, record in payload_records.items():
                if (
                    record["classification"] == "template-only"
                    and metadata.get("installationStatus") != "Needs Integration"
                ):
                    continue
                desired = entry_digest(inside(prepared, relative))
                baseline = managed.get(relative)
                actual = entry_digest(inside(root, relative))
                if baseline is None:
                    if actual is None and not inside(root, relative).exists():
                        add.append(relative)
                    elif actual != desired:
                        conflicts.append(relative)
                elif actual != baseline.get("baselineSha256"):
                    conflicts.append(relative)
                elif actual != desired:
                    replace.append(relative)
                if desired is not None:
                    new_managed[relative] = {
                        "ownership": "generated-config" if record["classification"] == "template-only" else "baton-managed",
                        "baselineSha256": desired,
                    }
            if metadata.get("installationStatus") == "Installed":
                team_path = inside(root, ".baton/state/team.json", allow_leaf_symlink=False)
                if team_path.is_file():
                    team = read_project_json(root, ".baton/state/team.json")
                    catalog = load_catalog(prepared)
                    configs = render_team_configs(team=team, catalog=catalog)
                    updated_team = json.loads(json.dumps(team))
                    for filename, content in configs.items():
                        relative = f".baton/agents/{filename}"
                        destination = inside(prepared, relative)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_text(content, encoding="utf-8")
                        desired = sha256_bytes(content.encode("utf-8"))
                        baseline = managed.get(relative)
                        actual = entry_digest(inside(root, relative))
                        if baseline is None:
                            if actual is None and not inside(root, relative).exists():
                                add.append(relative)
                            elif actual != desired:
                                conflicts.append(relative)
                        elif actual != baseline.get("baselineSha256"):
                            conflicts.append(relative)
                        elif actual != desired:
                            replace.append(relative)
                        new_managed[relative] = {
                            "ownership": "generated-config",
                            "baselineSha256": desired,
                        }
                        if filename.startswith("consultant-"):
                            identifier = filename.removeprefix("consultant-").removesuffix(".toml")
                            consultant = next(
                                (item for item in updated_team.get("consultants", []) if item.get("id") == identifier),
                                None,
                            )
                            if consultant is not None:
                                consultant["configBaselineSha256"] = desired
                    desired_codex = render_codex_config(active_agent_names(updated_team))
                    codex_relative = (
                        ".codex/config.toml"
                        if ".codex/config.toml" in managed
                        else ".baton/integration/codex-config.toml"
                    )
                    codex_destination = inside(prepared, codex_relative)
                    codex_destination.parent.mkdir(parents=True, exist_ok=True)
                    codex_destination.write_text(desired_codex, encoding="utf-8")
                    codex_digest = sha256_bytes(desired_codex.encode("utf-8"))
                    codex_baseline = managed.get(codex_relative)
                    codex_actual = entry_digest(inside(root, codex_relative))
                    if codex_baseline is None:
                        if codex_actual is None and not inside(root, codex_relative).exists():
                            add.append(codex_relative)
                        elif codex_actual != codex_digest:
                            conflicts.append(codex_relative)
                    elif codex_actual != codex_baseline.get("baselineSha256"):
                        conflicts.append(codex_relative)
                    elif codex_actual != codex_digest:
                        replace.append(codex_relative)
                    new_managed[codex_relative] = {
                        "ownership": "integration-link" if codex_relative == ".codex/config.toml" else "generated-config",
                        "baselineSha256": codex_digest,
                    }
                    if updated_team != team:
                        write_json(prepared / ".baton/state/team.json", updated_team)
                        replace.append(".baton/state/team.json")
                        records = {
                            name: updated_team if name == "team" else read_project_json(root, f".baton/state/{name}.json")
                            for name in ("project", "goals", "tickets", "ownership", "reviews", "team")
                        }
                        dashboard = render_dashboard(records)
                        dashboard_path = prepared / ".baton/dashboard/index.html"
                        dashboard_path.parent.mkdir(parents=True, exist_ok=True)
                        dashboard_path.write_text(dashboard, encoding="utf-8")
                        replace.append(".baton/dashboard/index.html")
                        new_managed[".baton/dashboard/index.html"] = {
                            "ownership": "generated-config",
                            "baselineSha256": sha256_bytes(dashboard.encode("utf-8")),
                        }
            cleanup_candidates = set(metadata.get("legacyCleanupCandidates", []))
            for relative, record in managed.items():
                if relative not in new_managed and (
                    record.get("ownership") == "baton-managed"
                    or relative.startswith(".baton/integration/starter/")
                ):
                    cleanup_candidates.add(relative)
            if conflicts:
                raise LifecycleError("update conflicts with modified or colliding Baton paths: " + ", ".join(conflicts))
            updated = json.loads(json.dumps(metadata))
            updated["batonVersion"] = manifest["version"]
            updated["stateSchemaVersion"] = target_state_schema
            updated["updatedAt"] = utc_now()
            updated["lastTransactionId"] = transaction_id
            updated["source"] = {
                "repository": manifest["source"]["repository"],
                "channel": "stable",
                "tag": manifest["stableTag"],
                "commit": manifest["source"]["commit"],
                "manifestSha256": manifest_sha256,
            }
            for relative, record in managed.items():
                if record.get("ownership") != "baton-managed" and relative not in new_managed:
                    new_managed[relative] = record
            updated["managedFiles"] = dict(sorted(new_managed.items()))
            updated["legacyCleanupCandidates"] = sorted(cleanup_candidates)
            write_json(prepared / METADATA_PATH, updated)
            replace.append(METADATA_PATH)
            add = sorted(set(add))
            replace = sorted(set(replace))

            def finalize_update(report: dict[str, Any]) -> None:
                report.update(
                    {
                        "transactionId": transaction_id,
                        "mode": "update",
                        "fromVersion": metadata["batonVersion"],
                        "toVersion": manifest["version"],
                        "cleanupCandidates": sorted(cleanup_candidates),
                        "rollbackLocation": str(transaction / "backup"),
                        "sourceEvidence": github_evidence(
                            manifest, payload_records, metadata.get("source")
                        ),
                    }
                )
                write_json(transaction / "update-report.json", report)

            report = apply_plan(
                root,
                prepared,
                add,
                replace,
                transaction,
                managed,
                finalize_update,
            )
            return {
                "ok": True,
                "mode": "update",
                "upToDate": False,
                "version": manifest["version"],
                "transactionId": transaction_id,
                "reportPath": str(transaction / "update-report.json"),
                "backupPath": str(transaction / "backup"),
                "cleanupCandidates": sorted(cleanup_candidates),
                "sourceEvidence": report["sourceEvidence"],
            }


def active_agent_names(team: dict[str, Any]) -> list[str]:
    names = ["management", "operations", "contractor", "internal_audit"]
    names.extend(
        f"consultant_{item['id'].replace('-', '_')}"
        for item in team.get("consultants", [])
        if item.get("status") == "active"
    )
    return names


def proposed_records(source: Path) -> tuple[dict[str, dict[str, Any]], Path]:
    root = source.resolve()
    state = root / "state" if (root / "state").is_dir() else root
    records: dict[str, dict[str, Any]] = {}
    for name in ("project", "goals", "tickets", "ownership", "reviews", "team"):
        path = state / f"{name}.json"
        if path.is_symlink() or not path.is_file():
            raise LifecycleError(f"activation proposal lacks a regular {name}.json record")
        records[name] = read_json(path)
    return records, root


def activate_adoption(
    *, project_root: Path, proposal: Path, assume_yes: bool
) -> dict[str, Any]:
    root = project_root.resolve()
    validate_target(root)
    metadata = read_project_json(root, METADATA_PATH)
    if metadata.get("schemaVersion") != 3 or metadata.get("installationStatus") != "Needs Integration":
        raise LifecycleError("activation requires a schema-v3 Baton installation in Needs Integration mode")
    if not assume_yes:
        if not sys.stdin.isatty():
            raise LifecycleError("activation requires a terminal or --yes")
        answer = input("Activate the reviewed mature-project state? [y/N] ").strip().casefold()
        if answer not in {"y", "yes"}:
            raise LifecycleError("no changes made")
    records, proposal_root = proposed_records(proposal)
    catalog = load_catalog(root)
    team = json.loads(json.dumps(records["team"]))
    if team.get("preset") != metadata.get("projectType"):
        raise LifecycleError("proposed team preset differs from the reviewed adoption choice")
    if normalized_reasoning(team.get("reasoning")) != normalized_reasoning(metadata.get("reasoning")):
        raise LifecycleError("proposed team reasoning differs from the reviewed adoption choice")
    configs = render_team_configs(team=team, catalog=catalog)
    for consultant in team.get("consultants", []):
        if consultant.get("status") == "active":
            filename = f"consultant-{consultant['id']}.toml"
            consultant["configBaselineSha256"] = sha256_bytes(configs[filename].encode("utf-8"))
    team_errors = validate_team(team, catalog)
    if team_errors:
        raise LifecycleError("proposed team is invalid: " + "; ".join(team_errors))
    records["team"] = team
    project = records.get("project", {}).get("project", {})
    if (
        not isinstance(project, dict)
        or project.get("templateMode") is not False
        or not isinstance(project.get("outcome"), str)
        or not project.get("outcome", "").strip()
        or not isinstance(project.get("currentGoal"), str)
        or not project.get("currentGoal", "").strip()
        or project.get("phase") == "Needs Definition"
    ):
        raise LifecycleError(
            "activation requires reviewed mature-project context with templateMode false, a concrete outcome/current goal, and a non-starter phase"
        )
    state_errors: list[str] = []
    validate_records(records, state_errors)
    if state_errors:
        raise LifecycleError("proposed mature-project state is invalid: " + "; ".join(state_errors))

    starter = root / ".baton/integration/starter"
    if not starter.is_dir() or starter.is_symlink():
        raise LifecycleError("the quarantined Baton starter is missing or unsafe")
    transaction_id = f"activate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    transaction = transaction_directory(root, transaction_id)
    with mutation_lock(root, "lifecycle-activate"):
        locked_metadata = read_project_json(root, METADATA_PATH)
        if locked_metadata != metadata:
            raise LifecycleError("Baton state changed while activation was waiting for the lock; retry")
        integrity = inspect_status(root)
        if not integrity["ok"]:
            raise LifecycleError("cannot activate because Baton-managed files differ from their baselines")
        with tempfile.TemporaryDirectory(prefix="baton-activation-") as raw:
            prepared = Path(raw) / "project"
            active_project_owned: list[str] = []
            for relative in all_entries(starter):
                destination = f".baton/{relative}"
                if destination.startswith(".baton/agents/") or destination == ".baton/dashboard/index.html":
                    continue
                copy_entry(starter, relative, prepared / ".baton")
                active_project_owned.append(destination)
            for name, record in records.items():
                write_json(prepared / f".baton/state/{name}.json", record)
                if f".baton/state/{name}.json" not in active_project_owned:
                    active_project_owned.append(f".baton/state/{name}.json")
            for name in ("overview.md", "direction.md"):
                candidate = proposal_root / "docs" / name
                if candidate.exists() or candidate.is_symlink():
                    if candidate.is_symlink() or not candidate.is_file():
                        raise LifecycleError(f"activation proposal docs/{name} is not a safe regular file")
                    target = prepared / ".baton/docs" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, target)
            dashboard = render_dashboard(records)
            dashboard_path = prepared / ".baton/dashboard/index.html"
            dashboard_path.parent.mkdir(parents=True, exist_ok=True)
            dashboard_path.write_text(dashboard, encoding="utf-8")
            generated: dict[str, str] = {
                ".baton/dashboard/index.html": sha256_bytes(dashboard.encode("utf-8"))
            }
            for filename, content in configs.items():
                relative = f".baton/agents/{filename}"
                path = prepared / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                generated[relative] = sha256_bytes(content.encode("utf-8"))

            desired_codex = render_codex_config(active_agent_names(team))
            managed = metadata.get("managedFiles")
            if not isinstance(managed, dict):
                raise LifecycleError("installed Baton metadata has no managed-file map")
            prior_managed = json.loads(json.dumps(managed))
            codex_target = (
                ".codex/config.toml"
                if ".codex/config.toml" in managed
                else ".baton/integration/codex-config.toml"
            )
            codex_record = managed.get(codex_target)
            if isinstance(codex_record, dict):
                actual = entry_digest(inside(root, codex_target))
                if actual != codex_record.get("baselineSha256"):
                    raise LifecycleError(f"cannot activate because {codex_target} differs from its Baton baseline")
            codex_path = prepared / codex_target
            codex_path.parent.mkdir(parents=True, exist_ok=True)
            codex_path.write_text(desired_codex, encoding="utf-8")

            updated = json.loads(json.dumps(metadata))
            updated["installationStatus"] = "Installed"
            updated["updatedAt"] = utc_now()
            updated["lastTransactionId"] = transaction_id
            managed_blocks = updated.get("managedBlocks")
            if not isinstance(managed_blocks, dict):
                raise LifecycleError("installed Baton metadata has no managed-block map")
            manage_agents = is_sha256(managed_blocks.get("AGENTS.md"))
            if manage_agents:
                agents_path = inside(root, "AGENTS.md", allow_leaf_symlink=False)
                if not agents_path.is_file():
                    raise LifecycleError("cannot activate because managed AGENTS.md is missing or unsafe")
                existing_agents = agents_path.read_text(encoding="utf-8")
                installed_agents, _ = merge_agents(existing_agents, "Installed")
                (prepared / "AGENTS.md").write_text(installed_agents, encoding="utf-8")
                managed_blocks["AGENTS.md"] = sha256_bytes(
                    default_agents_block("Installed").encode("utf-8")
                )
            for relative, digest in generated.items():
                managed[relative] = {"ownership": "generated-config", "baselineSha256": digest}
            managed[codex_target] = {
                "ownership": "integration-link" if codex_target == ".codex/config.toml" else "generated-config",
                "baselineSha256": sha256_bytes(desired_codex.encode("utf-8")),
            }
            preserved_starter = [
                relative
                for relative in managed
                if relative.startswith(".baton/integration/starter/")
            ]
            for relative in preserved_starter:
                managed.pop(relative, None)
            updated["managedFiles"] = dict(sorted(managed.items()))
            owned = set(updated.get("projectOwnedFiles", []))
            owned.update(active_project_owned)
            owned.update(preserved_starter)
            updated["projectOwnedFiles"] = sorted(owned)
            updated["pendingIntegration"] = [
                item for item in updated.get("pendingIntegration", [])
                if "activate" not in item.casefold() and "starter state" not in item.casefold()
            ]
            write_json(prepared / METADATA_PATH, updated)

            add: list[str] = []
            replace = [METADATA_PATH, codex_target]
            if manage_agents:
                replace.append("AGENTS.md")
            for relative in [*active_project_owned, *generated]:
                current = inside(root, relative)
                if current.exists() or current.is_symlink():
                    raise LifecycleError(f"activation target already exists and was preserved: {relative}")
                add.append(relative)

            def finalize_activation(report: dict[str, Any]) -> None:
                report.update(
                    {
                        "transactionId": transaction_id,
                        "mode": "activate",
                        "installationStatus": "Installed",
                        "adoptionTransactionId": metadata.get("lastTransactionId"),
                        "projectOwnedFiles": sorted(active_project_owned),
                        "rollbackLocation": str(transaction / "backup"),
                        "sourceEvidence": {
                            "release": f"https://github.com/{metadata['source']['repository']}/releases/tag/{metadata['source']['tag']}",
                            "manifest": f"https://github.com/{metadata['source']['repository']}/releases/download/{metadata['source']['tag']}/baton-manifest.json",
                            "sourceTree": f"https://github.com/{metadata['source']['repository']}/tree/{metadata['source']['commit']}/packages/consumer",
                        },
                    }
                )
                write_json(transaction / "update-report.json", report)

            report = apply_plan(
                root,
                prepared,
                sorted(set(add)),
                sorted(set(replace)),
                transaction,
                prior_managed,
                finalize_activation,
            )
            return {
                "ok": True,
                "mode": "activate",
                "installationStatus": "Installed",
                "transactionId": transaction_id,
                "reportPath": str(transaction / "update-report.json"),
                "backupPath": str(transaction / "backup"),
            }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    status.add_argument("--project-root", type=Path, required=True)
    status.add_argument("--json", action="store_true")
    for name in ("install", "update"):
        command = commands.add_parser(name)
        command.add_argument("--project-root", type=Path, required=True)
        command.add_argument("--payload-root", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--manifest-sha256", required=True)
        command.add_argument("--payload", choices=("new-project", "adoption"), required=True)
        command.add_argument("--json", action="store_true")
        if name == "install":
            command.add_argument("--project-name", required=True)
            command.add_argument("--project-type", default="software-product")
            command.add_argument("--reasoning-preset", default="medium")
            command.add_argument("--reasoning-json", required=True)
            command.add_argument("--consultants-json", default="[]")
    activate = commands.add_parser("activate")
    activate.add_argument("--project-root", type=Path, required=True)
    activate.add_argument("--from", dest="proposal", type=Path, required=True)
    activate.add_argument("--yes", action="store_true")
    activate.add_argument("--json", action="store_true")
    return result


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print("\nBaton")
    for key in ("mode", "project", "version", "batonVersion", "installationStatus", "transactionId", "reportPath", "backupPath"):
        if payload.get(key) is not None:
            print(f"  {key}: {payload[key]}")


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "status":
            payload = inspect_status(args.project_root)
        elif args.command == "activate":
            payload = activate_adoption(
                project_root=args.project_root,
                proposal=args.proposal,
                assume_yes=args.yes,
            )
        else:
            manifest = read_json(args.manifest)
            actual_manifest_sha = sha256_file(args.manifest)
            if actual_manifest_sha != args.manifest_sha256:
                raise LifecycleError("manifest checksum does not match the verified installer input")
            if args.command == "update":
                payload = update_installation(
                    project_root=args.project_root,
                    payload_root=args.payload_root,
                    manifest=manifest,
                    manifest_sha256=actual_manifest_sha,
                    payload=args.payload,
                )
            else:
                reasoning = json.loads(args.reasoning_json)
                consultants = json.loads(args.consultants_json)
                if not isinstance(reasoning, dict) or set(reasoning) != REASONING_KEYS:
                    raise LifecycleError("reasoning configuration is incomplete")
                reasoning = normalized_reasoning(reasoning)
                if not isinstance(consultants, list) or not all(isinstance(item, str) for item in consultants):
                    raise LifecycleError("Consultant selection must be a JSON string array")
                payload = install_or_adopt(
                    project_root=args.project_root,
                    payload_root=args.payload_root,
                    manifest=manifest,
                    manifest_sha256=actual_manifest_sha,
                    payload=args.payload,
                    project_name=args.project_name,
                    project_type=args.project_type,
                    reasoning_preset=args.reasoning_preset,
                    reasoning=reasoning,
                    selected_consultants=consultants,
                )
        emit(payload, args.json)
        return 0
    except (LifecycleError, MutationLockError, TeamError, OSError, ValueError, json.JSONDecodeError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
