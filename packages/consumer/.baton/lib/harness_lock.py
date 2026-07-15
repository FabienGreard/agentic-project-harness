#!/usr/bin/env python3
"""Shared cross-process mutation lock for one installed Baton project."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from typing import Iterator


class MutationLockError(RuntimeError):
    """The project mutation lock could not be acquired safely."""


def _lock_path(project_root: Path) -> Path:
    project = project_root.resolve()
    state_home = Path("/tmp").resolve() / f"baton-{os.getuid()}"
    project_id = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:16]
    lock = state_home / project_id / "mutation.lock"
    resolved_lock = lock.resolve(strict=False)
    if resolved_lock == project or project in resolved_lock.parents:
        raise MutationLockError("mutation lock data must be outside the working tree")
    candidate = lock
    while candidate != state_home:
        if candidate.is_symlink():
            raise MutationLockError(
                "mutation lock path must not contain a symbolic link"
            )
        candidate = candidate.parent
    return lock


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        details = path.lstat()
    except OSError as error:
        raise MutationLockError(f"cannot create external mutation lock directory: {error}") from error
    if (
        path.is_symlink()
        or not stat.S_ISDIR(details.st_mode)
        or details.st_uid != os.getuid()
        or stat.S_IMODE(details.st_mode) & 0o077
    ):
        raise MutationLockError(
            "mutation lock directory must be a private directory owned by the current user"
        )


@contextmanager
def mutation_lock(project_root: Path, operation: str) -> Iterator[Path]:
    """Serialize every state, team, install, and update mutation for a project."""
    if not isinstance(operation, str) or not operation.strip():
        raise MutationLockError("mutation lock operation must be named")
    lock = _lock_path(project_root)
    try:
        _ensure_private_directory(lock.parents[1])
        _ensure_private_directory(lock.parent)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock, flags, 0o600)
        handle = os.fdopen(descriptor, "r+", encoding="utf-8")
    except OSError as error:
        raise MutationLockError(f"cannot open external mutation lock: {error}") from error
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "operation": operation.strip(),
                    "acquiredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
        delay_raw = os.environ.get("BATON_TEST_HOLD_MUTATION_LOCK_MS")
        if delay_raw is None:
            delay_raw = os.environ.get("APH_TEST_HOLD_MUTATION_LOCK_MS")
        if delay_raw:
            try:
                delay_ms = int(delay_raw)
            except ValueError as error:
                raise MutationLockError("invalid mutation-lock test delay") from error
            if delay_ms < 0 or delay_ms > 5000:
                raise MutationLockError("mutation-lock test delay is out of range")
            time.sleep(delay_ms / 1000)
        yield lock
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
