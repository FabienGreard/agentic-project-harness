#!/usr/bin/env python3
"""Plan and apply fail-closed Baton removal."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
import uuid

sys.dont_write_bytecode = True

from baton_lifecycle import (
    AGENTS_END,
    AGENTS_START,
    LifecycleError,
    entry_digest,
    remove_entry,
    safe_relative,
    sha256_file,
    utc_now,
)
from harness_lock import MutationLockError, mutation_lock


PLAN_SCHEMA_VERSION = 1


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _plan_digest(plan: dict[str, Any]) -> str:
    unsigned = dict(plan)
    unsigned.pop("planDigest", None)
    return hashlib.sha256(_json_bytes(unsigned)).hexdigest()


def _tree_digest(root: Path) -> str | None:
    if root.is_symlink() or not root.is_dir():
        return None
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "kind": "symlink", "sha256": hashlib.sha256(os.readlink(path).encode("utf-8")).hexdigest()})
        elif path.is_file():
            entries.append({"path": relative, "kind": "file", "sha256": sha256_file(path)})
        else:
            return None
    return hashlib.sha256(_json_bytes(entries)).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise LifecycleError(f"required Baton file is missing or unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"invalid Baton JSON at {path}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"expected a JSON object at {path}")
    return value


def _agents_action(root: Path, metadata: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    path = root / "AGENTS.md"
    if not path.exists() and not path.is_symlink():
        return None, []
    if path.is_symlink() or not path.is_file():
        return None, ["Preserve AGENTS.md: it is not a safe regular file."]
    content = path.read_text(encoding="utf-8")
    start = content.find(AGENTS_START)
    end = content.find(AGENTS_END)
    if (
        start == -1
        or end < start
        or content.find(AGENTS_START, start + 1) != -1
        or content.find(AGENTS_END, end + 1) != -1
    ):
        return None, ["Preserve AGENTS.md: the Baton block is missing or ambiguous."]
    end += len(AGENTS_END)
    block = content[start:end]
    expected_block = metadata.get("managedBlocks", {}).get("AGENTS.md")
    actual_block = hashlib.sha256(block.encode("utf-8")).hexdigest()
    if expected_block and expected_block != actual_block:
        return None, ["Preserve AGENTS.md: the Baton block differs from its managed baseline."]
    return {
        "path": "AGENTS.md",
        "action": "remove-block",
        "expectedSha256": sha256_file(path),
        "expectedBlockSha256": actual_block,
    }, []


def create_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    baton = root / ".baton"
    metadata_path = baton / "metadata.json"
    metadata = _read_json(metadata_path)
    baton_digest = _tree_digest(baton)
    if baton_digest is None:
        raise LifecycleError("the Baton directory is missing or unsafe")

    actions: list[dict[str, Any]] = []
    manual_actions: list[str] = []
    agents, agents_manual = _agents_action(root, metadata)
    if agents:
        actions.append(agents)
    manual_actions.extend(agents_manual)

    managed = metadata.get("managedFiles", {})
    if not isinstance(managed, dict):
        raise LifecycleError("Baton metadata managedFiles is invalid")
    for relative, record in sorted(managed.items()):
        if relative == "AGENTS.md" or relative.startswith(".baton/"):
            continue
        safe_relative(relative)
        if not isinstance(record, dict):
            raise LifecycleError(f"Baton metadata record is invalid: {relative}")
        path = root.joinpath(*Path(relative).parts)
        actual = entry_digest(path)
        baseline = record.get("baselineSha256")
        if actual is not None and actual == baseline:
            actions.append({"path": relative, "action": "remove", "expectedSha256": actual})
        else:
            manual_actions.append(f"Preserve {relative}: it differs from its managed baseline or is missing.")

    # Source checkouts have no release managed-file inventory. Still recognize
    # exact Baton discovery links and fail closed on every collision.
    skills_root = root / ".agents/skills"
    if skills_root.is_dir() and not skills_root.is_symlink():
        for path in sorted(skills_root.iterdir()):
            relative = path.relative_to(root).as_posix()
            if any(action["path"] == relative for action in actions):
                continue
            expected = f"../../.baton/skills/{path.name}"
            if path.is_symlink() and os.readlink(path) == expected:
                actions.append({"path": relative, "action": "remove", "expectedTarget": expected})
            elif path.exists() or path.is_symlink():
                manual_actions.append(f"Preserve {relative}: it is not Baton's exact discovery link.")

    plan: dict[str, Any] = {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "action": "scrap",
        "projectRoot": str(root),
        "createdAt": utc_now(),
        "metadataSha256": sha256_file(metadata_path),
        "batonTreeSha256": baton_digest,
        "actions": actions,
        "manualActions": sorted(set(manual_actions)),
    }
    plan["planDigest"] = _plan_digest(plan)
    return plan


def write_plan(plan: dict[str, Any], output: Path, root: Path) -> None:
    root = root.resolve()
    output = output.expanduser().resolve(strict=False)
    baton = root / ".baton"
    if output == baton or baton in output.parents:
        raise LifecycleError("the scrap plan must be stored outside .baton")
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise LifecycleError("the scrap plan output is unsafe")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_json_bytes(plan))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _verify_plan(plan: dict[str, Any], root: Path) -> None:
    if (
        plan.get("schemaVersion") != PLAN_SCHEMA_VERSION
        or plan.get("action") != "scrap"
        or plan.get("projectRoot") != str(root)
        or plan.get("planDigest") != _plan_digest(plan)
    ):
        raise LifecycleError("the scrap plan is invalid, belongs to another Repository, or was modified")
    metadata = root / ".baton/metadata.json"
    if not metadata.is_file() or metadata.is_symlink() or sha256_file(metadata) != plan.get("metadataSha256"):
        raise LifecycleError("Baton metadata changed after the scrap plan was created")
    if _tree_digest(root / ".baton") != plan.get("batonTreeSha256"):
        raise LifecycleError("the Baton tree changed after the scrap plan was created")
    actions = plan.get("actions")
    if not isinstance(actions, list):
        raise LifecycleError("the scrap plan action list is invalid")
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            raise LifecycleError("the scrap plan contains an invalid action")
        relative = safe_relative(action.get("path"))
        if relative in seen or relative.startswith(".baton/"):
            raise LifecycleError("the scrap plan contains a duplicate or unsafe host action")
        seen.add(relative)
        path = root.joinpath(*Path(relative).parts)
        if action.get("action") == "remove-block":
            if path.is_symlink() or not path.is_file() or sha256_file(path) != action.get("expectedSha256"):
                raise LifecycleError(f"{relative} changed after the scrap plan was created")
        elif action.get("action") == "remove":
            if "expectedTarget" in action:
                if not path.is_symlink() or os.readlink(path) != action["expectedTarget"]:
                    raise LifecycleError(f"{relative} changed after the scrap plan was created")
            elif entry_digest(path) != action.get("expectedSha256"):
                raise LifecycleError(f"{relative} changed after the scrap plan was created")
        else:
            raise LifecycleError("the scrap plan contains an unknown action")


def _transaction_directory(root: Path, transaction_id: str) -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")).expanduser().resolve()
    project_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    transaction = (state_home / "baton" / project_id / "scrap" / transaction_id).resolve(strict=False)
    if transaction == root or root in transaction.parents:
        raise LifecycleError("scrap transaction evidence must stay outside the Repository")
    return transaction


def _backup(root: Path, transaction: Path, actions: list[dict[str, Any]]) -> Path:
    backup = transaction / "backup"
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copytree(root / ".baton", backup / ".baton", symlinks=True)
    for action in actions:
        relative = action["path"]
        source = root.joinpath(*Path(relative).parts)
        if not source.exists() and not source.is_symlink():
            continue
        destination = backup.joinpath(*Path(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            destination.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, destination)
        else:
            shutil.copytree(source, destination, symlinks=True)
    return backup


def _without_baton_block(content: str) -> str:
    start = content.index(AGENTS_START)
    end = content.index(AGENTS_END, start) + len(AGENTS_END)
    remaining = (content[:start] + content[end:]).strip()
    if remaining in {"", "# Baton discovery", "# Repository agents"}:
        return ""
    return remaining + "\n"


def _restore(root: Path, backup: Path, actions: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    try:
        remove_entry(root / ".baton")
        shutil.copytree(backup / ".baton", root / ".baton", symlinks=True)
    except OSError as error:
        failures.append(f".baton: {error}")
    for action in actions:
        relative = action["path"]
        source = backup.joinpath(*Path(relative).parts)
        destination = root.joinpath(*Path(relative).parts)
        try:
            remove_entry(destination)
            if source.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(os.readlink(source))
            elif source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            elif source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
        except OSError as error:
            failures.append(f"{relative}: {error}")
    return failures


def apply_plan(root: Path, plan_path: Path, *, assume_yes: bool) -> dict[str, Any]:
    root = root.resolve()
    plan = _read_json(plan_path.expanduser().resolve())
    if not assume_yes:
        if not sys.stdin.isatty():
            raise LifecycleError("scrap apply requires a terminal or --yes")
        answer = input("Scrap Baton using the reviewed plan? [y/N] ").strip().casefold()
        if answer not in {"y", "yes"}:
            raise LifecycleError("no changes made")
    transaction_id = f"scrap-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    transaction = _transaction_directory(root, transaction_id)
    actions = plan.get("actions", [])
    try:
        with mutation_lock(root, "scrap"):
            _verify_plan(plan, root)
            transaction.mkdir(parents=True, exist_ok=False)
            backup = _backup(root, transaction, actions)
            report_path = transaction / "scrap-report.json"
            report = {
                "ok": False,
                "action": "scrap",
                "result": "prepared",
                "transactionId": transaction_id,
                "planDigest": plan["planDigest"],
                "backupPath": str(backup),
                "manualActions": plan.get("manualActions", []),
                "removed": [],
            }
            report_path.write_bytes(_json_bytes(report))
            try:
                for action in actions:
                    relative = action["path"]
                    path = root.joinpath(*Path(relative).parts)
                    if action["action"] == "remove-block":
                        remaining = _without_baton_block(path.read_text(encoding="utf-8"))
                        if remaining:
                            path.write_text(remaining, encoding="utf-8")
                        else:
                            path.unlink()
                    else:
                        remove_entry(path)
                    report["removed"].append(relative)
                remove_entry(root / ".baton")
                report["removed"].append(".baton")
                for directory in (root / ".agents/skills", root / ".agents", root / ".codex"):
                    if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                        directory.rmdir()
                report.update({"ok": True, "result": "scrapped", "completedAt": utc_now()})
                report_path.write_bytes(_json_bytes(report))
                return {**report, "reportPath": str(report_path)}
            except BaseException as error:
                failures = _restore(root, backup, actions)
                report.update(
                    {
                        "result": "rollback-incomplete" if failures else "rolled-back",
                        "error": str(error),
                        "rollbackErrors": failures,
                    }
                )
                report_path.write_bytes(_json_bytes(report))
                if failures:
                    raise LifecycleError("scrap failed and rollback was incomplete: " + "; ".join(failures)) from error
                raise LifecycleError(f"scrap failed and was rolled back: {error}") from error
    except MutationLockError as error:
        raise LifecycleError(str(error)) from error
