"""Internal lifecycle engine for ``install.sh``.

This module is intentionally not a second public updater.  The supported user
entrypoint is ``install.sh``; it delegates filesystem planning and transactions
here so the same policy is exercised by local, piped, and installed flows.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

sys.dont_write_bytecode = True

from harness_team import (
    TEAM_NAME,
    TeamError,
    configure_existing_team,
    initialize_team,
    load_catalog,
    normalized_reasoning,
    preset_definition,
)
from harness_lock import MutationLockError, mutation_lock


METADATA_NAME = ".agent-harness.json"
SUPPORTED_OWNERSHIP = {"harness-managed", "generated-config", "project-owned"}
RELEASE_MANIFEST_SCHEMA = "agentic-project-harness.release-bundle/v1"
OFFICIAL_REPOSITORY = "FabienGreard/agentic-project-harness"
REASONING_LEVELS = {"inherit", "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
READY_ARRAY_FIELDS = (
    "scope",
    "nonGoals",
    "affectedSystems",
    "acceptanceCriteria",
    "requiredVerification",
    "expectedEvidence",
    "risks",
)


class LifecycleError(RuntimeError):
    """Raised when a lifecycle action cannot continue without risking data."""


def locked_lifecycle_mutation(function):
    @wraps(function)
    def wrapped(*, project_root: Path, **kwargs):
        with mutation_lock(project_root, f"lifecycle-{function.__name__}"):
            return function(project_root=project_root, **kwargs)

    return wrapped


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\0" in raw:
        raise LifecycleError(f"unsafe manifest path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise LifecycleError(f"unsafe manifest path: {raw!r}")
    return path.as_posix()


def _inside(root: Path, relative: str) -> Path:
    relative = _safe_relative(relative)
    parts = PurePosixPath(relative).parts
    candidate = root.joinpath(*parts)
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise LifecycleError(
                f"managed path passes through an existing symbolic link: {relative}"
            )
    parent = candidate.parent.resolve(strict=False)
    resolved_root = root.resolve()
    if parent != resolved_root and resolved_root not in parent.parents:
        raise LifecycleError(f"path escapes root: {relative}")
    return candidate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LifecycleError(f"required JSON file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise LifecycleError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"expected a JSON object in {path}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _write_final_transaction_report(path: Path, value: dict[str, Any]) -> None:
    """Write the final report, with a deterministic failure hook for rollback smoke tests."""
    if os.environ.get("APH_TEST_FAIL_FINAL_REPORT") == "1":
        raise OSError("injected final transaction report failure")
    _write_json_atomic(path, value)


def normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the lifecycle view of either a release or local test manifest."""
    if manifest.get("schema") == RELEASE_MANIFEST_SCHEMA:
        raw_files = manifest.get("files")
        if not isinstance(raw_files, list):
            raise LifecycleError("release manifest files must be an array")
        files: dict[str, dict[str, Any]] = {}
        for record in raw_files:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise LifecycleError("release manifest contains an invalid file record")
            path = _safe_relative(record["path"])
            if path in files:
                raise LifecycleError(f"duplicate manifest path: {path}")
            files[path] = {
                "ownership": record.get("ownership"),
                "sha256": record.get("sha256"),
                "kind": record.get("kind"),
            }
        raw_origins = manifest.get("upgrade_origins", {})
        upgrade_origins: dict[str, dict[str, Any]] = {}
        if isinstance(raw_origins, dict):
            for tag, record in raw_origins.items():
                if isinstance(record, dict):
                    upgrade_origins[tag] = {
                        "sourceCommit": record.get("source_commit"),
                        "manifestSha256": record.get("manifest_sha256"),
                    }
        return {
            "schemaVersion": 1,
            "harnessVersion": manifest.get("version"),
            "stateSchemaVersion": manifest.get("state_schema_version"),
            "channel": manifest.get("channel"),
            "tag": manifest.get("stable_tag"),
            "sourceCommit": manifest.get("source_commit"),
            "supportedUpgradeOrigins": manifest.get("supported_upgrade_origins", []),
            "upgradeOrigins": upgrade_origins,
            "files": files,
            "artifacts": manifest.get("artifacts", {}),
        }
    return manifest


def validate_manifest(manifest: dict[str, Any], source_root: Path | None = None) -> dict[str, Any]:
    manifest = normalize_manifest(manifest)
    required = {
        "schemaVersion": int,
        "harnessVersion": str,
        "stateSchemaVersion": int,
        "channel": str,
        "tag": str,
        "sourceCommit": str,
        "files": dict,
        "upgradeOrigins": dict,
    }
    for key, expected in required.items():
        if not isinstance(manifest.get(key), expected):
            raise LifecycleError(f"manifest {key} is missing or invalid")
    if type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1:
        raise LifecycleError(f"unsupported manifest schema: {manifest['schemaVersion']}")
    if type(manifest["stateSchemaVersion"]) is not int:
        raise LifecycleError("manifest stateSchemaVersion must be an integer")
    if manifest["channel"] not in {"stable", "local-development"}:
        raise LifecycleError(f"unsupported manifest channel: {manifest['channel']}")
    if manifest["channel"] == "stable" and manifest["tag"] != f"v{manifest['harnessVersion']}":
        raise LifecycleError("stable manifest tag does not match harnessVersion")
    if not isinstance(manifest["sourceCommit"], str) or (
        manifest["channel"] == "stable"
        and not _is_hex(manifest["sourceCommit"], 40)
    ):
        raise LifecycleError("manifest sourceCommit is not an immutable commit SHA")

    supported_origins = manifest.get("supportedUpgradeOrigins", [])
    upgrade_origins = manifest["upgradeOrigins"]
    if (
        not isinstance(supported_origins, list)
        or supported_origins != sorted(set(supported_origins))
        or set(upgrade_origins) != set(supported_origins)
    ):
        raise LifecycleError("manifest upgrade origins are incomplete or inconsistent")
    for tag, record in upgrade_origins.items():
        if (
            not isinstance(tag, str)
            or re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is None
            or not isinstance(record, dict)
            or not _is_hex(record.get("sourceCommit"), 40)
            or (
                record.get("manifestSha256") is not None
                and not _is_hex(record.get("manifestSha256"), 64)
            )
        ):
            raise LifecycleError(f"manifest upgrade origin is invalid: {tag!r}")

    seen: set[str] = set()
    for raw_path, record in manifest["files"].items():
        path = _safe_relative(raw_path)
        if path in seen:
            raise LifecycleError(f"duplicate manifest path: {path}")
        seen.add(path)
        if not isinstance(record, dict):
            raise LifecycleError(f"invalid manifest record: {path}")
        ownership = record.get("ownership")
        if ownership not in SUPPORTED_OWNERSHIP:
            raise LifecycleError(f"invalid ownership for {path}: {ownership!r}")
        if not _is_hex(record.get("sha256"), 64):
            raise LifecycleError(f"invalid sha256 for {path}")
        if source_root is not None:
            source = _inside(source_root, path)
            if source.is_symlink():
                _validate_source_symlink(source_root, source)
                actual = sha256_bytes(os.readlink(source).encode("utf-8"))
            elif source.is_file():
                actual = sha256_file(source)
            else:
                raise LifecycleError(f"manifest source entry is missing or unsupported: {path}")
            if actual != record["sha256"]:
                raise LifecycleError(f"manifest checksum mismatch: {path}")
    return manifest


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_source_symlink(root: Path, path: Path) -> None:
    target = os.readlink(path)
    if os.path.isabs(target):
        raise LifecycleError(f"absolute source symlink is not allowed: {path}")
    resolved = (path.parent / target).resolve(strict=False)
    resolved_root = root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise LifecycleError(f"source symlink escapes template root: {path}")


def ownership_for(relative: str) -> str:
    project_owned_exact = {
        "README.md",
        "docs/active-work.md",
        "docs/backlog.md",
        "docs/direction.md",
        "docs/overview.md",
        "docs/project-state.json",
        "docs/thread-registry.md",
    }
    project_owned_prefixes = (
        "docs/decisions/",
        "docs/implementation-reports/",
        "docs/prds/",
        "docs/requirements/",
        "docs/review-packets/",
        "docs/state/",
        "docs/tickets/",
    )
    generated_exact = {".agent-harness.json", ".codex/config.toml", "docs/index.html"}
    if relative in project_owned_exact or relative.startswith(project_owned_prefixes):
        return "project-owned"
    if relative in generated_exact or relative.startswith(".codex/agents/"):
        return "generated-config"
    return "harness-managed"


def _iter_template_entries(root: Path) -> list[str]:
    excluded_parts = {".git", ".artifacts", "__pycache__"}
    entries: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path.suffix == ".pyc" or (path.is_dir() and not path.is_symlink()):
            continue
        entries.append(relative.as_posix())
    return sorted(entries)


def manifest_for_local_source(source_root: Path) -> dict[str, Any]:
    root = source_root.resolve()
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    commit = "local-working-tree"
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    files: dict[str, dict[str, Any]] = {}
    for relative in _iter_template_entries(root):
        path = _inside(root, relative)
        if path.is_symlink():
            _validate_source_symlink(root, path)
            digest = sha256_bytes(os.readlink(path).encode("utf-8"))
            kind = "symlink"
        else:
            digest = sha256_file(path)
            kind = "file"
        files[relative] = {
            "ownership": ownership_for(relative),
            "sha256": digest,
            "kind": kind,
        }
    manifest = {
        "schemaVersion": 1,
        "harnessVersion": version,
        "stateSchemaVersion": 1,
        "channel": "local-development",
        "tag": "local-working-tree",
        "sourceCommit": commit,
        "supportedUpgradeOrigins": [],
        "upgradeOrigins": {},
        "files": files,
        "artifacts": {},
    }
    return validate_manifest(manifest, root)


def manifest_for_prepared_source(
    source_root: Path, base_manifest: dict[str, Any]
) -> dict[str, Any]:
    base = validate_manifest(base_manifest)
    prepared = dict(base)
    prepared_files: dict[str, dict[str, Any]] = {}
    for relative in _iter_template_entries(source_root):
        if relative == METADATA_NAME:
            continue
        path = _inside(source_root, relative)
        if not path.exists() and not path.is_symlink():
            continue
        digest = _entry_digest(path)
        if digest is None:
            raise LifecycleError(f"prepared source contains unsupported entry: {relative}")
        prepared_files[relative] = {
            "ownership": ownership_for(relative),
            "sha256": digest,
            "kind": "symlink" if path.is_symlink() else "file",
        }
    prepared["files"] = prepared_files
    return validate_manifest(prepared, source_root)


def _copy_template(source_root: Path, destination_root: Path, manifest: dict[str, Any]) -> None:
    destination_root.mkdir(parents=True, exist_ok=True)
    normalized = validate_manifest(manifest, source_root)
    for relative in normalized["files"]:
        if relative == METADATA_NAME:
            continue
        _copy_entry(source_root, relative, destination_root)


def _configure_reasoning(root: Path, reasoning: dict[str, str]) -> None:
    team_path = root / TEAM_NAME
    if team_path.is_file():
        tool_path = root / "tools/harness_team.py"
        spec = importlib.util.spec_from_file_location(
            f"aph_origin_team_{uuid.uuid4().hex}", tool_path
        )
        if spec is None or spec.loader is None:
            raise LifecycleError("could not load the pinned release team renderer")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            module.configure_existing_team(
                project_root=root,
                team=_read_json(team_path),
                reasoning=module.normalized_reasoning(reasoning),
            )
        except (OSError, RuntimeError) as error:
            raise LifecycleError(
                f"pinned release team renderer failed: {error}"
            ) from error
        return
    mapping = {
        "projectDirector": "project-director.toml",
        "deliveryLead": "delivery-lead.toml",
        "specialistLead": "specialist-lead.toml",
        "executionWorker": "execution-worker.toml",
        "harnessEvaluator": "harness-evaluator.toml",
    }
    for role, filename in mapping.items():
        level = reasoning[role]
        if level not in REASONING_LEVELS:
            raise LifecycleError(f"unsupported reasoning level for {role}: {level}")
        path = root / ".codex/agents" / filename
        text = path.read_text(encoding="utf-8")
        text = re.sub(r'^model_reasoning_effort\s*=\s*"[^"]+"\n', "", text, flags=re.MULTILINE)
        if level != "inherit":
            marker = re.search(r"^description\s*=.*\n", text, flags=re.MULTILINE)
            if marker is None:
                raise LifecycleError(f"agent config lacks description: {path}")
            text = text[: marker.end()] + f'model_reasoning_effort = "{level}"\n' + text[marker.end() :]
        path.write_text(text, encoding="utf-8")


def _configure_state(root: Path, project_name: str) -> None:
    project_path = root / "docs/state/project.json"
    if project_path.is_file():
        record = _read_json(project_path)
        record["project"]["name"] = project_name
        record["project"]["lastVerified"] = datetime.now(timezone.utc).date().isoformat()
        operation = {
            "schemaVersion": 1,
            "operation": "replace-records",
            "records": {"project": record},
        }
        operation_path = root / ".state-install-operation.json"
        _write_json_atomic(operation_path, operation)
        try:
            subprocess.run(
                [sys.executable, str(root / "tools/harness_state.py"), "apply", str(operation_path), "--json"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise LifecycleError(
                "generated project state could not be initialized: "
                + (error.stderr.strip() or error.stdout.strip())
            ) from error
        finally:
            operation_path.unlink(missing_ok=True)
    legacy_path = root / "docs/project-state.json"
    if legacy_path.is_file():
        legacy = _read_json(legacy_path)
        if isinstance(legacy.get("project"), dict):
            legacy["project"]["name"] = project_name
            legacy["project"]["lastVerified"] = datetime.now(timezone.utc).date().isoformat()
            _write_json_atomic(legacy_path, legacy)


def _project_readme(
    *,
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    team: dict[str, Any],
) -> str:
    project_label = team["presetLabel"]
    active_consultants = [
        item for item in team["consultants"] if item["status"] == "active"
    ]
    consultant_rows = [
        f"| Consultant | {item['title']} | `{reasoning['consultants']}` |"
        for item in active_consultants
    ]
    reasoning_rows = "\n".join(
        [
            "| Common role | Configured persona | Reasoning |",
            "| --- | --- | --- |",
            f"| Management | {team['management']['title']} | `{reasoning['management']}` |",
            f"| Operations | {team['operations']['title']} | `{reasoning['operations']}` |",
            *consultant_rows,
            f"| Contractors | Selected per assignment | `{reasoning['contractors']}` |",
            f"| Internal Audit | Hidden harness evaluator | `{reasoning['internalAudit']}` |",
        ]
    )
    consultants_prompt = (
        ", ".join(item["title"] for item in active_consultants)
        if active_consultants
        else "none yet"
    )
    prompt = f"""Bootstrap {project_name} using the installed Agentic Project Harness. The installer selected the {project_label} operating preset; use its professional context but never invent project direction.

First read AGENTS.md, every applicable rule under .agents/rules/, the project-scoped skills under .agents/skills/, .codex/config.toml, the active role configurations under .codex/agents/, docs/state/*.json, docs/index.html, docs/overview.md, docs/direction.md, docs/workflow.md, and the relevant role instructions completely. Verify the live repository before trusting starter claims.

This first run is governance-only. Do not implement the project, install an application stack, contact external systems, publish, or invent product or business direction. The common operating layer is Management, Operations, Consultants, and Contractors. Management is configured as {team['management']['title']}; Operations is configured as {team['operations']['title']}; starting Consultants are {consultants_prompt}. Internal Audit is harness maintenance, not project QA or a project-team member. Confirm the generated `Standard` test-rigor default and explicitly no default human-review stage, then ask only for decisions that materially change intended outcomes, constraints, assurance defaults, per-ticket human-review timing, or the configured team. Record user-authorized assurance overrides with a reason. Use python3 tools/harness_state.py apply with a schema-valid operation to customize project state, run python3 tools/harness_state.py check and python3 tools/harness_eval.py --strict, report blockers, and leave one explicit baton and wake trigger.

Management, Operations, and each active Consultant are permanent top-level tasks. Their task messages are the sole wake mechanism. Never create, resume, recreate, attach, or otherwise operate a Codex persistent goal for them, even when complete goal controls exist. This repository policy supersedes older onboarding prompts requesting a goal. Repository milestone goals in docs/state/goals.json are unrelated. If a legacy goal auto-resumes a task without a new message, perform no speculative work or goal operation, report it for user or administrative removal, and end immediately."""
    return f"""# {project_name}

This project uses [Agentic Project Harness](https://github.com/{OFFICIAL_REPOSITORY}) for Codex.

- Project type: **{project_label}**
- Reasoning setup: **{reasoning_preset}**
- Codex permissions: **on-request approval with Auto-review in a workspace-write sandbox**

## Start here

1. Review `AGENTS.md`, `docs/index.html`, and `.codex/agents/`.
2. Open this directory in Codex using the Management reasoning level.
3. Copy the complete **First project prompt** below into that task.
4. Approve the customized governance baseline before implementation begins.

## First project prompt

```text
{prompt}
```

## Configured reasoning

{reasoning_rows}

Explicit level support depends on the Codex model selected at runtime. `inherit` means no role-specific override is written.

Invoke `$hire-consultant` to add a curated or schema-valid custom Consultant and `$fire-consultant` to offboard one transactionally. Both skills use the deterministic team engine. Operations selects disposable Contractors from the preset capability bench when work is Ready.

Reusable harness guidance is preserved in [HARNESS.md](HARNESS.md).
"""


def prepare_project_source(
    *,
    source_root: Path,
    manifest: dict[str, Any],
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    selected_consultants: list[str],
    destination: Path,
) -> dict[str, Any]:
    _copy_template(source_root, destination, manifest)
    reasoning = normalized_reasoning(reasoning)
    team = initialize_team(
        project_root=destination,
        preset_id=project_type,
        selected=selected_consultants,
        reasoning=reasoning,
    )
    _configure_state(destination, project_name)
    (destination / "README.md").write_text(
        _project_readme(
            project_name=project_name,
            project_type=project_type,
            reasoning_preset=reasoning_preset,
            reasoning=reasoning,
            team=team,
        ),
        encoding="utf-8",
    )
    return manifest_for_prepared_source(destination, manifest)


def _extract_source_archive(
    archive_path: Path, destination: Path, *, expected_commit: str
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise LifecycleError("legacy stable source archive is empty")
        roots = {PurePosixPath(member.name).parts[0] for member in members if member.name}
        if len(roots) != 1:
            raise LifecycleError("legacy stable source archive has no single root")
        root_name = next(iter(roots))
        if not root_name.endswith(expected_commit):
            raise LifecycleError("pinned stable archive root does not match its commit")
        names: set[str] = set()
        symlinks: set[PurePosixPath] = set()
        for member in members:
            raw = PurePosixPath(member.name)
            if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
                raise LifecycleError(f"unsafe pinned archive path: {member.name}")
            if member.name in names:
                raise LifecycleError(f"duplicate pinned archive path: {member.name}")
            names.add(member.name)
            if member.issym():
                symlinks.add(raw)
        for member in members:
            raw = PurePosixPath(member.name)
            if any(parent in symlinks for parent in raw.parents):
                raise LifecycleError(
                    f"pinned archive path passes through a symlink: {member.name}"
                )
        for member in members:
            raw = PurePosixPath(member.name)
            parts = raw.parts[1:]
            if not parts:
                continue
            relative = PurePosixPath(*parts)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                target.mkdir(exist_ok=True)
            elif member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise LifecycleError(f"cannot read legacy archive member: {member.name}")
                target.write_bytes(handle.read())
                target.chmod(member.mode & 0o777)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                if link.is_absolute():
                    raise LifecycleError(f"unsafe legacy archive symlink: {member.name}")
                resolved = (target.parent / member.linkname).resolve(strict=False)
                destination_root = destination.resolve()
                if resolved != destination_root and destination_root not in resolved.parents:
                    raise LifecycleError(f"legacy archive symlink escapes: {member.name}")
                target.symlink_to(member.linkname)
            else:
                raise LifecycleError(f"unsupported pinned archive entry: {member.name}")
    if not (destination / "VERSION").is_file():
        raise LifecycleError(f"legacy archive root {root_name!r} is not a harness release")
    return destination


def _pinned_stable_source(tag: str, commit: str, destination: Path) -> Path:
    if not _is_hex(commit, 40):
        raise LifecycleError(f"stable origin {tag} has no immutable commit anchor")
    override = os.environ.get("APH_PINNED_STABLE_SOURCE_DIR")
    if override:
        source = Path(override).expanduser().resolve()
        try:
            head = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD^{commit}"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            dirty = subprocess.run(
                ["git", "-C", str(source), "status", "--porcelain=v1"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise LifecycleError(
                "APH_PINNED_STABLE_SOURCE_DIR must be a clean Git checkout"
            ) from error
        if head != commit or dirty:
            raise LifecycleError(
                "APH_PINNED_STABLE_SOURCE_DIR does not match the immutable origin commit"
            )
        if not (source / "VERSION").is_file() or (source / "VERSION").read_text(
            encoding="utf-8"
        ).strip() != tag[1:]:
            raise LifecycleError(
                "APH_PINNED_STABLE_SOURCE_DIR does not match the origin version"
            )
        return source
    archive_path = destination.parent / f"{tag}.tar.gz"
    url = f"https://codeload.github.com/{OFFICIAL_REPOSITORY}/tar.gz/{commit}"
    try:
        urllib.request.urlretrieve(url, archive_path)
    except OSError as error:
        raise LifecycleError(f"could not download pinned stable baseline {tag}: {error}") from error
    source = _extract_source_archive(
        archive_path, destination, expected_commit=commit
    )
    if (source / "VERSION").read_text(encoding="utf-8").strip() != tag[1:]:
        raise LifecycleError("pinned stable source VERSION does not match its tag")
    return source


def reconstruct_legacy_metadata(
    *,
    metadata: dict[str, Any],
    working_root: Path,
    scratch_root: Path,
    pinned_commit: str,
) -> dict[str, Any]:
    tag = metadata.get("ref")
    if (
        type(metadata.get("schemaVersion")) is not int
        or metadata.get("schemaVersion") != 1
        or metadata.get("installed") is not True
        or metadata.get("provider") != "codex"
        or metadata.get("source") != OFFICIAL_REPOSITORY
        or metadata.get("sourceMode") != "remote"
        or not isinstance(tag, str)
        or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag)
        or metadata.get("harnessVersion") != tag[1:]
    ):
        raise LifecycleError(
            "legacy provenance is not an official immutable stable tag; no files were changed"
        )
    reasoning = metadata.get("reasoning")
    if not isinstance(reasoning, dict) or set(reasoning) != {
        "projectDirector",
        "deliveryLead",
        "specialistLead",
        "executionWorker",
        "harnessEvaluator",
    }:
        raise LifecycleError("legacy reasoning baseline cannot be reconstructed safely")
    missing_legacy_specialist = reasoning.get("specialistLead") is None
    reasoning = dict(reasoning)
    if missing_legacy_specialist:
        reasoning["specialistLead"] = "high"
    if any(value not in REASONING_LEVELS for value in reasoning.values()):
        raise LifecycleError("legacy reasoning baseline contains an unsupported level")
    source = _pinned_stable_source(
        tag, pinned_commit, scratch_root / "legacy-source"
    )
    source_manifest = manifest_for_local_source(source)
    prepared = scratch_root / "legacy-prepared"
    _copy_template(source, prepared, source_manifest)
    _configure_reasoning(prepared, reasoning)
    if missing_legacy_specialist:
        (prepared / ".codex/agents/specialist-lead.toml").unlink(missing_ok=True)
    prepared_manifest = manifest_for_prepared_source(prepared, source_manifest)
    managed: dict[str, dict[str, str]] = {}
    for relative, record in prepared_manifest["files"].items():
        if record["ownership"] == "project-owned":
            continue
        digest = _entry_digest(_inside(prepared, relative))
        if digest is not None:
            managed[relative] = {
                "ownership": record["ownership"],
                "baselineSha256": digest,
            }
    project_name = "Project"
    legacy_state = working_root / "docs/project-state.json"
    if legacy_state.is_file():
        legacy_record = _read_json(legacy_state)
        legacy_project = legacy_record.get("project")
        if isinstance(legacy_project, dict) and isinstance(
            legacy_project.get("name"), str
        ):
            project_name = legacy_project["name"]
    return {
        "schemaVersion": 2,
        "harnessVersion": metadata["harnessVersion"],
        "stateSchemaVersion": 0,
        "provider": "codex",
        "installationStatus": "Legacy",
        "projectName": project_name,
        "projectType": metadata.get("projectType", "other"),
        "reasoningPreset": metadata.get("reasoningPreset", "custom"),
        "reasoning": reasoning,
        "source": {
            "repository": OFFICIAL_REPOSITORY,
            "channel": "stable",
            "tag": tag,
            "commit": pinned_commit,
            "manifestSha256": None,
        },
        "installedAt": metadata.get("installedAt"),
        "updatedAt": metadata.get("installedAt"),
        "lastTransactionId": None,
        "managedFiles": managed,
        "appliedMigrations": [
            {
                "id": "preset-team-v1",
                "appliedAt": utc_now(),
                "preserved": [],
            }
        ],
    }


def _legacy_markdown_ticket(
    *, project_root: Path, relative_path: str | None
) -> dict[str, Any]:
    if not isinstance(relative_path, str) or not relative_path:
        return {}
    try:
        path = _inside(project_root, relative_path)
    except LifecycleError:
        return {}
    if not path.is_file() or path.suffix.casefold() != ".md":
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    title = ""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("# ") and not title:
            heading = line[2:].strip()
            title = re.split(r"\s+[—-]\s+", heading, maxsplit=1)[-1]
            continue
        if line.startswith("## "):
            current = line[3:].strip().casefold()
            sections[current] = []
            continue
        if current is not None and line.strip():
            value = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
            if value:
                sections[current].append(value)

    def values(*names: str) -> list[str]:
        for name in names:
            found = sections.get(name.casefold(), [])
            if found:
                return found
        return []

    required_verification = values("Required verification", "Verification")
    return {
        "title": title,
        "objective": " ".join(values("Objective")),
        "scope": values("Scope"),
        "nonGoals": values("Non-goals", "Explicit non-goals"),
        "affectedSystems": values("Affected systems or outputs", "Expected affected systems"),
        "acceptanceCriteria": values("Acceptance criteria"),
        "requiredVerification": required_verification,
        "expectedEvidence": values("Expected evidence", "Evidence expectations") or required_verification,
        "risks": values("Risks", "Known risks"),
        "blockers": values("Blockers / open decisions", "Blockers"),
        "openDecisions": values("Blockers / open decisions", "Open decisions"),
    }


def migrate_legacy_state(
    *, project_root: Path, prepared_root: Path, plan: dict[str, Any]
) -> list[str]:
    legacy_path = project_root / "docs/project-state.json"
    if not legacy_path.is_file():
        plan["conflicts"].append(
            _action("docs/project-state.json", "project-owned", "legacy state source is missing")
        )
        plan["atomicBlocked"] = True
        return []
    legacy = _read_json(legacy_path)
    required = {"templateMode", "project", "baton", "tickets", "activeWork", "humanReviews"}
    if (
        not required.issubset(legacy)
        or not isinstance(legacy.get("project"), dict)
        or not isinstance(legacy.get("baton"), dict)
        or not isinstance(legacy.get("tickets"), list)
        or not isinstance(legacy.get("activeWork"), list)
        or not isinstance(legacy.get("humanReviews"), list)
    ):
        plan["conflicts"].append(
            _action("docs/project-state.json", "project-owned", "legacy state shape is ambiguous")
        )
        plan["atomicBlocked"] = True
        return []

    project_record = {
        "schemaVersion": 1,
        "recordType": "project",
        "project": {
            "name": legacy["project"].get("name", "Project"),
            "outcome": legacy["project"].get("outcome", ""),
            "currentGoal": "",
            "agentProvider": "codex",
            "phase": legacy["project"].get("phase", "Needs Definition"),
            "templateMode": bool(legacy.get("templateMode", False)),
            "lastVerified": legacy["project"].get("lastVerified", ""),
            "assuranceDefaults": {
                "testRigor": "Standard",
                "humanReviewStages": [],
            },
        },
        "baton": {
            "owner": legacy["baton"].get("owner", "Management"),
            "action": legacy["baton"].get("action", "Review migrated state"),
            "returnTrigger": legacy["baton"].get("returnTrigger", "Migrated state is approved"),
        },
    }
    legacy_ticket_statuses = {
        "Idea": "Backlog",
        "Needs Definition": "Backlog",
        "PRD in Progress": "Backlog",
        "Ready": "Ready",
        "Queued": "Ready",
        "In Progress": "In Progress",
        "Dispatched": "In Progress",
        "Blocked": "Blocked",
        "Integration": "In Progress",
        "Verification": "In Progress",
        "In Review": "In Review",
        "Completed": "Done",
        "Abandoned": "Cancelled",
    }
    legacy_ownership_steps = {
        "Queued": "Assigned",
        "Dispatched": "Assigned",
        "In Progress": "Building",
        "Blocked": "Blocked",
        "Integration": "Integrating",
        "Verification": "Verifying",
        "In Review": "Awaiting Review",
    }
    tickets = []
    active_ticket_ids = {
        item.get("ticket")
        for item in legacy.get("activeWork", [])
        if isinstance(item, dict)
    }
    active_consultant_ids = [
        item.get("id")
        for item in _read_json(prepared_root / TEAM_NAME).get("consultants", [])
        if isinstance(item, dict) and item.get("status") == "active"
    ]
    legacy_narratives: list[str] = []
    for ticket in legacy.get("tickets", []):
        if not isinstance(ticket, dict):
            plan["conflicts"].append(
                _action("docs/project-state.json", "project-owned", "legacy ticket is not an object")
            )
            continue
        narrative = _legacy_markdown_ticket(
            project_root=project_root, relative_path=ticket.get("path")
        )
        needs_consultant_review = bool(
            ticket.get(
                "requiresConsultantReview",
                ticket.get("requiresSpecialistReview", False),
            )
        )
        if needs_consultant_review and not active_consultant_ids:
            plan["conflicts"].append(
                _action(
                    ticket.get("path") or "docs/project-state.json",
                    "project-owned",
                    f"legacy ticket {ticket.get('id')} requires Consultant review but no active Consultant is configured",
                )
            )
        record = {
            "id": ticket.get("id"),
            "title": ticket.get("title") or narrative.get("title") or ticket.get("id") or "Migrated ticket",
            "status": legacy_ticket_statuses.get(ticket.get("status"), ticket.get("status")),
            "priority": ticket.get("priority"),
            "owner": ticket.get("owner"),
            "goal": "MIGRATED-GOAL-1",
            "dependencies": ticket.get("dependencies", []),
            "objective": ticket.get("objective") or narrative.get("objective", ""),
            "scope": ticket.get("scope") or narrative.get("scope", []),
            "nonGoals": ticket.get("nonGoals") or narrative.get("nonGoals", []),
            "affectedSystems": ticket.get("affectedSystems") or narrative.get("affectedSystems", []),
            "acceptanceCriteria": ticket.get("acceptanceCriteria") or narrative.get("acceptanceCriteria", []),
            "requiredVerification": ticket.get("requiredVerification") or narrative.get("requiredVerification", []),
            "expectedEvidence": ticket.get("expectedEvidence") or narrative.get("expectedEvidence", []),
            "risks": ticket.get("risks") or narrative.get("risks", []),
            "requiredConsultantIds": (
                [active_consultant_ids[0]] if needs_consultant_review else []
            ),
            "assurance": {
                "testRigor": "Standard",
                "humanReviewStages": (
                    ["Acceptance"]
                    if bool(ticket.get("requiresHumanReview", False))
                    else []
                ),
                "overrideReason": (
                    "Migrated legacy human-review requirement"
                    if bool(ticket.get("requiresHumanReview", False))
                    else ""
                ),
            },
            "blockers": ticket.get("blockers") or narrative.get("blockers", []),
            "openDecisions": ticket.get("openDecisions") or narrative.get("openDecisions", []),
            **({"narrativePath": ticket["path"]} if ticket.get("path") else {}),
            **({"reportPath": ticket["reportPath"]} if ticket.get("reportPath") else {}),
        }
        if ticket.get("path"):
            legacy_narratives.append(ticket["path"])
        if record["status"] in {"Ready", "In Progress", "Blocked", "In Review", "Done"}:
            missing = [
                field
                for field in ("objective", *READY_ARRAY_FIELDS)
                if not record.get(field)
            ]
            if missing and record["id"] in active_ticket_ids:
                plan["conflicts"].append(
                    _action(
                        ticket.get("path") or "docs/project-state.json",
                        "project-owned",
                        f"active legacy ticket {record['id']} lacks structured readiness fields: {', '.join(missing)}",
                    )
                )
            elif missing:
                prior_status = record["status"]
                record["status"] = "Backlog"
                record["blockers"] = [
                    *record["blockers"],
                    f"Legacy migration requires readiness review; prior status was {prior_status}",
                ]
        tickets.append(record)
    goals = []
    if tickets:
        statuses = {ticket.get("status") for ticket in tickets}
        evidence_paths = sorted(
            {
                ticket["reportPath"]
                for ticket in tickets
                if ticket.get("reportPath")
            }
        )
        if statuses == {"Done"}:
            goal_status = "Done"
        elif statuses & {"In Review"}:
            goal_status = "Review"
        elif active_ticket_ids:
            goal_status = "Active"
        elif statuses & {"Ready", "In Progress", "Blocked"}:
            goal_status = "Ready"
        else:
            goal_status = "Needs Definition"
        goal = {
            "id": "MIGRATED-GOAL-1",
            "title": "Continue migrated project work",
            "status": goal_status,
            "priority": "P1",
            "owner": legacy["baton"].get("owner", "Management"),
            "objective": "Review and continue the work preserved from the legacy project state",
            "context": "The legacy project's tickets and evidence were preserved for explicit review",
            "dependencies": [],
            "blockers": [],
            "decisionPaths": [],
            "evidencePaths": evidence_paths,
        }
        if goal_status == "Done":
            goal["completedAt"] = datetime.now(timezone.utc).date().isoformat()
            goal["resultSummary"] = "The migrated tickets were already recorded as completed; linked reports preserve their evidence"
        else:
            project_record["project"]["currentGoal"] = goal["id"]
        goals.append(goal)
    ownership = []
    for item in legacy.get("activeWork", []):
        if not isinstance(item, dict):
            continue
        migrated = dict(item)
        migrated["status"] = legacy_ownership_steps.get(item.get("status"), item.get("status"))
        ownership.append(migrated)
    reviews = []
    for review in legacy.get("humanReviews", []):
        if not isinstance(review, dict) or not review.get("ticket"):
            plan["conflicts"].append(
                _action("docs/project-state.json", "project-owned", "legacy review has no ticket reference")
            )
            continue
        reviews.append(dict(review))
    if plan["conflicts"]:
        plan["atomicBlocked"] = True
        return []

    records = {
        "project": project_record,
        "goals": {"schemaVersion": 1, "recordType": "goals", "goals": goals},
        "tickets": {"schemaVersion": 1, "recordType": "tickets", "tickets": tickets},
        "ownership": {"schemaVersion": 1, "recordType": "ownership", "ownership": ownership},
        "reviews": {
            "schemaVersion": 1,
            "recordType": "reviews",
            "reviews": reviews,
            "consultantReviews": [],
        },
    }
    operation_path = prepared_root / ".legacy-state-operation.json"
    _write_json_atomic(
        operation_path,
        {
            "schemaVersion": 1,
            "operation": "replace-records",
            "records": {
                name: record for name, record in records.items() if name != "team"
            },
        },
    )
    try:
        process = subprocess.run(
            [sys.executable, str(prepared_root / "tools/harness_state.py"), "apply", str(operation_path), "--json"],
            cwd=prepared_root,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        operation_path.unlink(missing_ok=True)
    if process.returncode:
        plan["conflicts"].append(
            _action("docs/project-state.json", "project-owned", "legacy state does not satisfy the target schema")
        )
        plan["atomicBlocked"] = True
        return []

    migrated_paths = [
        "docs/state/project.json",
        "docs/state/goals.json",
        "docs/state/tickets.json",
        "docs/state/ownership.json",
        "docs/state/reviews.json",
    ]
    plan["preserve"] = [
        item for item in plan["preserve"] if item["path"] not in migrated_paths
    ]
    plan["add"] = [item for item in plan["add"] if item["path"] not in migrated_paths]
    for relative in migrated_paths:
        destination = project_root / relative
        if destination.exists() or destination.is_symlink():
            plan["conflicts"].append(
                _action(relative, "project-owned", "existing target state is ambiguous during legacy migration")
            )
        else:
            plan["add"].append(
                _action(relative, "project-owned", "validated legacy state migration")
            )
    plan["atomicBlocked"] = bool(plan["conflicts"])
    return sorted(
        {
            relative
            for relative in (
                "docs/project-state.json",
                "docs/backlog.md",
                "docs/active-work.md",
                *legacy_narratives,
            )
            if (project_root / relative).exists()
        }
    )


def state_evidence_paths(records: dict[str, dict[str, Any]]) -> list[str]:
    """Return repository files that target-state validation must be able to see."""
    paths: set[str] = set()
    for goal in records.get("goals", {}).get("goals", []):
        if not isinstance(goal, dict):
            continue
        if isinstance(goal.get("narrativePath"), str):
            paths.add(goal["narrativePath"])
        for field in ("decisionPaths", "evidencePaths"):
            for value in goal.get(field, []):
                if isinstance(value, str):
                    paths.add(value)
    for ticket in records.get("tickets", {}).get("tickets", []):
        if not isinstance(ticket, dict):
            continue
        if isinstance(ticket.get("narrativePath"), str):
            paths.add(ticket["narrativePath"])
        if (
            ticket.get("status") == "Done"
            and isinstance(ticket.get("reportPath"), str)
        ):
            paths.add(ticket["reportPath"])
    reviews = records.get("reviews", {})
    for review in reviews.get("reviews", []):
        if (
            isinstance(review, dict)
            and review.get("status") == "Approved"
            and isinstance(review.get("path"), str)
        ):
            paths.add(review["path"])
    for review in reviews.get("consultantReviews", []):
        if not isinstance(review, dict):
            continue
        for value in review.get("evidencePaths", []):
            if isinstance(value, str):
                paths.add(value)
    return sorted(paths)


def stage_state_evidence(
    *,
    project_root: Path,
    prepared_root: Path,
    records: dict[str, dict[str, Any]],
) -> list[str]:
    """Copy preserved evidence into the disposable target validation view."""
    resolved_project_root = project_root.resolve()
    staged: list[str] = []
    for relative in state_evidence_paths(records):
        source = _inside(project_root, relative)
        if source.is_symlink() or not source.is_file():
            raise LifecycleError(
                f"installed state evidence is missing or not a regular file: {relative}"
            )
        resolved_source = source.resolve(strict=True)
        if (
            resolved_source != resolved_project_root
            and resolved_project_root not in resolved_source.parents
        ):
            raise LifecycleError(
                f"state evidence path escapes the installed project: {relative}"
            )
        destination = _inside(prepared_root, relative)
        if destination.exists() or destination.is_symlink():
            # A target-release file is already sufficient for existence-based
            # state validation. Never let installed evidence overwrite target
            # bytes or influence the target manifest/baseline.
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved_source, destination)
        staged.append(relative)
    return staged


def remove_staged_state_evidence(
    *, prepared_root: Path, staged_paths: list[str]
) -> None:
    """Remove validation-only evidence before calculating target baselines."""
    for relative in staged_paths:
        candidate = _inside(prepared_root, relative)
        if candidate.is_symlink() or not candidate.is_file():
            raise LifecycleError(
                f"validation-only state evidence changed unexpectedly: {relative}"
            )
        candidate.unlink()


def hydrate_current_state(
    *, project_root: Path, prepared_root: Path
) -> list[str]:
    records: dict[str, dict[str, Any]] = {}
    names = ["project", "goals", "tickets", "ownership", "reviews"]
    if (project_root / TEAM_NAME).is_file():
        names.append("team")
    for name in names:
        relative = f"docs/state/{name}.json"
        source = _inside(project_root, relative)
        if not source.is_file():
            raise LifecycleError(
                f"installed state schema 1 is missing canonical record: {relative}"
            )
        record = _read_json(source)
        records[name] = record
        destination = _inside(prepared_root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    staged_paths = stage_state_evidence(
        project_root=project_root,
        prepared_root=prepared_root,
        records=records,
    )
    operation_path = prepared_root / ".state-hydration-operation.json"
    _write_json_atomic(
        operation_path,
        {
            "schemaVersion": 1,
            "operation": "replace-records",
            "records": {
                name: record for name, record in records.items() if name != "team"
            },
        },
    )
    try:
        process = subprocess.run(
            [
                sys.executable,
                str(prepared_root / "tools/harness_state.py"),
                "apply",
                str(operation_path),
                "--json",
            ],
            cwd=prepared_root,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        operation_path.unlink(missing_ok=True)
    if process.returncode:
        raise LifecycleError(
            "installed canonical state cannot be carried into the target release: "
            + (process.stderr.strip() or process.stdout.strip())
        )
    return staged_paths


def refresh_prepared_dashboard(prepared_root: Path) -> None:
    operation_path = prepared_root / ".dashboard-refresh-operation.json"
    _write_json_atomic(
        operation_path,
        {
            "schemaVersion": 1,
            "operation": "replace-records",
            "records": {
                "project": _read_json(prepared_root / "docs/state/project.json")
            },
        },
    )
    try:
        process = subprocess.run(
            [
                sys.executable,
                str(prepared_root / "tools/harness_state.py"),
                "apply",
                str(operation_path),
                "--json",
            ],
            cwd=prepared_root,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        operation_path.unlink(missing_ok=True)
    if process.returncode:
        raise LifecycleError(
            "target dashboard could not be refreshed after team migration: "
            + (process.stderr.strip() or process.stdout.strip())
        )


def verify_installed_baselines(
    *,
    project_root: Path,
    source_root: Path,
    source_manifest: dict[str, Any],
    metadata: dict[str, Any],
    scratch_root: Path,
) -> None:
    """Rebuild trusted baselines from an immutable source before planning writes."""
    managed = metadata.get("managedFiles")
    reasoning = metadata.get("reasoning")
    if not isinstance(managed, dict) or not isinstance(reasoning, dict):
        raise LifecycleError("installed lifecycle baselines are missing or invalid")
    try:
        normalized_reasoning(reasoning)
    except TeamError as error:
        raise LifecycleError("installed reasoning provenance is invalid") from error
    prepared = scratch_root / "verified-installed-baseline"
    _copy_template(source_root, prepared, source_manifest)
    state_schema = metadata.get("stateSchemaVersion", 0)
    if type(state_schema) is int and state_schema == 1:
        staged_paths = hydrate_current_state(
            project_root=project_root, prepared_root=prepared
        )
        remove_staged_state_evidence(
            prepared_root=prepared, staged_paths=staged_paths
        )
    elif type(state_schema) is not int or state_schema != 0:
        raise LifecycleError(
            f"installed state schema {state_schema!r} cannot be reconstructed"
        )
    _configure_reasoning(prepared, reasoning)
    prepared_manifest = manifest_for_prepared_source(prepared, source_manifest)
    expected = {
        path: record
        for path, record in prepared_manifest["files"].items()
        if record["ownership"] != "project-owned"
    }
    pending_records = metadata.get("pendingIntegration", [])
    if not isinstance(pending_records, list):
        raise LifecycleError("installed pending-integration metadata is invalid")
    pending = {
        item.get("path")
        for item in pending_records
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    failures: list[str] = []
    for path, record in sorted(expected.items()):
        installed = managed.get(path)
        if installed is None and path in pending:
            continue
        if not isinstance(installed, dict):
            failures.append(f"{path}: trusted baseline is missing")
            continue
        if installed.get("ownership") == "project-owned":
            continue
        if (
            installed.get("ownership") != record["ownership"]
            or installed.get("baselineSha256") != record["sha256"]
        ):
            failures.append(f"{path}: baseline differs from immutable release content")
    for raw_path, record in sorted(managed.items()):
        try:
            path = _safe_relative(raw_path)
        except LifecycleError as error:
            failures.append(str(error))
            continue
        if not isinstance(record, dict):
            failures.append(f"{path}: baseline record is invalid")
            continue
        ownership = record.get("ownership")
        baseline = record.get("baselineSha256")
        if ownership not in SUPPORTED_OWNERSHIP or not _is_hex(baseline, 64):
            failures.append(f"{path}: baseline record is invalid")
        elif ownership != "project-owned" and path not in expected:
            failures.append(f"{path}: managed path is not part of the immutable release")
    if failures:
        raise LifecycleError(
            "installed baseline provenance cannot be verified; no files were changed: "
            + "; ".join(failures)
        )


def _version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise LifecycleError(f"unsupported stable version: {value!r}")
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    if match is None:
        raise LifecycleError(f"unsupported stable version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _confirm_plan(
    *, from_version: str, to_version: str, plan: dict[str, Any], assume_yes: bool
) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty() and not Path("/dev/tty").exists():
        raise LifecycleError("update confirmation requires a terminal or --yes")
    lines = [
        "",
        f"Update plan: {from_version} -> {to_version}",
        f"  Add: {len(plan.get('add', []))}",
        f"  Replace: {len(plan.get('replace', []))}",
        f"  Retire untouched managed files: {len(plan.get('retire', []))}",
        f"  Preserve project-owned files: {len(plan.get('preserve', []))}",
        "Apply this transactional update? [y/N] ",
    ]
    try:
        with open("/dev/tty", "r+", encoding="utf-8") as terminal:
            terminal.write("\n".join(lines))
            terminal.flush()
            answer = terminal.readline().strip()
    except OSError as error:
        raise LifecycleError("update confirmation requires a terminal or --yes") from error
    if answer not in {"y", "Y", "yes", "YES", "Yes"}:
        raise LifecycleError("update cancelled; no repository files were changed")


def _cleanup_report(
    *,
    metadata: dict[str, Any],
    target_manifest: dict[str, Any],
    transaction_id: str,
    preserved_legacy: list[str],
    conflicts: list[dict[str, str]],
    checksum_details: list[dict[str, Any]],
    file_links: list[str],
) -> dict[str, Any]:
    old_source = metadata.get("source", {})
    old_tag = old_source.get("tag") or f"v{metadata.get('harnessVersion')}"
    old_ref = old_source.get("commit") or old_tag
    target_tag = target_manifest["tag"]
    target_ref = target_manifest["sourceCommit"]
    paths = [item["path"] for item in conflicts]
    return {
        "projectName": metadata.get("projectName", "Project"),
        "fromVersion": metadata.get("harnessVersion"),
        "toVersion": target_manifest["harnessVersion"],
        "fromStateSchema": metadata.get("stateSchemaVersion", 0),
        "toStateSchema": target_manifest["stateSchemaVersion"],
        "transactionId": transaction_id,
        "preservedLegacyFiles": preserved_legacy,
        "conflicts": paths,
        "manualActions": [f"Merge project intent with the target form of {path}" for path in paths],
        "releaseUrl": f"https://github.com/{OFFICIAL_REPOSITORY}/releases/tag/{target_tag}",
        "compareUrl": f"https://github.com/{OFFICIAL_REPOSITORY}/compare/{old_ref}...{target_ref}",
        "fileLinks": file_links,
        "checksumDetails": checksum_details,
    }


def action_checksum_details(
    *,
    project_root: Path,
    prepared_root: Path,
    plan: dict[str, Any],
    metadata: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    managed = (metadata or {}).get("managedFiles", {})
    for kind in ("add", "replace", "retire", "conflicts"):
        for item in plan.get(kind, []):
            relative = item["path"]
            baseline = managed.get(relative, {}).get("baselineSha256")
            current = _entry_digest(_inside(project_root, relative))
            target = _entry_digest(_inside(prepared_root, relative))
            details.append(
                {
                    "path": relative,
                    "action": kind,
                    "ownership": item.get("ownership"),
                    "reason": item.get("reason"),
                    "baselineSha256": baseline,
                    "currentSha256": current,
                    "targetSha256": target,
                }
            )
    return details


def _validate_installed_project(project_root: Path) -> list[str]:
    commands: list[list[str]] = []
    if (project_root / "tools/harness_team.py").is_file():
        commands.append(
            [sys.executable, str(project_root / "tools/harness_team.py"), "check", "--json"]
        )
    if (project_root / "tools/harness_state.py").is_file():
        commands.append(
            [sys.executable, str(project_root / "tools/harness_state.py"), "check", "--json"]
        )
    if (project_root / "tools/harness_eval.py").is_file():
        commands.append(
            [sys.executable, str(project_root / "tools/harness_eval.py"), "--json"]
        )
    failures: list[str] = []
    for command in commands:
        process = subprocess.run(
            command, cwd=project_root, check=False, capture_output=True, text=True
        )
        if process.returncode:
            failures.append(process.stderr.strip() or process.stdout.strip())
    return failures


def finalize_adoption(
    *,
    project_root: Path,
    metadata: dict[str, Any],
    target_manifest: dict[str, Any],
    manifest_sha256: str,
    assume_yes: bool,
) -> dict[str, Any]:
    pending = metadata.get("pendingIntegration")
    if not isinstance(pending, list) or not pending:
        raise LifecycleError("Needs Integration metadata has no pending integration records")
    expected_manifest = metadata.get("source", {}).get("manifestSha256")
    if expected_manifest != manifest_sha256:
        raise LifecycleError(
            "the installed adoption baseline differs from the current stable bundle; update cannot finalize it safely"
        )

    root = project_root.resolve()
    baselines = dict(metadata.get("managedFiles", {}))
    missing: list[str] = []
    for record in pending:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise LifecycleError("pending integration metadata is invalid")
        relative = _safe_relative(record["path"])
        digest = _entry_digest(_inside(root, relative))
        if digest is None:
            missing.append(relative)
            continue
        baselines[relative] = {
            "ownership": "project-owned",
            "baselineSha256": digest,
        }
    if missing:
        raise LifecycleError(
            "integration cannot be finalized while preserved paths are missing: "
            + ", ".join(missing)
        )

    validation_failures = _validate_installed_project(root)
    if validation_failures:
        raise LifecycleError(
            "integration is not yet valid; finish the cleanup prompt before finalizing: "
            + "; ".join(validation_failures)
        )
    _confirm_plan(
        from_version=metadata["harnessVersion"],
        to_version=metadata["harnessVersion"],
        plan={
            "add": [],
            "replace": [{"path": METADATA_NAME}],
            "retire": [],
            "preserve": pending,
        },
        assume_yes=assume_yes,
    )

    transaction_id = f"integration-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    transaction = transaction_directory(root, transaction_id)
    with tempfile.TemporaryDirectory(prefix="aph-finalize-") as raw_prepared:
        prepared = Path(raw_prepared)
        next_metadata = build_metadata(
            project_name=metadata.get("projectName", "Project"),
            project_type=metadata.get("projectType", "other"),
            reasoning_preset=metadata.get("reasoningPreset", "custom"),
            reasoning=metadata["reasoning"],
            manifest=target_manifest,
            manifest_sha256=manifest_sha256,
            installation_status="Installed",
            managed_files=baselines,
            installed_at=metadata.get("installedAt"),
            applied_migrations=metadata.get("appliedMigrations", []),
            transaction_id=transaction_id,
            last_team_transaction_id=metadata.get("lastTeamTransactionId"),
            pending_integration=[],
        )
        _write_json_atomic(prepared / METADATA_NAME, next_metadata)
        plan = {
            "mode": "integration-finalize",
            "add": [],
            "replace": [
                _action(METADATA_NAME, "generated-config", "finalize validated adoption")
            ],
            "retire": [],
            "preserve": [
                _action(record["path"], "project-owned", "preserved adoption collision")
                for record in pending
            ],
            "conflicts": [],
            "atomicBlocked": False,
        }
        report = apply_file_plan(
            project_root=root,
            source_root=prepared,
            plan=plan,
            transaction_root=transaction,
        )
    report.update(
        {
            "transactionId": transaction_id,
            "installationStatus": "Installed",
            "projectOwnedPaths": [record["path"] for record in pending],
        }
    )
    try:
        _write_final_transaction_report(transaction / "update-report.json", report)
    except BaseException as error:
        rollback_applied_plan(
            project_root=root,
            plan=plan,
            transaction_root=transaction,
            reason=f"integration finalization failed: {error}",
        )
        raise LifecycleError(
            "integration finalization failed; repository metadata was rolled back"
        ) from error
    return {
        "ok": True,
        "mode": "integration-finalize",
        "project": str(root),
        "version": metadata["harnessVersion"],
        "installationStatus": "Installed",
        "transactionId": transaction_id,
        "conflicts": [],
        "cleanupPromptPath": None,
        "upToDate": True,
    }


@locked_lifecycle_mutation
def update_project(
    *,
    project_root: Path,
    source_root: Path,
    raw_manifest: dict[str, Any],
    manifest_sha256: str,
    assume_yes: bool,
) -> dict[str, Any]:
    root = project_root.resolve()
    target_manifest = validate_manifest(raw_manifest, source_root)
    if target_manifest["channel"] != "stable":
        raise LifecycleError("updates use official stable releases only")
    raw_metadata = _read_json(root / METADATA_NAME)
    with tempfile.TemporaryDirectory(prefix="aph-update-") as raw_scratch:
        scratch = Path(raw_scratch)
        current_version = raw_metadata.get("harnessVersion")
        target_version = target_manifest["harnessVersion"]
        current_tuple = _version_tuple(current_version)
        target_tuple = _version_tuple(target_version)
        if target_tuple < current_tuple:
            raise LifecycleError("automatic downgrade is not supported")
        origin_tag = f"v{current_version}"

        raw_schema_version = raw_metadata.get("schemaVersion")
        if type(raw_schema_version) is int and raw_schema_version == 1:
            origin = target_manifest["upgradeOrigins"].get(origin_tag)
            if not isinstance(origin, dict):
                raise LifecycleError(
                    f"stable {target_manifest['tag']} does not support upgrading from {origin_tag}"
                )
            metadata = reconstruct_legacy_metadata(
                metadata=raw_metadata,
                working_root=root,
                scratch_root=scratch,
                pinned_commit=origin["sourceCommit"],
            )
        elif type(raw_schema_version) is int and raw_schema_version == 2:
            metadata = raw_metadata
            source = metadata.get("source")
            if (
                metadata.get("provider") != "codex"
                or not isinstance(source, dict)
                or source.get("repository") != OFFICIAL_REPOSITORY
            ):
                raise LifecycleError(
                    "installed provenance is not an official harness source; no files were changed"
                )
            if (
                source.get("channel") != "stable"
                or source.get("tag") != origin_tag
            ):
                raise LifecycleError(
                    "installed provenance is not an official stable release; no files were changed"
                )
            if target_version == current_version:
                if (
                    source.get("commit") != target_manifest["sourceCommit"]
                    or source.get("manifestSha256") != manifest_sha256
                ):
                    raise LifecycleError(
                        "installed provenance does not match this immutable stable release; no files were changed"
                    )
                verify_installed_baselines(
                    project_root=root,
                    source_root=source_root,
                    source_manifest=target_manifest,
                    metadata=metadata,
                    scratch_root=scratch,
                )
            else:
                origin = target_manifest["upgradeOrigins"].get(origin_tag)
                if not isinstance(origin, dict):
                    raise LifecycleError(
                        f"stable {target_manifest['tag']} does not support upgrading from {origin_tag}"
                    )
                if (
                    origin.get("manifestSha256") is None
                    or source.get("commit") != origin.get("sourceCommit")
                    or source.get("manifestSha256") != origin.get("manifestSha256")
                ):
                    raise LifecycleError(
                        "installed metadata is not anchored to the immutable origin release; no files were changed"
                    )
                pinned_source = _pinned_stable_source(
                    origin_tag,
                    origin["sourceCommit"],
                    scratch / "pinned-installed-source",
                )
                pinned_manifest = manifest_for_local_source(pinned_source)
                verify_installed_baselines(
                    project_root=root,
                    source_root=pinned_source,
                    source_manifest=pinned_manifest,
                    metadata=metadata,
                    scratch_root=scratch,
                )
        else:
            raise LifecycleError("unsupported installed metadata schema")

        if metadata.get("installationStatus") == "Needs Integration":
            if target_version != current_version:
                raise LifecycleError(
                    "finish the existing adoption integration before upgrading to another release"
                )
            return finalize_adoption(
                project_root=root,
                metadata=metadata,
                target_manifest=target_manifest,
                manifest_sha256=manifest_sha256,
                assume_yes=assume_yes,
            )
        if target_version == current_version:
            return {
                "ok": True,
                "mode": "update",
                "project": str(root),
                "version": current_version,
                "installationStatus": metadata.get("installationStatus", "Installed"),
                "transactionId": metadata.get("lastTransactionId"),
                "conflicts": [],
                "cleanupPromptPath": None,
                "upToDate": True,
            }
        installed_state_schema = metadata.get("stateSchemaVersion", 0)
        target_state_schema = target_manifest["stateSchemaVersion"]
        if type(installed_state_schema) is not int or type(target_state_schema) is not int:
            raise LifecycleError("state schema versions must be integers")
        if installed_state_schema > target_state_schema:
            raise LifecycleError("target release has an older project-state schema")
        if installed_state_schema not in {target_state_schema, 0}:
            raise LifecycleError(
                f"no ordered migration is available from state schema {installed_state_schema} to {target_state_schema}"
            )

        prepared = scratch / "target"
        try:
            target_reasoning = normalized_reasoning(metadata["reasoning"])
        except TeamError as error:
            raise LifecycleError(f"installed reasoning cannot be migrated: {error}") from error
        metadata = dict(metadata)
        metadata["reasoning"] = target_reasoning
        preset_id = metadata.get("projectType", "software-product")
        target_catalog = load_catalog(source_root)
        if preset_id not in target_catalog["presets"]:
            preset_id = "software-product"
            metadata["projectType"] = preset_id
        _copy_template(source_root, prepared, target_manifest)
        staged_paths: list[str] = []
        if installed_state_schema == target_state_schema == 1:
            staged_paths = hydrate_current_state(
                project_root=root, prepared_root=prepared
            )
        prepared_team = prepared / TEAM_NAME
        if (root / TEAM_NAME).is_file() and prepared_team.is_file():
            configure_existing_team(
                project_root=prepared,
                team=_read_json(root / TEAM_NAME),
                reasoning=target_reasoning,
            )
        else:
            target_preset = preset_definition(target_catalog, preset_id)
            initialize_team(
                project_root=prepared,
                preset_id=preset_id,
                selected=target_preset["defaultConsultants"],
                reasoning=target_reasoning,
            )
        refresh_prepared_dashboard(prepared)
        remove_staged_state_evidence(
            prepared_root=prepared, staged_paths=staged_paths
        )
        prepared_manifest = manifest_for_prepared_source(prepared, target_manifest)
        plan = plan_files(
            mode="update",
            project_root=root,
            source_root=prepared,
            target_manifest=prepared_manifest,
            installed_metadata=metadata,
        )
        if (root / TEAM_NAME).is_file() and prepared_team.is_file():
            for action in ("add", "replace", "retire", "preserve", "conflicts"):
                plan[action] = [
                    item for item in plan[action] if item["path"] != TEAM_NAME
                ]
            if _entry_digest(root / TEAM_NAME) == _entry_digest(prepared_team):
                plan["preserve"].append(
                    _action(
                        TEAM_NAME,
                        "project-owned",
                        "team state and generated config baselines are target-identical",
                    )
                )
            else:
                plan["replace"].append(
                    _action(
                        TEAM_NAME,
                        "project-owned",
                        "atomically refresh generated team fields while preserving Consultant definitions and history",
                    )
                )
            plan["atomicBlocked"] = bool(plan["conflicts"])
        preserved_legacy: list[str] = []
        migrations = list(metadata.get("appliedMigrations", []))
        if not (root / TEAM_NAME).is_file() and not any(
            item.get("id") == "preset-team-v1"
            for item in migrations
            if isinstance(item, dict)
        ):
            migrations.append(
                {
                    "id": "preset-team-v1",
                    "appliedAt": utc_now(),
                    "preserved": [],
                }
            )
        if installed_state_schema == 0 and target_state_schema == 1:
            preserved_legacy = migrate_legacy_state(
                project_root=root, prepared_root=prepared, plan=plan
            )
            if not plan["atomicBlocked"]:
                migrations.append(
                    {
                        "id": "operational-state-v0-to-v1",
                        "appliedAt": utc_now(),
                        "preserved": preserved_legacy,
                    }
                )
            prepared_manifest = manifest_for_prepared_source(prepared, target_manifest)

        transaction_id = f"update-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        transaction = transaction_directory(root, transaction_id)
        checksum_details = action_checksum_details(
            project_root=root,
            prepared_root=prepared,
            plan=plan,
            metadata=metadata,
        )
        file_links = [
            f"https://github.com/{OFFICIAL_REPOSITORY}/blob/{target_manifest['sourceCommit']}/{item['path']}"
            for item in plan["conflicts"]
        ]
        cleanup = _cleanup_report(
            metadata=metadata,
            target_manifest=target_manifest,
            transaction_id=transaction_id,
            preserved_legacy=preserved_legacy,
            conflicts=plan["conflicts"],
            checksum_details=checksum_details,
            file_links=file_links,
        )
        if plan["atomicBlocked"]:
            blocked = record_blocked_plan(
                project_root=root,
                source_root=prepared,
                plan=plan,
                transaction_root=transaction,
                cleanup_report=cleanup,
                target_ref=target_manifest["sourceCommit"],
            )
            raise LifecycleError(
                f"update blocked by {len(plan['conflicts'])} preserved conflict(s); cleanup prompt: {blocked['cleanupPromptPath']}"
            )

        _confirm_plan(
            from_version=current_version,
            to_version=target_version,
            plan=plan,
            assume_yes=assume_yes,
        )
        managed = {
            relative: {
                "ownership": record["ownership"],
                "baselineSha256": record["sha256"],
            }
            for relative, record in prepared_manifest["files"].items()
            if record["ownership"] != "project-owned"
        }
        managed.update(
            {
                relative: dict(record)
                for relative, record in metadata.get("managedFiles", {}).items()
                if isinstance(record, dict)
                and record.get("ownership") == "project-owned"
            }
        )
        next_metadata = build_metadata(
            project_name=metadata.get("projectName", "Project"),
            project_type=metadata.get("projectType", "other"),
            reasoning_preset=metadata.get("reasoningPreset", "custom"),
            reasoning=metadata["reasoning"],
            manifest=target_manifest,
            manifest_sha256=manifest_sha256,
            installation_status="Installed",
            managed_files=managed,
            installed_at=metadata.get("installedAt"),
            applied_migrations=migrations,
            transaction_id=transaction_id,
            last_team_transaction_id=metadata.get("lastTeamTransactionId"),
        )
        _write_json_atomic(prepared / METADATA_NAME, next_metadata)
        plan["replace"].append(
            _action(METADATA_NAME, "generated-config", "advance installed lifecycle metadata")
        )
        report = apply_file_plan(
            project_root=root,
            source_root=prepared,
            plan=plan,
            transaction_root=transaction,
        )
        try:
            failures = _validate_installed_project(root)
            if failures:
                raise LifecycleError(
                    "target validation failed: " + "; ".join(failures)
                )

            cleanup["reportPath"] = str(transaction / "update-report.json")
            cleanup["backupPath"] = str(transaction / "backup")
            report["checksumDetails"] = checksum_details
            prompt = build_cleanup_prompt(cleanup)
            (transaction / "cleanup-prompt.txt").write_text(prompt, encoding="utf-8")
            report.update(
                {
                    "transactionId": transaction_id,
                    "installationStatus": "Installed",
                    "cleanupPromptPath": str(transaction / "cleanup-prompt.txt"),
                    "preservedLegacyFiles": preserved_legacy,
                }
            )
            _write_final_transaction_report(transaction / "update-report.json", report)
        except BaseException as error:
            rollback_applied_plan(
                project_root=root,
                plan=plan,
                transaction_root=transaction,
                reason=f"update finalization failed: {error}",
            )
            if isinstance(error, LifecycleError):
                raise LifecycleError(
                    f"{error}; the update was rolled back"
                ) from error
            raise LifecycleError(
                "update finalization failed; the update was rolled back"
            ) from error
        return {
            "ok": True,
            "mode": "update",
            "project": str(root),
            "version": target_version,
            "installationStatus": "Installed",
            "transactionId": transaction_id,
            "conflicts": [],
            "cleanupPromptPath": str(transaction / "cleanup-prompt.txt"),
            "preservedLegacyFiles": preserved_legacy,
            "upToDate": False,
        }


def build_metadata(
    *,
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    manifest: dict[str, Any],
    manifest_sha256: str,
    installation_status: str,
    managed_files: dict[str, dict[str, str]],
    installed_at: str | None = None,
    applied_migrations: list[dict[str, Any]] | None = None,
    transaction_id: str | None = None,
    last_team_transaction_id: str | None = None,
    pending_integration: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    manifest = validate_manifest(manifest)
    if installation_status not in {"Installed", "Needs Integration", "Migration Blocked"}:
        raise LifecycleError(f"invalid installation status: {installation_status}")
    if not _is_hex(manifest_sha256, 64):
        raise LifecycleError("manifest checksum must be a sha256")
    try:
        reasoning = normalized_reasoning(reasoning)
    except TeamError as error:
        raise LifecycleError(
            "reasoning metadata must define every common harness role"
        ) from error
    normalized_files: dict[str, dict[str, str]] = {}
    for raw_path, record in sorted(managed_files.items()):
        path = _safe_relative(raw_path)
        ownership = record.get("ownership")
        baseline = record.get("baselineSha256")
        if ownership not in SUPPORTED_OWNERSHIP:
            raise LifecycleError(f"metadata cannot manage ownership {ownership!r}: {path}")
        if not _is_hex(baseline, 64):
            raise LifecycleError(f"invalid baseline checksum: {path}")
        normalized_files[path] = {
            "ownership": ownership,
            "baselineSha256": baseline,
        }

    normalized_pending: list[dict[str, str]] = []
    pending_paths: set[str] = set()
    for record in pending_integration or []:
        if not isinstance(record, dict):
            raise LifecycleError("pending integration record must be an object")
        path = _safe_relative(record.get("path"))
        if path in pending_paths:
            raise LifecycleError(f"duplicate pending integration path: {path}")
        pending_paths.add(path)
        target_digest = record.get("targetSha256")
        target_ownership = record.get("targetOwnership")
        if not _is_hex(target_digest, 64) or target_ownership not in SUPPORTED_OWNERSHIP:
            raise LifecycleError(f"invalid pending integration record: {path}")
        normalized_pending.append(
            {
                "path": path,
                "targetSha256": target_digest,
                "targetOwnership": target_ownership,
            }
        )

    now = utc_now()
    return {
        "schemaVersion": 2,
        "harnessVersion": manifest["harnessVersion"],
        "stateSchemaVersion": manifest["stateSchemaVersion"],
        "provider": "codex",
        "installationStatus": installation_status,
        "projectName": project_name,
        "projectType": project_type,
        "reasoningPreset": reasoning_preset,
        "reasoning": dict(sorted(reasoning.items())),
        "source": {
            "repository": "FabienGreard/agentic-project-harness",
            "channel": manifest["channel"],
            "tag": manifest["tag"],
            "commit": manifest["sourceCommit"],
            "manifestSha256": manifest_sha256,
        },
        "installedAt": installed_at or now,
        "updatedAt": now,
        "lastTransactionId": transaction_id,
        "lastTeamTransactionId": last_team_transaction_id,
        "managedFiles": normalized_files,
        "appliedMigrations": applied_migrations or [],
        "pendingIntegration": normalized_pending,
    }


def inspect_status(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    metadata = _read_json(root / METADATA_NAME)
    schema = metadata.get("schemaVersion")
    if type(schema) is int and schema == 1:
        return {
            "installedVersion": metadata.get("harnessVersion"),
            "stateSchemaVersion": 0,
            "installationStatus": "Legacy",
            "source": {
                "repository": metadata.get("source"),
                "tag": metadata.get("ref"),
                "mode": metadata.get("sourceMode"),
            },
            "integrity": {"modified": [], "missing": [], "unverifiable": True},
            "lastTransactionId": None,
            "team": None,
        }
    if type(schema) is not int or schema != 2:
        raise LifecycleError(f"unsupported metadata schema: {schema!r}")
    state_schema = metadata.get("stateSchemaVersion")
    if type(state_schema) is not int:
        raise LifecycleError(
            f"unsupported state schema version: {state_schema!r}"
        )

    managed_files = metadata.get("managedFiles")
    pending_integration = metadata.get("pendingIntegration")
    if not isinstance(managed_files, dict) or not isinstance(pending_integration, list):
        raise LifecycleError("installed metadata has invalid lifecycle records")
    modified: list[str] = []
    missing: list[str] = []
    project_modified: list[str] = []
    project_missing: list[str] = []
    for raw_path, record in sorted(managed_files.items()):
        if not isinstance(record, dict):
            raise LifecycleError(f"installed metadata has an invalid baseline: {raw_path}")
        path = _inside(root, raw_path)
        if path.is_symlink():
            actual = sha256_bytes(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            actual = sha256_file(path)
        else:
            if record.get("ownership") == "project-owned":
                project_missing.append(raw_path)
            else:
                missing.append(raw_path)
            continue
        if actual != record.get("baselineSha256"):
            if record.get("ownership") == "project-owned":
                project_modified.append(raw_path)
            else:
                modified.append(raw_path)
    team_summary = None
    team_path = root / TEAM_NAME
    if team_path.is_file():
        team = _read_json(team_path)
        team_summary = {
            "preset": team.get("preset"),
            "presetLabel": team.get("presetLabel"),
            "management": team.get("management", {}).get("title"),
            "operations": team.get("operations", {}).get("title"),
            "activeConsultants": [
                item.get("title")
                for item in team.get("consultants", [])
                if isinstance(item, dict) and item.get("status") == "active"
            ],
        }
    return {
        "installedVersion": metadata.get("harnessVersion"),
        "stateSchemaVersion": metadata.get("stateSchemaVersion"),
        "installationStatus": metadata.get("installationStatus"),
        "source": metadata.get("source"),
        "integrity": {
            "modified": modified,
            "missing": missing,
            "projectOwnedChanged": project_modified,
            "projectOwnedMissing": project_missing,
            "unverifiable": False,
        },
        "lastTransactionId": metadata.get("lastTransactionId"),
        "lastTeamTransactionId": metadata.get("lastTeamTransactionId"),
        "team": team_summary,
        "pendingIntegration": pending_integration,
    }


def _entry_digest(path: Path) -> str | None:
    if path.is_symlink():
        return sha256_bytes(os.readlink(path).encode("utf-8"))
    if path.is_file():
        return sha256_file(path)
    return None


def _action(path: str, ownership: str, reason: str) -> dict[str, str]:
    return {"path": path, "ownership": ownership, "reason": reason}


def plan_files(
    *,
    mode: str,
    project_root: Path,
    source_root: Path,
    target_manifest: dict[str, Any],
    installed_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    if mode not in {"install", "adoption", "update"}:
        raise LifecycleError(f"unsupported lifecycle mode: {mode}")
    target_manifest = validate_manifest(target_manifest, source_root)
    root = project_root.resolve()
    managed = (installed_metadata or {}).get("managedFiles", {})
    if mode == "update" and not isinstance(managed, dict):
        raise LifecycleError("installed metadata has no managed-file baseline")

    plan: dict[str, Any] = {
        "mode": mode,
        "add": [],
        "replace": [],
        "retire": [],
        "preserve": [],
        "conflicts": [],
        "atomicBlocked": False,
    }

    target_files: dict[str, dict[str, str]] = target_manifest["files"]
    for raw_path, target_record in sorted(target_files.items()):
        path = _safe_relative(raw_path)
        ownership = target_record["ownership"]
        current = _inside(root, path)
        current_digest = _entry_digest(current)

        if mode in {"install", "adoption"}:
            if current_digest is None and not current.exists():
                plan["add"].append(_action(path, ownership, "path is available"))
            elif current_digest == target_record["sha256"]:
                plan["preserve"].append(
                    _action(path, ownership, "existing path is target-identical")
                )
            else:
                plan["conflicts"].append(
                    _action(path, ownership, "existing project path is preserved")
                )
            continue

        baseline_record = managed.get(path)
        if ownership == "project-owned":
            if current_digest is None and not current.exists():
                plan["add"].append(
                    _action(path, ownership, "new project-owned path is available")
                )
            else:
                plan["preserve"].append(
                    _action(path, ownership, "project-owned records migrate separately")
                )
            continue

        if isinstance(baseline_record, dict) and baseline_record.get("ownership") == "project-owned":
            plan["preserve"].append(
                _action(path, "project-owned", "adopted project-owned path is never updated automatically")
            )
            continue

        if baseline_record is None:
            if current_digest is None and not current.exists():
                plan["add"].append(_action(path, ownership, "new managed path"))
            else:
                plan["conflicts"].append(
                    _action(path, ownership, "new managed path collides with project content")
                )
            continue

        baseline = baseline_record.get("baselineSha256")
        if current_digest is None:
            plan["conflicts"].append(
                _action(path, ownership, "installed managed path is missing or unsupported")
            )
        elif current_digest != baseline:
            plan["conflicts"].append(
                _action(path, ownership, "managed path differs from its installed baseline")
            )
        elif target_record["sha256"] == baseline:
            plan["preserve"].append(
                _action(path, ownership, "managed path is already target-identical")
            )
        else:
            plan["replace"].append(
                _action(path, ownership, "unchanged managed path has a new stable baseline")
            )

    if mode == "update":
        for raw_path, baseline_record in sorted(managed.items()):
            path = _safe_relative(raw_path)
            if path in target_files:
                continue
            current = _inside(root, path)
            current_digest = _entry_digest(current)
            ownership = baseline_record.get("ownership", "harness-managed")
            if ownership == "project-owned":
                plan["preserve"].append(
                    _action(
                        path,
                        ownership,
                        "project-owned path is never retired automatically",
                    )
                )
                continue
            if current_digest is None and not current.exists():
                continue
            if current_digest == baseline_record.get("baselineSha256"):
                plan["retire"].append(
                    _action(path, ownership, "untouched managed path retired upstream")
                )
            else:
                plan["conflicts"].append(
                    _action(path, ownership, "retired managed path was modified locally")
                )
        plan["atomicBlocked"] = bool(plan["conflicts"])
    return plan


def transaction_directory(project_root: Path, transaction_id: str) -> Path:
    if not transaction_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in transaction_id):
        raise LifecycleError("transaction ID contains unsupported characters")
    root = project_root.resolve()
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))
    ).expanduser()
    project_id = sha256_bytes(str(root).encode("utf-8"))[:16]
    transaction = (
        state_home
        / "agentic-project-harness"
        / project_id
        / "updates"
        / transaction_id
    ).resolve()
    if transaction == root or root in transaction.parents:
        raise LifecycleError("transaction data must be outside the working tree")
    return transaction


def _remove_entry(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_entry(source_root: Path, relative: str, destination_root: Path) -> None:
    source = _inside(source_root, relative)
    destination = _inside(destination_root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _remove_entry(destination)
    if source.is_symlink():
        _validate_source_symlink(source_root, source)
        destination.symlink_to(os.readlink(source))
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise LifecycleError(f"source entry cannot be copied: {relative}")


def _backup_entry(project_root: Path, relative: str, backup_root: Path) -> bool:
    source = _inside(project_root, relative)
    if not source.exists() and not source.is_symlink():
        return False
    destination = _inside(backup_root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_file():
        shutil.copy2(source, destination)
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    return True


def _missing_parent_directories(root: Path, destination: Path) -> list[Path]:
    missing: list[Path] = []
    current = destination.parent
    while current != root:
        if not current.exists() and not current.is_symlink():
            missing.append(current)
        current = current.parent
    return missing


def _prune_created_directories(paths: Iterable[Path]) -> None:
    for path in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
        try:
            path.rmdir()
        except (FileNotFoundError, OSError):
            pass


def _restore_touched_entries(
    *,
    root: Path,
    backup: Path,
    touched: list[tuple[str, bool]],
    created_directories: Iterable[Path],
) -> list[str]:
    failures: list[str] = []
    for relative, existed in reversed(touched):
        destination = _inside(root, relative)
        try:
            _remove_entry(destination)
            if existed:
                _copy_entry(backup, relative, root)
        except (LifecycleError, OSError) as error:
            failures.append(f"{relative}: {error}")
    _prune_created_directories(created_directories)
    return failures


def apply_file_plan(
    *,
    project_root: Path,
    source_root: Path,
    plan: dict[str, Any],
    transaction_root: Path,
) -> dict[str, Any]:
    if plan.get("atomicBlocked"):
        raise LifecycleError("file plan has unresolved conflicts")
    root = project_root.resolve()
    source = source_root.resolve()
    transaction = transaction_root.resolve()
    if transaction == root or root in transaction.parents:
        raise LifecycleError("transaction data must be outside the working tree")
    backup = transaction / "backup"
    proposed = transaction / "proposed"
    try:
        backup.mkdir(parents=True, exist_ok=True)
        proposed.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise LifecycleError(f"cannot create external transaction storage: {error}") from error

    touched: list[tuple[str, bool]] = []
    created_directories: set[Path] = set()
    writes = 0
    fail_after_raw = os.environ.get("APH_TEST_FAIL_AFTER_WRITES")
    fail_after = int(fail_after_raw) if fail_after_raw else None
    actions: list[tuple[str, dict[str, str]]] = []
    actions.extend(("add", item) for item in plan.get("add", []))
    actions.extend(("replace", item) for item in plan.get("replace", []))
    actions.extend(("retire", item) for item in plan.get("retire", []))

    try:
        for kind, item in actions:
            relative = _safe_relative(item["path"])
            existed = _backup_entry(root, relative, backup)
            touched.append((relative, existed))
            if kind == "retire":
                _remove_entry(_inside(root, relative))
            else:
                created_directories.update(
                    _missing_parent_directories(root, _inside(root, relative))
                )
                _copy_entry(source, relative, proposed)
                _copy_entry(source, relative, root)
            writes += 1
            if fail_after is not None and writes >= fail_after:
                raise LifecycleError("injected lifecycle failure")
    except BaseException as error:
        restore_failures = _restore_touched_entries(
            root=root,
            backup=backup,
            touched=touched,
            created_directories=created_directories,
        )
        report = {
            "result": "rolled-back",
            "mode": plan.get("mode"),
            "error": str(error),
            "backupPath": str(backup),
            "actions": [item for _, item in actions],
            "createdDirectories": [
                str(path.relative_to(root)) for path in sorted(created_directories)
            ],
            "restoreFailures": restore_failures,
        }
        try:
            _write_json_atomic(transaction / "update-report.json", report)
        except OSError:
            pass
        if restore_failures:
            raise LifecycleError(
                "lifecycle transaction failed and rollback was incomplete: "
                + "; ".join(restore_failures)
            ) from error
        if isinstance(error, LifecycleError):
            raise
        raise LifecycleError(f"lifecycle transaction rolled back: {error}") from error

    report = {
        "result": "applied",
        "mode": plan.get("mode"),
        "backupPath": str(backup),
        "proposedPath": str(proposed),
        "actions": [item for _, item in actions],
        "preserved": plan.get("preserve", []),
        "conflicts": plan.get("conflicts", []),
        "createdDirectories": [
            str(path.relative_to(root)) for path in sorted(created_directories)
        ],
    }
    try:
        _write_json_atomic(transaction / "update-report.json", report)
    except OSError as error:
        restore_failures = _restore_touched_entries(
            root=root,
            backup=backup,
            touched=touched,
            created_directories=created_directories,
        )
        if restore_failures:
            raise LifecycleError(
                "transaction reporting failed and rollback was incomplete: "
                + "; ".join(restore_failures)
            ) from error
        raise LifecycleError(
            "transaction reporting failed; repository writes were rolled back"
        ) from error
    return report


def rollback_applied_plan(
    *, project_root: Path, plan: dict[str, Any], transaction_root: Path, reason: str
) -> None:
    root = project_root.resolve()
    transaction = transaction_root.resolve()
    backup = transaction / "backup"
    actions = [
        *plan.get("add", []),
        *plan.get("replace", []),
        *plan.get("retire", []),
    ]
    failures: list[str] = []
    created_directories: list[Path] = []
    report_path = transaction / "update-report.json"
    if report_path.is_file():
        try:
            previous_report = _read_json(report_path)
        except LifecycleError:
            previous_report = {}
        for relative in previous_report.get("createdDirectories", []):
            if isinstance(relative, str):
                created_directories.append(_inside(root, relative))
    for item in reversed(actions):
        relative = _safe_relative(item["path"])
        destination = _inside(root, relative)
        _remove_entry(destination)
        saved = _inside(backup, relative)
        if saved.exists() or saved.is_symlink():
            try:
                _copy_entry(backup, relative, root)
            except LifecycleError as error:
                failures.append(str(error))
    _prune_created_directories(created_directories)
    report = {
        "result": "rolled-back",
        "reason": reason,
        "restoreFailures": failures,
        "backupPath": str(backup),
        "actions": actions,
        "createdDirectories": [
            str(path.relative_to(root)) for path in created_directories
        ],
    }
    _write_json_atomic(transaction / "update-report.json", report)
    if failures:
        raise LifecycleError(
            "update validation failed and rollback was incomplete: " + "; ".join(failures)
        )


def record_blocked_plan(
    *,
    project_root: Path,
    source_root: Path,
    plan: dict[str, Any],
    transaction_root: Path,
    cleanup_report: dict[str, Any],
    target_ref: str,
) -> dict[str, Any]:
    transaction = transaction_root.resolve()
    transaction.mkdir(parents=True, exist_ok=True)
    _copy_conflict_evidence(
        source_root, plan.get("conflicts", []), transaction, target_ref
    )
    report = {
        "result": "blocked",
        "mode": plan.get("mode"),
        "project": str(project_root.resolve()),
        "conflicts": plan.get("conflicts", []),
        "add": plan.get("add", []),
        "replace": plan.get("replace", []),
        "retire": plan.get("retire", []),
        "preserve": plan.get("preserve", []),
        "backupPath": str(transaction / "backup"),
        "checksumDetails": cleanup_report.get("checksumDetails", []),
    }
    _write_json_atomic(transaction / "update-report.json", report)
    cleanup_report = dict(cleanup_report)
    cleanup_report["reportPath"] = str(transaction / "update-report.json")
    cleanup_report["backupPath"] = str(transaction / "backup")
    prompt = build_cleanup_prompt(cleanup_report)
    (transaction / "cleanup-prompt.txt").write_text(prompt, encoding="utf-8")
    report["cleanupPromptPath"] = str(transaction / "cleanup-prompt.txt")
    _write_json_atomic(transaction / "update-report.json", report)
    return report


def _bullet_list(values: Iterable[str], fallback: str = "None") -> str:
    rendered = [f"- {value}" for value in values]
    return "\n".join(rendered) if rendered else f"- {fallback}"


def build_cleanup_prompt(report: dict[str, Any]) -> str:
    file_links = report.get("fileLinks", [])
    checksum_lines = [
        f"{item.get('path')}: action={item.get('action')}; "
        f"baseline={item.get('baselineSha256') or 'absent'}; "
        f"current={item.get('currentSha256') or 'absent'}; "
        f"target={item.get('targetSha256') or 'absent'}"
        for item in report.get("checksumDetails", [])
    ]
    return f"""Complete the Agentic Project Harness update cleanup for {report.get('projectName', 'this project')}.

Update:
- Harness: {report.get('fromVersion', 'unknown')} -> {report.get('toVersion', 'unknown')}
- State schema: {report.get('fromStateSchema', 'unknown')} -> {report.get('toStateSchema', 'unknown')}
- Transaction: {report.get('transactionId', 'unknown')}
- Update report: {report.get('reportPath', 'unknown')}
- Rollback backup: {report.get('backupPath', 'unknown')}
- Stable release: {report.get('releaseUrl', 'unknown')}
- Stable comparison: {report.get('compareUrl', 'unknown')}

Official target files:
{_bullet_list(file_links)}

Exact baseline/current/target checksums:
{_bullet_list(checksum_lines)}

Preserved legacy files:
{_bullet_list(report.get('preservedLegacyFiles', []))}

Conflicts:
{_bullet_list(report.get('conflicts', []))}

Manual actions:
{_bullet_list(report.get('manualActions', []))}

First read AGENTS.md and its applicable rules. Treat the update report, local baseline/current/target snapshots, checksums, and immutable GitHub links as the exact cleanup boundary. Preserve unrelated work and do not commit, push, publish, or replace a user-modified file wholesale.

Confirm that every meaningful project fact reached the canonical JSON records, resolve only the listed conflicts, validate the JSON schemas, regenerate the HTML project view, run ./install.sh status and the harness evaluator, and report exact results and remaining manual work.

Do not delete legacy files or the rollback backup yourself. After every check passes, present exact archival or deletion candidates and request explicit human approval.
"""


def _manifest_sha256(manifest: dict[str, Any]) -> str:
    encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return sha256_bytes(encoded)


def _managed_baselines(
    prepared_root: Path,
    prepared_manifest: dict[str, Any],
    installed_paths: set[str],
) -> dict[str, dict[str, str]]:
    managed: dict[str, dict[str, str]] = {}
    for relative, record in sorted(prepared_manifest["files"].items()):
        if relative not in installed_paths or record["ownership"] == "project-owned":
            continue
        actual = _entry_digest(_inside(prepared_root, relative))
        if actual is None:
            raise LifecycleError(f"installed managed path has no baseline: {relative}")
        managed[relative] = {
            "ownership": record["ownership"],
            "baselineSha256": actual,
        }
    return managed


def _copy_conflict_evidence(
    prepared_root: Path,
    conflicts: list[dict[str, str]],
    transaction_root: Path,
    target_ref: str,
) -> list[str]:
    links: list[str] = []
    target = transaction_root / "target-conflicts"
    for item in conflicts:
        relative = item["path"]
        source = _inside(prepared_root, relative)
        if source.exists() or source.is_symlink():
            _copy_entry(prepared_root, relative, target)
        if _is_hex(target_ref, 40):
            links.append(
                f"https://github.com/{OFFICIAL_REPOSITORY}/blob/{target_ref}/{relative}"
            )
    return links


def _is_effectively_empty(root: Path) -> bool:
    try:
        return next(root.iterdir(), None) is None
    except OSError as error:
        raise LifecycleError(f"target cannot be safely inspected: {root}: {error}") from error


def _validate_target(root: Path) -> None:
    if ".." in root.parts:
        raise LifecycleError("target path must not contain a '..' segment")
    absolute = root.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise LifecycleError(f"target path must not be or pass through a symbolic link: {root}")
    if root.exists() and not root.is_dir():
        raise LifecycleError(f"target exists and is not a directory: {root}")


@locked_lifecycle_mutation
def install_or_adopt(
    *,
    project_root: Path,
    source_root: Path,
    manifest: dict[str, Any],
    manifest_sha256: str,
    project_name: str,
    project_type: str,
    reasoning_preset: str,
    reasoning: dict[str, str],
    selected_consultants: list[str],
) -> dict[str, Any]:
    root = project_root.absolute()
    _validate_target(root)
    if (root / METADATA_NAME).exists():
        raise LifecycleError("target already contains harness metadata; use update")
    root.mkdir(parents=True, exist_ok=True)
    was_empty = _is_effectively_empty(root)
    mode = "install" if was_empty else "adoption"
    created_git = False
    if was_empty:
        try:
            subprocess.run(
                ["git", "-C", str(root), "init", "-q", "-b", "main"],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise LifecycleError("git is required for a fresh empty-folder installation")
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(root), "symbolic-ref", "HEAD", "refs/heads/main"],
                    check=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError) as error:
                shutil.rmtree(root / ".git", ignore_errors=True)
                raise LifecycleError("git initialization failed; no harness files were installed") from error
        created_git = True

    plan: dict[str, Any] | None = None
    transaction: Path | None = None
    applied = False
    try:
        with tempfile.TemporaryDirectory(prefix="aph-prepared-") as raw_prepared:
            prepared_root = Path(raw_prepared) / "project"
            prepared_manifest = prepare_project_source(
                source_root=source_root,
                manifest=manifest,
                project_name=project_name,
                project_type=project_type,
                reasoning_preset=reasoning_preset,
                reasoning=reasoning,
                selected_consultants=selected_consultants,
                destination=prepared_root,
            )
            plan = plan_files(
                mode=mode,
                project_root=root,
                source_root=prepared_root,
                target_manifest=prepared_manifest,
                installed_metadata=None,
            )
            transaction_id = f"{mode}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
            transaction = transaction_directory(root, transaction_id)
            file_links = _copy_conflict_evidence(
                prepared_root,
                plan["conflicts"],
                transaction,
                manifest["sourceCommit"]
                if manifest["channel"] == "stable"
                else manifest["tag"],
            )
            checksum_details = action_checksum_details(
                project_root=root,
                prepared_root=prepared_root,
                plan=plan,
                metadata=None,
            )
            installed_paths = {
                item["path"] for item in (*plan["add"], *plan["replace"])
            }
            installed_paths.update(
                item["path"]
                for item in plan["preserve"]
                if item["reason"] == "existing path is target-identical"
            )
            status = "Installed" if not plan["conflicts"] else "Needs Integration"
            metadata = build_metadata(
                project_name=project_name,
                project_type=project_type,
                reasoning_preset=reasoning_preset,
                reasoning=reasoning,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                installation_status=status,
                managed_files=_managed_baselines(
                    prepared_root, prepared_manifest, installed_paths
                ),
                transaction_id=transaction_id,
                pending_integration=[
                    {
                        "path": item["path"],
                        "targetSha256": prepared_manifest["files"][item["path"]]["sha256"],
                        "targetOwnership": prepared_manifest["files"][item["path"]]["ownership"],
                    }
                    for item in plan["conflicts"]
                ],
            )
            _write_json_atomic(prepared_root / METADATA_NAME, metadata)
            plan["add"].append(
                _action(METADATA_NAME, "generated-config", "record installed lifecycle metadata")
            )
            report = apply_file_plan(
                project_root=root,
                source_root=prepared_root,
                plan=plan,
                transaction_root=transaction,
            )
            applied = True
            cleanup_report = {
                "projectName": project_name,
                "fromVersion": "none",
                "toVersion": manifest["harnessVersion"],
                "fromStateSchema": 0,
                "toStateSchema": manifest["stateSchemaVersion"],
                "transactionId": transaction_id,
                "reportPath": str(transaction / "update-report.json"),
                "backupPath": str(transaction / "backup"),
                "preservedLegacyFiles": [item["path"] for item in plan["preserve"]],
                "conflicts": [item["path"] for item in plan["conflicts"]],
                "manualActions": [
                    f"Merge project intent with the target form of {item['path']}"
                    for item in plan["conflicts"]
                ],
                "releaseUrl": f"https://github.com/{OFFICIAL_REPOSITORY}/releases/tag/{manifest['tag']}",
                "compareUrl": "Not applicable to a first installation",
                "fileLinks": file_links,
                "checksumDetails": checksum_details,
            }
            prompt = build_cleanup_prompt(cleanup_report)
            (transaction / "cleanup-prompt.txt").write_text(prompt, encoding="utf-8")
            report.update(
                {
                    "transactionId": transaction_id,
                    "installationStatus": status,
                    "metadataPath": str(root / METADATA_NAME),
                    "cleanupPromptPath": str(transaction / "cleanup-prompt.txt"),
                    "checksumDetails": checksum_details,
                }
            )
            _write_final_transaction_report(transaction / "update-report.json", report)
    except BaseException as error:
        if applied and plan is not None and transaction is not None:
            rollback_applied_plan(
                project_root=root,
                plan=plan,
                transaction_root=transaction,
                reason="installation finalization failed",
            )
        if created_git:
            shutil.rmtree(root / ".git", ignore_errors=True)
        if was_empty:
            for created_entry in root.iterdir():
                _remove_entry(created_entry)
        if isinstance(error, LifecycleError):
            raise
        raise LifecycleError(
            f"installation failed and was rolled back: {error}"
        ) from error

    return {
        "ok": True,
        "mode": mode,
        "project": str(root),
        "version": manifest["harnessVersion"],
        "installationStatus": status,
        "transactionId": transaction_id,
        "conflicts": [item["path"] for item in plan["conflicts"]],
        "cleanupPromptPath": str(transaction / "cleanup-prompt.txt"),
    }


def _emit_status(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    integrity = payload["integrity"]
    print("\nAgentic Project Harness status")
    print(f"  Installed version: {payload.get('installedVersion')}")
    print(f"  State schema: {payload.get('stateSchemaVersion')}")
    print(f"  Installation: {payload.get('installationStatus')}")
    print(f"  Modified managed files: {len(integrity.get('modified', []))}")
    print(f"  Missing managed files: {len(integrity.get('missing', []))}")
    print(f"  Changed project-owned files: {len(integrity.get('projectOwnedChanged', []))}")
    print(f"  Missing project-owned files: {len(integrity.get('projectOwnedMissing', []))}")
    print(f"  Pending integration paths: {len(payload.get('pendingIntegration', []))}")
    if payload.get("lastTransactionId"):
        print(f"  Last transaction: {payload['lastTransactionId']}")


def _emit_result(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print("\nAgentic Project Harness")
    print(f"  Mode: {payload['mode']}")
    print(f"  Project: {payload['project']}")
    print(f"  Version: {payload['version']}")
    print(f"  Status: {payload['installationStatus']}")
    if payload.get("upToDate"):
        if payload["mode"] == "integration-finalize":
            print("  Result: adoption integration finalized; preserved collisions are project-owned")
        else:
            print("  Result: already on the latest stable release")
        return
    if payload["conflicts"]:
        print("  Preserved conflicts:")
        for path in payload["conflicts"]:
            print(f"    - {path}")
        print(f"  Copy-ready cleanup prompt: {payload['cleanupPromptPath']}")
    elif payload["mode"] == "update":
        print(f"  Transaction: {payload['transactionId']}")
        if payload.get("preservedLegacyFiles"):
            print(f"  Preserved legacy files: {len(payload['preservedLegacyFiles'])}")
        print(f"  Cleanup prompt: {payload['cleanupPromptPath']}")
    else:
        print("  First project prompt: README.md")


def internal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal install.sh lifecycle engine")
    parser.add_argument("command", choices=("smart", "status", "update"))
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--project-name")
    parser.add_argument("--project-type", default="software-product")
    parser.add_argument("--reasoning-preset", default="medium")
    parser.add_argument("--reasoning-json")
    parser.add_argument("--consultants-json", default="[]")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = internal_parser().parse_args()
    try:
        if args.command == "status":
            _emit_status(inspect_status(args.project_root), args.json)
            return 0
        if args.source_root is None:
            raise LifecycleError("install/update source is missing")
        if args.manifest:
            raw_manifest = _read_json(args.manifest)
            manifest_sha256 = args.manifest_sha256 or sha256_file(args.manifest)
        else:
            raw_manifest = manifest_for_local_source(args.source_root)
            manifest_sha256 = _manifest_sha256(raw_manifest)
        manifest = validate_manifest(raw_manifest, args.source_root)
        metadata_path = args.project_root / METADATA_NAME
        if metadata_path.exists():
            if args.command == "smart":
                raise LifecycleError(
                    "an existing harness was detected at the selected destination; run its ./install.sh update command"
                )
            result = update_project(
                project_root=args.project_root,
                source_root=args.source_root,
                raw_manifest=raw_manifest,
                manifest_sha256=manifest_sha256,
                assume_yes=args.yes,
            )
            _emit_result(result, args.json)
            return 0
        if args.command == "update":
            raise LifecycleError("no installed harness metadata was found")
        if not args.project_name or not args.reasoning_json:
            raise LifecycleError("installation configuration is incomplete")
        reasoning = json.loads(args.reasoning_json)
        if not isinstance(reasoning, dict):
            raise LifecycleError("reasoning configuration must be an object")
        selected_consultants = json.loads(args.consultants_json)
        if not isinstance(selected_consultants, list) or not all(
            isinstance(item, str) for item in selected_consultants
        ):
            raise LifecycleError("Consultant selection must be a JSON string array")
        result = install_or_adopt(
            project_root=args.project_root,
            source_root=args.source_root,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            project_name=args.project_name,
            project_type=args.project_type,
            reasoning_preset=args.reasoning_preset,
            reasoning=reasoning,
            selected_consultants=selected_consultants,
        )
        _emit_result(result, args.json)
        return 0
    except (
        MutationLockError,
        LifecycleError,
        json.JSONDecodeError,
        OSError,
        tarfile.TarError,
    ) as error:
        if args.json:
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
