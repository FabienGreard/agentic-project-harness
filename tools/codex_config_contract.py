#!/usr/bin/env python3
"""Dependency-free parser and exact contract for project-scoped Codex config."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


EXPECTED_CODEX_CONFIG: dict[str, Any] = {
    "approval_policy": "on-request",
    "approvals_reviewer": "auto_review",
    "sandbox_mode": "workspace-write",
    "agents": {
        "max_threads": 4,
        "max_depth": 1,
    },
    "sandbox_workspace_write": {
        "network_access": True,
    },
}


def _parse_value(raw: str) -> Any:
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"'):
        value = json.loads(raw)
        if isinstance(value, str):
            return value
    raise ValueError(f"unsupported TOML value: {raw}")


def parse_codex_config(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    current = parsed
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section = re.fullmatch(r"\[([A-Za-z0-9_-]+)\]", line)
        if section:
            name = section.group(1)
            if name in parsed:
                raise ValueError(f"duplicate section at line {number}: {name}")
            current = {}
            parsed[name] = current
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if not assignment:
            raise ValueError(f"unsupported TOML syntax at line {number}: {raw_line}")
        key, raw_value = assignment.groups()
        if key in current:
            raise ValueError(f"duplicate key at line {number}: {key}")
        current[key] = _parse_value(raw_value.strip())
    return parsed


def assert_codex_config(path: Path) -> None:
    actual = parse_codex_config(path)
    if actual != EXPECTED_CODEX_CONFIG:
        raise AssertionError(f"Codex config mismatch: expected {EXPECTED_CODEX_CONFIG!r}, got {actual!r}")
