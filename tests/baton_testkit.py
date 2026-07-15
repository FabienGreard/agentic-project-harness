#!/usr/bin/env python3
"""Disposable source, release, and consumer fixtures for Baton v0.6.0 tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
RELEASE_TOOL = ROOT / "scripts/release_bundle.py"
ARTIFACTS = {
    "install.sh",
    "baton-new-project.tar.gz",
    "baton-adoption.tar.gz",
    "baton-manifest.json",
    "SHA256SUMS",
}
SKILLS = (
    "brainstorm",
    "code-review",
    "fire-consultant",
    "hire-consultant",
    "improve-codebase-architecture",
)


def run(
    arguments: Sequence[Any],
    *,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        environment.update(env)
    completed = subprocess.run(
        [str(item) for item in arguments],
        cwd=str(cwd or ROOT),
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != expected:
        raise AssertionError(
            f"expected exit {expected}, got {completed.returncode}: "
            f"{' '.join(str(item) for item in arguments)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def json_output(completed: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"command did not emit one JSON value: {completed.stdout!r}") from error
    if not isinstance(value, dict):
        raise AssertionError(f"command JSON is not an object: {value!r}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit(source: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()


def inferred_class(relative: str) -> str:
    if relative == "template/.baton/integration/README.md":
        return "adoption-runtime"
    if relative.startswith("template/.baton/"):
        payload_relative = relative.removeprefix("template/")
        template_prefixes = (
            ".baton/state/",
            ".baton/dashboard/",
            ".baton/docs/",
            ".baton/decisions/",
            ".baton/implementation-reports/",
            ".baton/prds/",
            ".baton/review-packets/",
            ".baton/tickets/",
        )
        if payload_relative == ".baton/thread-registry.md" or payload_relative.startswith(template_prefixes):
            return "template-only"
        return "shared"
    return "source-only"


def projected_path(source_path: str, classification: str, payload: str) -> Optional[str]:
    if not source_path.startswith("template/") or classification == "source-only":
        return None
    relative = source_path.removeprefix("template/")
    if payload == "new-project":
        return None if classification == "adoption-runtime" else relative
    if classification in {"shared", "adoption-runtime"}:
        return relative
    return ".baton/integration/starter/" + relative.removeprefix(".baton/")


def make_candidate(base: Path, version: str, *, marker: str = "") -> Path:
    source = base / f"source-{version.replace('.', '-')}"
    source.mkdir(parents=True)
    (source / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/install.sh", source / "scripts/install.sh")
    (source / "VERSION").write_text(version + "\n", encoding="utf-8")
    (source / "README.md").write_text("# Baton source fixture\n", encoding="utf-8")
    (source / "LICENSE").write_text("fixture license\n", encoding="utf-8")
    for relative in (
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".baton/AGENTS.md",
        ".baton/state/project.json",
        ".baton/metadata.json",
        "docs/source-only.md",
        "tests/source-only.txt",
        "scripts/source-only.txt",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"source-only fixture: {relative}\n", encoding="utf-8")
    shutil.copytree(
        ROOT / "template",
        source / "template",
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    if marker:
        guide = source / "template/.baton/guide.md"
        guide.write_text(guide.read_text(encoding="utf-8") + f"\nRelease marker: {marker}\n", encoding="utf-8")
        starter_overview = source / "template/.baton/docs/overview.md"
        starter_overview.write_text(
            starter_overview.read_text(encoding="utf-8")
            + f"\nStarter release marker: {marker}\n",
            encoding="utf-8",
        )
    classification = source / "release/source-classification.json"
    classification.parent.mkdir(parents=True)
    classification.write_text("{}\n", encoding="utf-8")
    run(["git", "init", "-q", "-b", "main"], cwd=source)
    run(["git", "config", "user.email", "baton-smoke@example.test"], cwd=source)
    run(["git", "config", "user.name", "Baton Smoke"], cwd=source)
    run(["git", "add", "."], cwd=source)
    run([sys.executable, RELEASE_TOOL, "classify", "--source", source, "--write"])
    run(["git", "add", "release/source-classification.json"], cwd=source)
    run(["git", "commit", "-qm", f"fixture {version}"], cwd=source)
    return source


def build_bundle(
    source: Path,
    output: Path,
    *,
    origins: Iterable[Tuple[str, str, Optional[str]]] = (),
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    version = (source / "VERSION").read_text(encoding="utf-8").strip()
    arguments: List[Any] = [
        sys.executable,
        RELEASE_TOOL,
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
    for tag, commit, manifest_digest in origins:
        specification = f"{tag}={commit}"
        if manifest_digest is not None:
            specification += f",{manifest_digest}"
        arguments.extend(["--supported-upgrade-origin", specification])
    return run(arguments, expected=expected)


def manifest(bundle: Path) -> Dict[str, Any]:
    return json.loads((bundle / "baton-manifest.json").read_text(encoding="utf-8"))


def archive_names(bundle: Path, payload: str) -> List[str]:
    name = manifest(bundle)["payloads"][payload]["artifact"]
    with tarfile.open(bundle / name, "r:gz") as archive:
        return archive.getnames()


def install_bundle(
    bundle: Path,
    target: Path,
    state_home: Path,
    *,
    expected: int = 0,
    extra_env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "BATON_RELEASE_DIR": str(bundle),
        "XDG_STATE_HOME": str(state_home),
        "HOME": str(state_home.parent / "home"),
    }
    if extra_env:
        environment.update(extra_env)
    return run(
        ["bash", bundle / "install.sh", "--yes", "--json", "--target", target],
        cwd=state_home.parent,
        env=environment,
        expected=expected,
    )


def baton(
    target: Path,
    arguments: Sequence[Any],
    state_home: Path,
    *,
    bundle: Optional[Path] = None,
    expected: int = 0,
    extra_env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "XDG_STATE_HOME": str(state_home),
        "HOME": str(state_home.parent / "home"),
    }
    if bundle is not None:
        environment["BATON_RELEASE_DIR"] = str(bundle)
    if extra_env:
        environment.update(extra_env)
    return run(
        [target / ".baton/bin/baton", *arguments],
        cwd=target,
        env=environment,
        expected=expected,
    )


def tree_snapshot(root: Path) -> Dict[str, Tuple[str, str]]:
    if not root.exists():
        return {}
    result: Dict[str, Tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            result[relative] = ("directory", "")
        else:
            result[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def changed_paths(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def parse_value(raw: str) -> Any:
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"'):
        return json.loads(raw)
    raise AssertionError(f"unsupported TOML value: {raw}")


def semantic_toml(path: Path) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    current = parsed
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        table = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]", line)
        if table:
            current = parsed
            for part in table.group(1).split("."):
                value = current.setdefault(part, {})
                if not isinstance(value, dict):
                    raise AssertionError(f"table collision at line {number}")
                current = value
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if assignment is None:
            raise AssertionError(f"unsupported TOML syntax at line {number}: {raw_line}")
        key, raw_value = assignment.groups()
        if key in current:
            raise AssertionError(f"duplicate TOML key at line {number}: {key}")
        current[key] = parse_value(raw_value.strip())
    return parsed


def expected_consumer_config(consultants: Sequence[str] = ("product-designer",)) -> Dict[str, Any]:
    expected: Dict[str, Any] = {
        "approval_policy": "on-request",
        "approvals_reviewer": "auto_review",
        "sandbox_mode": "workspace-write",
        "agents": {
            "max_threads": 4,
            "max_depth": 1,
            "management": {
                "description": "Own project outcomes, priority, scope, readiness, and release decisions.",
                "config_file": "../.baton/agents/management.toml",
            },
            "operations": {
                "description": "Own delivery, Contractor dispatch, integration, and verification.",
                "config_file": "../.baton/agents/operations.toml",
            },
            "contractor": {
                "description": "Execute one bounded assignment for Operations.",
                "config_file": "../.baton/agents/contractor.toml",
            },
            "internal_audit": {
                "description": "Independently evaluate Baton behavior without joining the project team.",
                "config_file": "../.baton/agents/internal-audit.toml",
            },
        },
        "sandbox_workspace_write": {"network_access": True},
    }
    for identifier in consultants:
        name = "consultant_" + identifier.replace("-", "_")
        expected["agents"][name] = {
            "description": f"Recurring Consultant for the {identifier.replace('-', ' ')} domain.",
            "config_file": f"../.baton/agents/consultant-{identifier}.toml",
        }
    return expected


def assert_no_python_cache(root: Path) -> None:
    caches = [path for path in root.rglob("__pycache__")]
    pyc = [path for path in root.rglob("*.pyc")]
    if caches or pyc:
        raise AssertionError(f"Python cache artifacts exist: {caches + pyc}")


def make_mature_project(root: Path) -> Dict[str, bytes]:
    fixtures = {
        "VERSION": b"9.4.2\n",
        "LICENSE": b"consumer license\n",
        ".github/workflows/ci.yml": b"name: consumer-ci\n",
        "tests/existing_test.py": b"assert True\n",
        "tools/existing_tool.py": b"print('consumer')\n",
        "docs/architecture.md": b"# Consumer architecture\n",
        "node_modules/vendor/package.json": b'{"name":"vendor"}\n',
        "vendor/nested/cache.bin": b"ignored vendor bytes\n",
        ".gitignore": b"node_modules/\nvendor/\n",
        "AGENTS.md": b"# Existing governance\n\nPreserve this instruction.\n",
        ".codex/config.toml": b"[project]\nname = \"consumer-owned\"\n",
        ".agents/skills/brainstorm/SKILL.md": b"# Existing brainstorm skill\n",
    }
    for relative, content in fixtures.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    outside = root.parent / "outside-vendor"
    outside.mkdir(exist_ok=True)
    (outside / "sentinel.txt").write_text("outside\n", encoding="utf-8")
    (root / "node_modules/vendor/outside-link").symlink_to(outside)
    return fixtures


def make_activation_proposal(target: Path, destination: Path, *, valid: bool = True) -> Path:
    shutil.copytree(target / ".baton/integration/starter/state", destination / "state")
    if not valid:
        return destination
    project_path = destination / "state/project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    project["project"].update(
        {
            "name": "Mature consumer",
            "outcome": "Preserve the mature repository while using Baton for coordination.",
            "currentGoal": "MATURE-GOAL-001",
            "phase": "Active delivery",
            "templateMode": False,
            "lastVerified": "2026-07-15",
        }
    )
    project["baton"] = {
        "owner": "Management",
        "action": "Define the first bounded mature-project ticket",
        "returnTrigger": "A Ready ticket is recorded",
    }
    project_path.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    goals = {
        "schemaVersion": 1,
        "recordType": "goals",
        "goals": [
            {
                "id": "MATURE-GOAL-001",
                "title": "Adopt Baton without replacing project ownership",
                "status": "Active",
                "priority": "P1",
                "owner": "Management",
                "objective": "Activate reviewed mature-project coordination state.",
                "context": "The project predates Baton and retains its identity and assets.",
                "dependencies": [],
                "blockers": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        ],
    }
    (destination / "state/goals.json").write_text(
        json.dumps(goals, indent=2) + "\n", encoding="utf-8"
    )
    return destination
