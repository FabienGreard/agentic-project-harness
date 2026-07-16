#!/usr/bin/env python3
"""Source-only evaluator for the Baton v0.6.0 distribution candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


VERSION = "0.6.0"
TEMPLATE_PREFIX = "template/.baton/"
PROJECTIONS = {"shared", "starter", "adoption-only"}
ADOPTION_ONLY_PATH = "template/.baton/migration/README.md"
STARTER_PATHS = {
    "template/.baton/AGENTS.md",
}
STARTER_PREFIXES = (
    "template/.baton/memory/",
    "template/.baton/state/",
    "template/.baton/views/",
    "template/.baton/records/",
)
SKILLS = (
    "boot",
    "brainstorm",
    "code-review",
    "control",
    "doctor",
    "improve-codebase-architecture",
    "roster",
    "scrap",
    "terminal",
    "upgrade",
)
MANAGEMENT_COMMANDS = (
    "boot",
    "control",
    "roster",
    "terminal",
    "upgrade",
    "doctor",
    "scrap",
)
CACHE_SCAN_SCOPES = (
    ".baton",
    "template/.baton",
    "scripts",
    "tests",
)
PUBLIC_DOC_GUIDES = (
    "docs/getting-started.md",
    "docs/installation.md",
    "docs/cli.md",
    "docs/customization.md",
    "docs/architecture.md",
    "docs/releasing.md",
)
PUBLIC_DOC_ASSETS = (
    "docs/assets/baton-logo.png",
    "docs/assets/baton-social-preview.png",
    "docs/assets/baton-wordmark.png",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BASE_CONFIG: Dict[str, Any] = {
    "approval_policy": "on-request",
    "approvals_reviewer": "auto_review",
    "sandbox_mode": "workspace-write",
    "agents": {"max_threads": 4, "max_depth": 1},
    "sandbox_workspace_write": {"network_access": True},
}


class EvaluationFailure(AssertionError):
    """One source contract is not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationFailure(message)


def read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationFailure(f"{path}: invalid JSON: {error}") from error
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def run(root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        list(arguments),
        cwd=root,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_paths(root: Path, *arguments: str) -> List[str]:
    completed = run(root, ["git", "ls-files", "-z", *arguments])
    require(completed.returncode == 0, completed.stderr.strip() or "git ls-files failed")
    return sorted(item for item in completed.stdout.split("\0") if item)


def candidate_paths(root: Path) -> List[str]:
    visible = git_paths(root, "--cached", "--others", "--exclude-standard")
    return [
        relative
        for relative in visible
        if (root / relative).exists() or (root / relative).is_symlink()
    ]


def cache_artifacts(root: Path) -> List[str]:
    """Return candidate cache paths without walking ignored or vendor trees."""
    visible = candidate_paths(root)
    ignored_markers = git_paths(
        root,
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
        "--",
        *CACHE_SCAN_SCOPES,
    )
    artifacts = set()
    for raw in (*visible, *ignored_markers):
        relative = raw.rstrip("/")
        parts = PurePosixPath(relative).parts
        if "__pycache__" in parts or relative.endswith(".pyc"):
            artifacts.add(relative)
    return sorted(artifacts)


def template_sources(root: Path) -> List[str]:
    template_paths = [path for path in candidate_paths(root) if path.startswith("template/")]
    invalid = sorted(path for path in template_paths if not path.startswith(TEMPLATE_PREFIX))
    require(not invalid, f"consumer source exists outside template/.baton: {invalid}")
    require(bool(template_paths), "consumer source template/.baton is empty")
    require(ADOPTION_ONLY_PATH in template_paths, f"adoption-only source is missing: {ADOPTION_ONLY_PATH}")
    missing_starter = sorted(STARTER_PATHS - set(template_paths))
    require(not missing_starter, f"starter sources are missing: {missing_starter}")
    return sorted(template_paths)


def projection_for(source_path: str) -> str:
    require(source_path.startswith(TEMPLATE_PREFIX), f"consumer source is outside template/.baton: {source_path}")
    if source_path == ADOPTION_ONLY_PATH:
        return "adoption-only"
    if source_path in STARTER_PATHS or source_path.startswith(STARTER_PREFIXES):
        return "starter"
    return "shared"


def payload_path(source_path: str, projection: str, payload: str) -> Optional[str]:
    require(projection in PROJECTIONS, f"unsupported payload projection for {source_path}: {projection!r}")
    require(source_path.startswith(TEMPLATE_PREFIX), f"consumer source is outside template/.baton: {source_path}")
    relative = source_path.removeprefix("template/")
    if payload == "new-project":
        return None if projection == "adoption-only" else relative
    if projection in {"shared", "adoption-only"}:
        return relative
    if projection == "starter":
        return ".baton/migration/starter/" + relative.removeprefix(".baton/")
    return None


def parse_value(raw: str) -> Any:
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"'):
        value = json.loads(raw)
        require(isinstance(value, str), f"unsupported TOML value: {raw}")
        return value
    raise EvaluationFailure(f"unsupported TOML value: {raw}")


def parse_semantic_toml(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    current = parsed
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        table = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]", line)
        if table:
            current = parsed
            for part in table.group(1).split("."):
                existing = current.get(part)
                if existing is None:
                    nested: Dict[str, Any] = {}
                    current[part] = nested
                    current = nested
                else:
                    require(isinstance(existing, dict), f"TOML table collision at line {number}")
                    current = existing
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        require(assignment is not None, f"unsupported TOML syntax at line {number}: {raw_line}")
        key, raw_value = assignment.groups()
        require(key not in current, f"duplicate TOML key at line {number}: {key}")
        current[key] = parse_value(raw_value.strip())
    return parsed


def expected_config(agent_records: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
    expected = json.loads(json.dumps(BASE_CONFIG))
    agents = expected["agents"]
    for name, (description, filename) in agent_records.items():
        agents[name] = {
            "description": description,
            "config_file": f"../.baton/agents/{filename}",
        }
    return expected


def source_config() -> Dict[str, Any]:
    return expected_config(
        {
            "management": (
                "Own Baton product outcomes, priority, scope, readiness, and release decisions.",
                "management.toml",
            ),
            "operations": (
                "Own Baton delivery, Contractor dispatch, integration, and verification.",
                "operations.toml",
            ),
            "contractor": (
                "Execute one bounded Baton assignment for Operations.",
                "contractor.toml",
            ),
            "internal_audit": (
                "Independently evaluate Baton without joining its product team.",
                "internal-audit.toml",
            ),
            "consultant_product_designer": (
                "Provide recurring product and interaction design readiness and acceptance.",
                "consultant-product-designer.toml",
            ),
        }
    )


def consumer_config() -> Dict[str, Any]:
    return expected_config(
        {
            "management": (
                "Own project outcomes, priority, scope, readiness, and release decisions.",
                "management.toml",
            ),
            "operations": (
                "Own delivery, Contractor dispatch, integration, and verification.",
                "operations.toml",
            ),
            "contractor": (
                "Execute one bounded assignment for Operations.",
                "contractor.toml",
            ),
            "internal_audit": (
                "Independently evaluate Baton behavior without joining the project team.",
                "internal-audit.toml",
            ),
            "consultant_product_designer": (
                "Recurring Consultant for the product designer domain.",
                "consultant-product-designer.toml",
            ),
        }
    )


def check_version(root: Path) -> None:
    require((root / "VERSION").read_text(encoding="utf-8") == VERSION + "\n", f"VERSION is not exactly {VERSION}")


def check_source_identity(root: Path) -> None:
    root_agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    require("<!-- BATON:START -->" in root_agents and ".baton/AGENTS.md" in root_agents, "root AGENTS.md does not expose Baton discovery")
    metadata = read_json(root / ".baton/metadata.json")
    require(metadata.get("schemaVersion") == 3, "source metadata schema is not 3")
    require(metadata.get("batonVersion") == VERSION, "source metadata Baton version differs from VERSION")
    require(metadata.get("installationStatus") == "Source Repository", "root .baton is not source-only state")
    require(metadata.get("repositoryVersion") is None, "source metadata must not derive repositoryVersion from VERSION")
    project = read_json(root / ".baton/state/project.json")
    require(project.get("project", {}).get("name") == "Baton", "source project state is not Baton")
    require(project.get("project", {}).get("templateMode") is False, "source repository is still template mode")


def check_consumer_layout(root: Path) -> None:
    obsolete = (
        "packages",
        "examples",
        "tools",
        "release",
        "install.sh",
        "docs/evals",
        "docs/release-policy.md",
        "scripts/source-classification.json",
    )
    present = [
        relative
        for relative in obsolete
        if (root / relative).exists() or (root / relative).is_symlink()
    ]
    require(not present, f"obsolete source-layout paths remain: {present}")
    source_utilities = (
        "scripts/install.sh",
        "scripts/harness_eval.py",
        "scripts/release_bundle.py",
    )
    missing_utilities = [relative for relative in source_utilities if not (root / relative).is_file()]
    require(not missing_utilities, f"consolidated source utilities are incomplete: {missing_utilities}")
    consumer = root / "template"
    require(consumer.is_dir(), "template is missing")
    paths = [path.relative_to(consumer).as_posix() for path in consumer.rglob("*") if not path.is_dir() or path.is_symlink()]
    bad = sorted(path for path in paths if not path.startswith(".baton/"))
    require(not bad, f"consumer source has files outside .baton: {bad}")
    required = {
        ".baton/AGENTS.md",
        ".baton/bin/baton",
        ".baton/migration/README.md",
        ".baton/lib/baton_cli.py",
        ".baton/lib/baton_lifecycle.py",
        ".baton/lib/harness_state.py",
        ".baton/lib/harness_team.py",
        ".baton/state/project.json",
        ".baton/team-presets.json",
        ".baton/records/README.md",
    }
    missing = sorted(required - set(paths))
    require(not missing, f"consumer source is incomplete: {missing}")
    require(".baton/metadata.json" not in paths, "consumer source contains release-specific metadata")


def check_template_boundary(root: Path) -> None:
    sources = template_sources(root)
    require(all(path.startswith(TEMPLATE_PREFIX) for path in sources), "consumer source escaped template/.baton")
    require(not (root / "scripts/source-classification.json").exists(), "obsolete source-classification inventory remains")
    require(projection_for(ADOPTION_ONLY_PATH) == "adoption-only", "adoption-only projection is not explicit")
    require(
        all(projection_for(path) == "starter" for path in STARTER_PATHS),
        "starter projections are not explicit",
    )


def check_payload_projection(root: Path) -> None:
    sources = template_sources(root)
    projected: Dict[str, List[str]] = {"new-project": [], "adoption": []}
    for payload in projected:
        for source_path in sources:
            destination = payload_path(source_path, projection_for(source_path), payload)
            if destination is not None:
                projected[payload].append(destination)
        require(projected[payload], f"{payload} payload is empty")
        require(len(projected[payload]) == len(set(projected[payload])), f"{payload} payload contains duplicate paths")
        bad = sorted(path for path in projected[payload] if not path.startswith(".baton/"))
        require(not bad, f"{payload} payload pollutes the consumer root: {bad}")
    require(not any(path.startswith(".baton/migration/starter/") for path in projected["new-project"]), "new-project payload contains quarantined starter paths")
    require(any(path.startswith(".baton/migration/starter/state/") for path in projected["adoption"]), "adoption payload does not quarantine starter state")
    require(".baton/state/project.json" in projected["new-project"], "new-project payload lacks canonical starter state")
    require(".baton/state/project.json" not in projected["adoption"], "adoption payload activates starter state")
    require(".baton/AGENTS.md" in projected["new-project"], "new-project payload lacks its agent map")
    require(".baton/AGENTS.md" not in projected["adoption"], "adoption payload activates the starter agent map")
    require(
        ".baton/migration/starter/AGENTS.md" in projected["adoption"],
        "adoption payload does not quarantine the starter agent map",
    )
    require(
        {path for path in projected["new-project"] if path.startswith(".baton/memory/")}
        == {".baton/memory/history.jsonl", ".baton/memory/memory.json"},
        "new-project payload does not contain the exact active starter memory",
    )
    require(
        {path for path in projected["adoption"] if path.startswith(".baton/migration/starter/memory/")}
        == {
            ".baton/migration/starter/memory/history.jsonl",
            ".baton/migration/starter/memory/memory.json",
        },
        "adoption payload does not contain the exact quarantined starter memory",
    )
    require(
        not any(path.startswith(".baton/memory/") for path in projected["adoption"]),
        "adoption payload activates starter memory",
    )
    require(not any(path.startswith(".baton/") for path in sources), "root source .baton entered consumer projection")


def check_release_contract(root: Path) -> None:
    source = (root / "scripts/release_bundle.py").read_text(encoding="utf-8")
    required = (
        'NEW_PROJECT_ARCHIVE = "baton-new-project.tar.gz"',
        'ADOPTION_ARCHIVE = "baton-adoption.tar.gz"',
        'MANIFEST_NAME = "baton-manifest.json"',
        'TEMPLATE_PREFIX = "template/.baton/"',
        'PROJECTIONS = {"shared", "starter", "adoption-only"}',
        'MANIFEST_SCHEMA = "baton.release-bundle/v1"',
        'INSTALLER_SOURCE = "scripts/install.sh"',
        '"memorySchemaVersion": args.memory_schema_version',
    )
    missing = [value for value in required if value not in source]
    require(not missing, f"release builder contract is incomplete: {missing}")
    require("sourceClassificationSha256" not in source, "release manifest retains source-classification metadata")
    require('add_parser("classify"' not in source, "release builder retains the classification command")
    require(
        "upgrade origins must use TAG=FULL_COMMIT,MANIFEST_SHA256" in source,
        "release builder does not require immutable origin commit and manifest digests",
    )


def check_installer_surface(root: Path) -> None:
    source = (root / "scripts/install.sh").read_text(encoding="utf-8")
    for value in (
        "BATON_RELEASE_DIR",
        "baton-new-project.tar.gz",
        "baton-adoption.tar.gz",
        ".baton/lib/baton_lifecycle.py",
        ".baton/metadata.json",
        'PROJECT_TYPE="software-product"',
        'READINESS_PROTOCOL="Standard Protocol"',
        'CLEARANCE_PROTOCOL="Release Clearance"',
        '--readiness-protocol "$READINESS_PROTOCOL"',
        '--clearance-protocol "$CLEARANCE_PROTOCOL"',
    ):
        require(value in source, f"installer is missing {value}")
    forbidden_prompts = (
        "SELECT PROJECT TYPE",
        "SELECT REASONING",
        "SELECT READINESS PROTOCOL",
        "SELECT CLEARANCE PROTOCOL",
        "SELECT CONSULTANTS",
    )
    require(
        not any(value in source for value in forbidden_prompts)
        and source.count("read -r") == 1,
        "installer still owns post-install Project decisions",
    )
    require("APH_RELEASE_DIR" not in source, "installer retains the obsolete APH release override")
    require("./install.sh status" not in source, "installer advertises a root installed lifecycle command")
    require(
        "After installation, invoke `$boot`" in source
        and ".baton/bin/baton boot status --json" in source,
        "installer does not distinguish guided Boot from status inspection",
    )


def check_runtime_surface(root: Path) -> None:
    cli = (root / "template/.baton/lib/baton_cli.py").read_text(encoding="utf-8")
    lifecycle = (root / "template/.baton/lib/baton_lifecycle.py").read_text(encoding="utf-8")
    library = root / "template/.baton/lib"
    script = (
        "import argparse,json,sys; "
        f"sys.path.insert(0, {str(library)!r}); "
        "import baton_cli,baton_lifecycle; "
        "p=baton_cli.parser(); "
        "top=next(a for a in p._actions if isinstance(a,argparse._SubParsersAction)); "
        "nested={}; "
        "[(nested.__setitem__(name, sorted(next(a for a in child._actions if isinstance(a,argparse._SubParsersAction)).choices))) for name,child in top.choices.items()]; "
        "control=top.choices['control']; "
        "control_sub=next(a for a in control._actions if isinstance(a,argparse._SubParsersAction)); "
        "memory=control_sub.choices['memory']; "
        "memory_sub=next(a for a in memory._actions if isinstance(a,argparse._SubParsersAction)); "
        "print(json.dumps({'top':sorted(top.choices),'nested':nested,'controlMemory':sorted(memory_sub.choices),'skills':sorted(baton_lifecycle.SKILL_NAMES)}))"
    )
    completed = run(root, [sys.executable, "-c", script])
    require(completed.returncode == 0, "cannot inspect installed CLI: " + completed.stderr.strip())
    surface = json.loads(completed.stdout)
    expected_nested = {
        "boot": ["activate", "catalog", "configure", "initialize", "inspect", "next", "record", "status"],
        "control": ["apply", "check", "memory", "protocols", "show"],
        "roster": ["catalog", "check", "configure", "fire", "hire", "list"],
        "terminal": ["status", "view"],
        "upgrade": ["apply", "status"],
        "doctor": ["check", "recover"],
        "scrap": ["apply", "plan"],
    }
    require(surface["top"] == sorted(MANAGEMENT_COMMANDS), f"installed CLI families differ: {surface['top']}")
    require(surface["nested"] == expected_nested, f"installed CLI operations differ: {surface['nested']}")
    require(
        surface["controlMemory"] == ["inspect", "transact"],
        f"advanced Memory CLI seam differs: {surface['controlMemory']}",
    )
    require(surface["skills"] == sorted(SKILLS), f"lifecycle skill inventory differs: {surface['skills']}")
    require(
        'description="Inspect and manage this Baton control plane."' in cli
        and '"Examples:\\n"' in cli
        and 'print(f"\\nBaton / {surface}"' in cli,
        "installed CLI lacks the restrained human terminal and discoverable examples",
    )
    require(
        'recovery["team"] = capture_internal(root, "harness_team", ["recover"])' in cli
        and 'recovery["memory"] = capture_internal(root, "baton_memory", ["recover"])' in cli,
        "doctor recover does not invoke both recognized transaction recovery paths",
    )
    require(
        all(token not in cli for token in ('add_parser("_state"', 'add_parser("_team"', 'add_parser("_memory"', 'add_parser("_activate"')),
        "installed CLI exposes a private engine",
    )
    require('METADATA_PATH = ".baton/metadata.json"' in lifecycle, "lifecycle metadata is not namespaced")
    require('"schemaVersion": 3' in lifecycle, "lifecycle does not emit metadata schema 3")
    require('"repositoryVersion": None' in lifecycle, "lifecycle derives the Repository version")
    require('"memorySchemaVersion": manifest["memorySchemaVersion"]' in lifecycle, "lifecycle metadata omits the memory schema version")
    require("explicit sequential memory migration" in lifecycle, "memory schema changes do not fail closed")
    require("legacyCleanupCandidates" in lifecycle and "Needs Integration" in lifecycle, "migration preservation/quarantine contract is absent")
    require(
        "def activate_adoption(" in lifecycle
        and re.search(r'boot_activate\.add_argument\(\s*"--from"', cli) is not None,
        "reviewed adoption activation is absent",
    )
    require(
        "skill-discovery collision" in lifecycle
        and "did not guess, replace, or partially install" in lifecycle,
        "short skill discovery does not fail closed atomically",
    )
    scrap = (root / "template/.baton/lib/baton_scrap.py").read_text(encoding="utf-8")
    for token in (
        "planDigest",
        "batonTreeSha256",
        "metadataSha256",
        "mutation_lock(root, \"scrap\")",
        "def _backup(",
        "def _restore(",
        "rollback-incomplete",
        "scrap plan must be stored outside .baton",
    ):
        require(token in scrap, f"scrap transaction contract lacks {token}")
    for relative in (
        "template/.baton/bin/baton",
        "template/.baton/lib/baton_cli.py",
        "template/.baton/lib/baton_lifecycle.py",
        "template/.baton/lib/harness_state.py",
        "template/.baton/lib/harness_team.py",
        "template/.baton/lib/baton_scrap.py",
    ):
        require("dont_write_bytecode = True" in (root / relative).read_text(encoding="utf-8"), f"{relative} does not disable bytecode")


def check_source_config(root: Path) -> None:
    actual = parse_semantic_toml((root / ".codex/config.toml").read_text(encoding="utf-8"))
    require(actual == source_config(), f"source Codex semantic config mismatch: expected {source_config()!r}, got {actual!r}")


def generated_runtime_contract(root: Path) -> Dict[str, Any]:
    library = root / "template/.baton/lib"
    script = (
        "import json,sys; sys.dont_write_bytecode=True; "
        f"sys.path.insert(0, {str(library)!r}); "
        "import baton_lifecycle as lifecycle; import codex_config_contract as config; "
        "print(json.dumps({'config': config.render_codex_config(['management','operations','contractor','internal_audit','consultant_product_designer']), 'skills': list(lifecycle.SKILL_NAMES)}))"
    )
    completed = run(root, [sys.executable, "-c", script])
    require(completed.returncode == 0, f"cannot load consumer lifecycle contract: {completed.stderr.strip()}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise EvaluationFailure(f"consumer lifecycle contract emitted invalid JSON: {error}") from error
    require(isinstance(value, dict), "consumer lifecycle contract is not an object")
    return value


def check_consumer_config(root: Path) -> None:
    contract = generated_runtime_contract(root)
    actual = parse_semantic_toml(contract["config"])
    require(actual == consumer_config(), f"generated Codex semantic config mismatch: expected {consumer_config()!r}, got {actual!r}")


def check_discovery(root: Path) -> None:
    contract = generated_runtime_contract(root)
    require(tuple(contract["skills"]) == SKILLS, f"runtime skill discovery set differs: {contract['skills']!r}")
    visible = candidate_paths(root)
    forbidden = sorted(path for path in visible if path == ".codex/skills" or "/.codex/skills" in path)
    require(not forbidden, f"obsolete .codex/skills paths remain: {forbidden}")
    discovery = root / ".agents/skills"
    actual = sorted(path.name for path in discovery.iterdir()) if discovery.is_dir() else []
    require(actual == sorted(SKILLS), f"source skill links differ: {actual}")
    for name in SKILLS:
        path = discovery / name
        require(path.is_symlink(), f"source discovery path is not a symlink: {path}")
        require(os.readlink(path) == f"../../.baton/skills/{name}", f"source discovery target is wrong: {path}")


def check_integration_allowlist(root: Path) -> None:
    library = root / "template/.baton/lib"
    script = f"""
import json,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0, {str(library)!r})
import baton_lifecycle as module
with tempfile.TemporaryDirectory() as raw:
    base=Path(raw); prepared=base/'prepared'; project=base/'project'
    prepared.mkdir(); project.mkdir()
    managed,generated,manual=module.integration_plan(prepared,project,'Installed',['management','operations','contractor','internal_audit','consultant_product_designer'],{{'supportedUpgradeOrigins': {{}}}})
    print(json.dumps({{'managed': managed, 'generated': generated, 'manual': manual}}))
"""
    completed = run(root, [sys.executable, "-c", script])
    require(completed.returncode == 0, f"cannot inspect integration plan: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    expected = {"AGENTS.md", ".codex/config.toml", *(f".agents/skills/{name}" for name in SKILLS)}
    require(set(payload["managed"]) == expected, f"consumer integration writes exceed the allowlist: {payload['managed']!r}")
    require(payload["generated"] == [], f"empty project integration unexpectedly generates collision artifacts: {payload['generated']!r}")
    require(payload["manual"] == [], f"empty project integration unexpectedly needs manual actions: {payload['manual']!r}")


def check_consumer_state(root: Path) -> None:
    library = root / "template/.baton/lib"
    template = root / "template/.baton"
    script = f"""
import json,os,shutil,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
with tempfile.TemporaryDirectory() as raw:
    project=Path(raw)/'project'; baton=project/'.baton'
    shutil.copytree({str(template)!r},baton)
    os.environ['BATON_PROJECT_ROOT']=str(project)
    sys.path.insert(0,{str(library)!r})
    from baton_lifecycle import configure_new_project
    configure_new_project(
        project,
        project_name='Baton starter',
        project_type='software-product',
        readiness_protocol='Standard Protocol',
        clearance_protocol='Release Clearance',
        reasoning={{
            'management':'inherit','operations':'inherit','consultants':'inherit',
            'contractors':'inherit','internalAudit':'inherit',
        }},
        selected_consultants=[],
    )
    required=(
        '.baton/state/team.json','.baton/views/dashboard.html',
        '.baton/views/team-tasks.md','.baton/records',
    )
    missing=[relative for relative in required if not (project/relative).exists()]
    print(json.dumps({{'missing':missing}}))
"""
    completed = run(root, [sys.executable, "-c", script])
    require(
        completed.returncode == 0,
        "consumer starter state/team check failed: "
        + (completed.stdout + completed.stderr).strip(),
    )
    result = json.loads(completed.stdout)
    require(not result["missing"], f"consumer starter is incomplete: {result['missing']}")


def check_bootstrap_memory_integration(root: Path) -> None:
    memory = (root / "template/.baton/lib/baton_memory.py").read_text(
        encoding="utf-8"
    )
    memory_schema = (
        root / "template/.baton/schemas/memory.schema.json"
    ).read_text(encoding="utf-8")
    project_schema = (
        root / "template/.baton/schemas/project.schema.json"
    ).read_text(encoding="utf-8")
    state = (root / "template/.baton/lib/harness_state.py").read_text(
        encoding="utf-8"
    )
    team = (root / "template/.baton/lib/harness_team.py").read_text(
        encoding="utf-8"
    )
    lifecycle = (root / "template/.baton/lib/baton_lifecycle.py").read_text(
        encoding="utf-8"
    )
    bootstrap_skill = (
        root / "template/.baton/skills/boot/SKILL.md"
    ).read_text(encoding="utf-8")
    management_role = (
        root / "template/.baton/roles/management.md"
    ).read_text(encoding="utf-8")
    memory_rule = (
        root / "template/.baton/rules/memory.md"
    ).read_text(encoding="utf-8")
    for token in (
        "def prepare_under_lock(",
        "def render_team_tasks(",
        "def _generated_views(",
        '"after-generated"',
        '"claims": 10, "utf8Bytes": 1800, "estimatedTokens": 600',
    ):
        require(token in memory, f"memory engine lacks {token}")
    require("def load_memory_projection(" in state, "state validation does not load memory")
    require(
        "Company memory" in state,
        "dashboard has no privacy-filtered company memory view",
    )
    require(
        "scoped_record_path(" in state
        and 'name_pattern=r"review-' in state
        and ".baton/records/{scope}" in state
        and "review-packets" not in state,
        "approved clearances do not use flat Goal-or-Ticket record scopes",
    )
    for token in (
        "recentOutcomes",
        "performanceSummaries",
        "sourceLabel",
        "Evidence links",
        "Self Reflection · Unverified",
    ):
        require(token in state, f"dashboard omits personnel evidence surface {token}")
    require(
        "bootstrap roster accepts active Management, Operations, and Consultant seats only"
        in memory,
        "direct bootstrap roster mutation does not enforce permanent active seats",
    )
    require(
        "def _ordered_bootstrap_seats(" in memory
        and '"reconcile-%s" % mode' in memory
        and "bootstrap tasks must be registered and woken in roster order" in memory,
        "post-confirmation bootstrap does not persist and enforce ordered roster registration",
    )
    require(
        "def _bootstrap_next_step(" in memory
        and '"confirm-project-preset"' in memory
        and '"assemble-team"' in memory
        and '"publicStatus"' in memory,
        "bootstrap lacks a deterministic preset and continuation state machine",
    )
    require(
        all(
            token in bootstrap_skill
            for token in (
                "Select the Readiness Protocol",
                "Select the Clearance Protocol",
            )
        )
        and '"readinessProtocol": provisional["readinessProtocol"]' in memory
        and '"clearanceProtocol": provisional["clearanceProtocol"]' in memory,
        "bootstrap does not confirm and promote both protocol defaults",
    )
    require(
        'requested_seats if snapshot["bootstrap"].get("confirmedAt") else []'
        in memory
        and "project intent must be confirmed before team assembly" in memory
        and "def _permanent_task_title(" in memory
        and '"taskTitle": task_title' in memory
        and '"title",\n            "archive",' in memory,
        "bootstrap can create personnel before confirmation or lacks exact task-title planning",
    )
    require(
        '"registered"' in memory_schema
        and '"create-pending"' in memory_schema
        and '"cleanup-required"' in memory_schema
        and '"cleanupTasks"' in memory_schema
        and "native bootstrap registration requires the matching created checkpoint"
        in memory
        and "bootstrap task registration requires exact verified title readback"
        in memory
        and '"status": "registered" if in_bootstrap else "online"' in memory
        and "only a registered bootstrap task can be marked online" in memory
        and "bootstrap onboarding must continue in its original invoking task"
        in memory,
        "bootstrap lacks one-task binding or two-phase title/wake registration",
    )
    require(
        "def _assert_bootstrap_coordinator(" in memory
        and "def _project_intent_complete(" in memory
        and "bootstrap project answers cannot modify control metadata" in memory
        and '"legacy incomplete onboarding requires an explicit reset before restart"'
        in memory
        and "native bootstrap requires a complete live task inventory" in memory
        and "predecessors_ready = all(" in memory
        and "provider_ready = bool(" in memory
        and '"recover-created"' in memory
        and '"cleanup-required"' in memory
        and '"cleanup-complete"' in memory,
        "bootstrap lacks task-bound intent validation or crash-safe task reconciliation",
    )
    require(
        "def _promoted_project_direction(" in memory
        and '".baton/state/project.json": project_after' in memory
        and '"projectAfter": project_after' in memory
        and '"templateMode": False' in memory
        and all(
            '"%s"' % field in project_schema
            for field in (
                "purpose",
                "users",
                "constraints",
                "nonGoals",
                "principles",
                "openQuestions",
            )
        ),
        "confirmed onboarding does not promote complete direction into canonical project state",
    )
    require(
        "def reconfigure_preset(" in team
        and '"reconfigure"' in team
        and '"--invocation-task-id"' in team
        and "project preset reconfiguration requires the original invoking task ID"
        in team
        and "project preset reconfiguration must come from its original invoking task"
        in team
        and "modified generated role config must be reviewed manually" in team,
        "bootstrap cannot bind transactional preset changes to the original task or preserve modified role config",
    )
    require(
        "def _profile_mismatch_fingerprint(" in memory
        and "def _project_preset_ids(" in memory
        and 'action == "profile-mismatch"' in memory
        and "recommended_preset not in listed_presets" in memory
        and 'evidence_basis not in {"explicit-user", "discoverable-project-facts"}'
        in memory
        and '"rejectedProfileMismatchFingerprints"' in memory
        and "fingerprint in rejected_fingerprints" in memory
        and "active profile recommendation must be resolved before another is proposed"
        in memory
        and "profile recommendation was already rejected for unchanged evidence"
        in memory,
        "bootstrap lacks durable evidence-fingerprinted preset mismatch suppression",
    )
    lowered_bootstrap = bootstrap_skill.casefold()
    bootstrap_concepts = {
        "single-conversation confirmation": ("one question at a time", "confirm one plain-language summary"),
        "temporary root boundary": (
            "`root` designation",
            "bootstrap authority only",
            "never becomes management",
        ),
        "accessible presentation": ("decoration", "never carry meaning alone"),
        "honest machine ceremony": (
            "never fabricate progress, confidence, diagnostics, privileges, task identity, or success",
        ),
        "preset mismatch suppression": ("evidence basis", "fingerprint", "rejection"),
        "crash-safe registration": ("persist the creation attempt", "stable id", "verify the exact title"),
        "explicit reset ordering": ("reset-onboarding", "after that transaction commits"),
        "fail-closed fallback": ("create nothing", "copy-ready"),
        "progressive disclosure": ("normal output", "uncreated coworker"),
        "authority relinquishment": ("relinquish `root` authority",),
    }
    for concept, terms in bootstrap_concepts.items():
        require(all(term in lowered_bootstrap for term in terms), f"bootstrap skill omits {concept}")
    bootstrap_sentences = re.split(r"(?<=[.!?])\s+", lowered_bootstrap)
    fabricate_sentences = [sentence for sentence in bootstrap_sentences if "fabricat" in sentence]
    require(
        any("never" in sentence or "not" in sentence for sentence in fabricate_sentences),
        "bootstrap presentation permits fabricated machine state",
    )
    reset_sentences = [
        sentence
        for sentence in bootstrap_sentences
        if "archive superseded" in sentence and "transaction" in sentence
    ]
    require(
        any("after" in sentence and "commit" in sentence for sentence in reset_sentences),
        "bootstrap reset can archive before its state commit",
    )
    require(
        "management joins only after" in management_role.casefold()
        and "does not replay onboarding" in management_role.casefold(),
        "permanent Management still owns pre-provisioning onboarding",
    )
    require(
        'CONTEXT_ROLES = ROLES + ("Internal Audit",)' in memory
        and "Internal Audit context requires an explicit authorized evaluation boundary" in memory
        and 'result["authority"] = "read-only-evaluation"' in memory,
        "Internal Audit lacks a bounded read-only memory context path",
    )
    require(
        "def _initialization_metadata(" in memory
        and '"projectOwnedFiles"' in memory,
        "explicit memory initialization does not classify project-owned files",
    )
    require(
        "def prepare_consultant_memory(" in team,
        "Consultant lifecycle does not preserve personnel history",
    )
    require(
        "generated_team_tasks(" in team,
        "team lifecycle does not reconcile the generated team task view",
    )
    require(
        '".baton/views/team-tasks.md"' in lifecycle
        and "render_team_tasks" in lifecycle,
        "install or activation does not generate the team task view",
    )
    template_memory = json.loads(
        (root / "template/.baton/memory/memory.json").read_text(encoding="utf-8")
    )
    require(
        template_memory.get("revision") == 0
        and template_memory.get("personnel") == []
        and template_memory.get("claims") == []
        and (root / "template/.baton/memory/history.jsonl").read_bytes() == b"",
        "consumer starter memory is not pristine",
    )
    lowered_memory_rule = memory_rule.casefold()
    wake_sentences = [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", lowered_memory_rule)
        if "role wake" in sentence
    ]
    require(
        "memory is internal infrastructure" in lowered_memory_rule
        and "public skills" in lowered_memory_rule
        and "at most 10 claims and 1,800 utf-8 bytes" in lowered_memory_rule
        and any(all(term in sentence for term in ("only", "assignment", "confirmed")) for sentence in wake_sentences),
        "mandatory memory rule lacks deterministic bounded briefing policy",
    )
    behavioral_tests = (
        "tests.test_memory.MemoryTests.test_bootstrap_keeps_one_conversation_until_confirmed_then_titles_the_team",
        "tests.test_memory.MemoryTests.test_project_confirmation_rolls_back_memory_state_and_views_together",
        "tests.test_memory.MemoryTests.test_one_conversation_trace_keeps_the_invoking_task_through_confirmation",
        "tests.test_memory.MemoryTests.test_interrupted_native_create_recovers_or_cleans_up_before_retry",
        "tests.test_memory.MemoryTests.test_bound_onboarding_rejects_every_wrong_task_mutation",
        "tests.test_memory.MemoryTests.test_native_assembly_requires_created_order_and_provider_inventory",
        "tests.test_memory.MemoryTests.test_post_confirmation_task_mutations_remain_bound_to_invoking_task",
        "tests.test_memory.MemoryTests.test_provisional_answers_cannot_overwrite_bootstrap_control_metadata",
        "tests.test_memory.MemoryTests.test_reset_allows_confirmed_incomplete_assembly_but_rejects_complete_team",
        "tests.test_memory.MemoryTests.test_incomplete_intent_and_legacy_unbound_resume_fail_closed",
        "tests.test_memory.MemoryTests.test_preset_selection_does_not_reactivate_a_legacy_consultant_task",
        "tests.test_memory.MemoryTests.test_profile_mismatch_recommendation_is_durable_and_rejection_suppresses_repeats",
        "tests.test_memory.MemoryTests.test_project_preset_catalog_allows_only_the_contained_source_projection_symlink",
        "tests.test_memory.MemoryTests.test_user_can_reset_incomplete_onboarding_without_erasing_company_memory",
    )
    completed = run(
        root,
        [sys.executable, "-m", "unittest", *behavioral_tests],
    )
    require(
        completed.returncode == 0,
        "bootstrap executable behavior contract failed: "
        + (completed.stdout + completed.stderr).strip(),
    )


def check_no_publication(root: Path) -> None:
    paths = [
        root / "scripts/install.sh",
        root / "scripts/release_bundle.py",
        root / "template/.baton/lib/baton_cli.py",
        root / "template/.baton/lib/baton_lifecycle.py",
    ]
    forbidden = ("git push", "git tag", "gh release", "gh pr", "create-release", "upload-release-asset")
    hits: List[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        hits.extend(f"{path.relative_to(root)}:{value}" for value in forbidden if value in text)
    require(not hits, f"candidate contains automatic publication behavior: {hits}")


def check_python_and_cache_hygiene(root: Path) -> None:
    caches = cache_artifacts(root)
    python_files = [root / path for path in candidate_paths(root) if path.endswith(".py")]
    for path in python_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec", dont_inherit=True)
        except (OSError, SyntaxError) as error:
            raise EvaluationFailure(f"{path.relative_to(root)} does not compile: {error}") from error
    python39 = shutil.which("python3.9")
    if python39:
        with tempfile.TemporaryDirectory(prefix="baton-py39-cache-") as cache:
            environment = dict(os.environ)
            environment["PYTHONPYCACHEPREFIX"] = cache
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                [python39, "-m", "py_compile", *(str(path) for path in python_files)],
                cwd=root,
                env=environment,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        require(completed.returncode == 0, f"Python 3.9 compilation failed: {completed.stderr.strip()}")
    require(not caches, f"Python cache artifacts exist: {caches}")


def check_public_docs_inventory(root: Path) -> None:
    public_docs = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "docs").rglob("*")
        if path.is_file() or path.is_symlink()
    )
    expected_docs = sorted((*PUBLIC_DOC_GUIDES, *PUBLIC_DOC_ASSETS))
    require(
        public_docs == expected_docs,
        f"docs is not exclusively the approved public guides and brand assets: {public_docs}",
    )
    for relative in PUBLIC_DOC_ASSETS:
        require(
            (root / relative).read_bytes().startswith(PNG_SIGNATURE),
            f"public brand asset is not a PNG: {relative}",
        )


def check_test_suite(root: Path) -> None:
    expected = {
        "tests/baton_testkit.py",
        "tests/test_release.py",
        "tests/test_lifecycle.py",
        "tests/test_cli.py",
        "tests/test_state_team.py",
        "tests/test_memory.py",
        "tests/test_interactive.py",
        "tests/test_evaluator.py",
        "tests/test_scenario_evaluator.py",
        "tests/run_smokes.py",
        "tests/install_smoke.sh",
        "tests/install_remote_smoke.sh",
        "tests/evals/README.md",
        "tests/evals/operator-prompt.md",
        "tests/evals/judge-prompt.md",
        "tests/evals/rubric.md",
        "tests/evals/report-schema.json",
        "tests/evals/report-template.md",
        "tests/evals/static-checks.md",
        "tests/evals/live-trace-schema.json",
        "scripts/harness_scenario_eval.py",
    }
    missing = sorted(path for path in expected if not (root / path).is_file())
    require(not missing, f"focused Baton smoke suite is incomplete: {missing}")
    check_public_docs_inventory(root)
    obsolete = {
        "tests/harness_lifecycle_smoke.py",
        "tests/harness_state_smoke.py",
        "tests/install_interactive_smoke.py",
        "tests/install_update_smoke.py",
        "tests/release_bundle_smoke.py",
        "tests/status_lifecycle_smoke.py",
        "tests/team_lifecycle_smoke.py",
    }
    present = sorted(path for path in obsolete if (root / path).exists())
    require(not present, f"obsolete template smokes remain: {present}")


def check_contract_coherence(root: Path) -> None:
    """Check ownership and semantic agreement without freezing prose."""
    baton = root / "template/.baton"
    retired_surfaces = {
        "guide.md",
        "docs",
        "decisions",
        "integration",
        "implementation-reports",
        "prds",
        "review-packets",
        "tickets",
        "work",
        "thread-registry.md",
        "dashboard",
        "templates/prd.md",
        "templates/implementation-report.md",
        "templates/review-packet.md",
    }
    present_retired = sorted(
        relative
        for relative in retired_surfaces
        if (baton / relative).exists() or (baton / relative).is_symlink()
    )
    require(not present_retired, f"retired consumer surfaces remain: {present_retired}")
    migration_contract = (baton / "migration/README.md").read_text(
        encoding="utf-8"
    )
    require(
        "not authoritative" in migration_contract
        and "Later Roster changes" in migration_contract
        and "external transaction evidence" in migration_contract,
        "migration workspace is not bounded to adoption",
    )
    template_names = {
        path.name for path in (baton / "templates").iterdir() if path.is_file()
    }
    require(
        template_names == {
            "brief.md",
            "decision.md",
            "report.md",
            "review.md",
            "ticket.operation.json",
        },
        f"Record templates differ: {sorted(template_names)}",
    )
    mandatory_rules = {
        "authority.md",
        "bootstrap.md",
        "delivery.md",
        "design.md",
        "lifecycle.md",
        "memory.md",
        "operations.md",
        "verification.md",
    }
    legacy_rules = {
        "authority-boundaries.md",
        "bootstrap-and-task-registration.md",
        "codebase-design.md",
        "company-memory.md",
        "completion-and-review.md",
        "dispatch-and-ownership.md",
        "external-notifications.md",
        "fast-feedback-development.md",
        "harness-evaluation.md",
        "incoming-change-triage.md",
        "lifecycle-and-idle.md",
        "llm-first-operability.md",
        "readiness-and-scope.md",
        "repository-safety.md",
        "repository-truth.md",
        "risk-based-findings.md",
        "testing.md",
        "transactional-state.md",
    }

    actual_rules = {path.name for path in (baton / "rules").glob("*.md")}
    require(actual_rules == mandatory_rules, f"mandatory rule set differs: {sorted(actual_rules)}")
    rule_words = sum(len(path.read_text(encoding="utf-8").split()) for path in (baton / "rules").glob("*.md"))
    require(1800 <= rule_words <= 3500, f"mandatory rules exceed the concise contract budget: {rule_words}")

    agents = (baton / "AGENTS.md").read_text(encoding="utf-8")
    require(not (baton / "skills-README.md").exists(), "standalone skill catalog duplicates the agent map")
    require(
        ".baton/records/<SCOPE>/" in agents
        and "(records/README.md)" in agents
        and "views/team-tasks.md" in agents,
        "agent map does not route scoped records and generated task views",
    )
    records_contract = (baton / "records/README.md").read_text(encoding="utf-8")
    require(
        all(
            token in records_contract
            for token in (
                ".baton/records/PROJECT/",
                ".baton/records/<GOAL-ID>/",
                ".baton/records/<TICKET-ID>/",
                "brief.md",
                "decision-<slug>.md",
                "report.md",
                "review-<stage>-<reviewer>.md",
                ".baton/state/",
            )
        ),
        "records README does not define the Project-, Goal-, and Ticket-scoped record contract",
    )
    project_template = read_json(baton / "state/project.json")["project"]
    require(
        all(
            field in project_template
            for field in (
                "purpose",
                "users",
                "constraints",
                "nonGoals",
                "principles",
                "openQuestions",
            )
        ),
        "canonical project starter omits approved direction fields",
    )
    require(
        project_template.get("assuranceDefaults")
        == {
            "readinessProtocol": "Standard Protocol",
            "clearanceProtocol": "Release Clearance",
        },
        "canonical project starter does not use the approved protocol defaults",
    )
    project_schema = read_json(baton / "schemas/project.schema.json")
    provider_contract = project_schema["properties"]["project"]["properties"][
        "agentProvider"
    ]
    require(
        provider_contract.get("type") == "string"
        and provider_contract.get("minLength") == 1
        and "const" not in provider_contract,
        "canonical project state locks Baton to one agent provider",
    )
    language = (baton / "language.md").read_text(encoding="utf-8")
    required_terms = {
        "Project",
        "Repository",
        "State",
        "Record",
        "Goal",
        "Ticket",
        "Brief",
        "Decision",
        "Report",
        "Evidence",
        "Review",
        "Readiness Protocol",
        "Clearance Protocol",
        "Release",
        "Publication",
        "Memory",
    }
    defined_terms = re.findall(r"^- \*\*([^*]+)\*\* — ", language, re.MULTILINE)
    require(
        set(defined_terms) == required_terms
        and len(defined_terms) == len(set(defined_terms)),
        "ubiquitous language is incomplete or defines a term more than once",
    )
    require(
        "(language.md)" in agents and "(workflow.md)" in agents,
        "agent map does not route language and workflow",
    )
    linked_rules = re.findall(r"\(rules/([^)]+\.md)\)", agents)
    require(set(linked_rules) == mandatory_rules, f"agent map and mandatory rules disagree: {linked_rules}")
    require(len(linked_rules) == len(set(linked_rules)), "agent map links a mandatory rule more than once")
    require(
        re.search(r"read every file.*mandatory rules", agents, re.IGNORECASE | re.DOTALL) is not None,
        "agent map does not make the complete rule set mandatory",
    )
    startup_markers = (
        "Read every file",
        "Validate Baton",
        "controlling Goal and Ticket records",
        "assigned role contract",
        "invoked skill",
        "bounded company memory",
    )
    positions = [agents.find(marker) for marker in startup_markers]
    require(all(position >= 0 for position in positions) and positions == sorted(positions), "agent startup order is incomplete or contradictory")

    role_files = {path.name for path in (baton / "roles").glob("*.md") if path.name != "contractor-assignment-template.md"}
    linked_roles = set(re.findall(r"\(roles/([^)]+\.md)\)", agents))
    require(linked_roles == role_files, f"agent role map differs from role contracts: {sorted(linked_roles)}")

    skill_files = sorted((baton / "skills").glob("*/SKILL.md"))
    skill_names = set()
    for path in skill_files:
        match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)
        require(match is not None and match.group(1) == path.parent.name, f"skill identity differs: {path}")
        skill_names.add(path.parent.name)
    require(skill_names == set(SKILLS), f"runtime and Markdown skill inventories differ: {sorted(skill_names)}")
    linked_skills = re.findall(r"\(skills/([^/]+)/SKILL\.md\)", agents)
    require(set(linked_skills) == skill_names, f"agent map and invoked skills disagree: {linked_skills}")
    require(len(linked_skills) == len(set(linked_skills)), "agent map links an invoked skill more than once")
    skill_catalog = read_json(baton / "skills.json")
    require(
        set(skill_catalog.get("skills", [])) == skill_names
        and len(skill_catalog.get("skills", [])) == len(skill_names),
        "skill catalog and invoked skill sources disagree",
    )
    retired_management_skills = {
        "bootstrap-baton",
        "hire-consultant",
        "fire-consultant",
        "memory",
    }
    present_retired_skills = sorted(
        name for name in retired_management_skills if (baton / "skills" / name).exists()
    )
    require(not present_retired_skills, f"retired management skills remain: {present_retired_skills}")
    private_cli_tokens = ("_state", "_team", "_memory", "_activate")
    for command in MANAGEMENT_COMMANDS:
        source = (baton / "skills" / command / "SKILL.md").read_text(encoding="utf-8")
        routed = re.findall(r"\.baton/bin/baton\s+([a-z0-9-]+)", source)
        require(
            routed == [command] and all(token not in source for token in private_cli_tokens),
            f"{command} skill does not delegate exclusively to its matching public CLI family",
        )
    memory_rule = (baton / "rules/memory.md").read_text(encoding="utf-8")
    require(
        "Memory is internal infrastructure" in memory_rule
        and "$memory" not in memory_rule
        and "matching CLI command family" in memory_rule,
        "Memory is exposed as a parallel management surface",
    )
    team_source = (baton / "lib/harness_team.py").read_text(encoding="utf-8")
    require(
        'CODEX_PROPOSAL_ARTIFACT = "proposals/codex-config.toml"' in team_source
        and "external_writes=codex_external" in team_source
        and "def external_codex_proposal(" in team_source
        and ".baton/migration/codex-config.{transaction_id}" not in team_source,
        "Roster config collisions do not use external transaction evidence",
    )
    control_skill = (baton / "skills/control/SKILL.md").read_text(encoding="utf-8")
    public_cli = (baton / "lib/baton_cli.py").read_text(encoding="utf-8")
    require(
        "control memory" not in control_skill.casefold()
        and "memory" not in skill_names
        and re.search(r'command_parser\(\s*control_memory_commands,\s*"inspect"', public_cli)
        is not None
        and re.search(r'command_parser\(\s*control_memory_commands,\s*"transact"', public_cli)
        is not None,
        "advanced Memory access is missing or advertised as a normal skill",
    )

    markdown_files = sorted(baton.rglob("*.md"))
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        provider = re.search(r"\b(?:Codex|Claude|Gemini)\b", content, re.IGNORECASE)
        require(provider is None, f"consumer contract leaks a provider name: {path.relative_to(root)}")
        for legacy in legacy_rules:
            require(legacy not in content, f"consumer Markdown links a retired rule {legacy}: {path.relative_to(root)}")
        for raw_target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue
            require((path.parent / target).exists(), f"broken Markdown link in {path.relative_to(root)}: {raw_target}")

    seen_paragraphs: Dict[str, Path] = {}
    for path in markdown_files:
        for paragraph in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            if not lines or any(
                line.startswith(("---", "#", "|", "- ", "* ", "```"))
                or re.match(r"^[0-9]+[.)]\s", line)
                for line in lines
            ):
                continue
            words = re.findall(r"[a-z0-9]+", " ".join(lines).casefold())
            if len(words) < 24:
                continue
            normalized = " ".join(words)
            previous = seen_paragraphs.get(normalized)
            if previous is not None and previous != path:
                raise EvaluationFailure(
                    f"duplicated contract paragraph: {previous.relative_to(root)} and {path.relative_to(root)}"
                )
            seen_paragraphs[normalized] = path

    workflow = (baton / "workflow.md").read_text(encoding="utf-8")
    require(
        "(language.md)" in workflow and "## Ubiquitous language" not in workflow,
        "workflow duplicates or fails to route the ubiquitous language",
    )

    goal_schema = read_json(baton / "schemas/goals.schema.json")
    ticket_schema = read_json(baton / "schemas/tickets.schema.json")
    project_properties = project_schema["properties"]["project"]["properties"]
    goal_properties = goal_schema["properties"]["goals"]["items"]["properties"]
    ticket_properties = ticket_schema["properties"]["tickets"]["items"]["properties"]
    require(
        {"decisionPaths", "evidencePaths"} <= set(project_properties)
        and "briefPath" not in project_properties
        and "reportPath" not in project_properties,
        "Project record links contradict the scoped-record contract",
    )
    scope_fields = {"briefPath", "decisionPaths", "reportPath", "evidencePaths"}
    require(
        scope_fields <= set(goal_properties)
        and scope_fields <= set(ticket_properties)
        and "narrativePath" not in goal_properties
        and "narrativePath" not in ticket_properties,
        "Goal and Ticket record links contradict the scoped-record contract",
    )
    require(
        goal_properties["id"].get("not", {}).get("const") == "PROJECT"
        and ticket_properties["id"].get("not", {}).get("const") == "PROJECT",
        "canonical ids do not reserve the PROJECT record scope",
    )

    def enum(schema_name: str, *keys: str) -> set[str]:
        value: Any = read_json(baton / f"schemas/{schema_name}.schema.json")
        for key in keys:
            value = value[key]
        require(isinstance(value, list) and all(isinstance(item, str) for item in value), f"schema enum is invalid: {schema_name} {keys}")
        return set(value)

    ticket_block = workflow.split("## Ticket states", 1)[1].split("## Goal states", 1)[0]
    goal_block = workflow.split("## Goal states", 1)[1].split("## Priority and protocols", 1)[0]
    assurance_block = workflow.split("## Priority and protocols", 1)[1].split("## Transition path", 1)[0]
    ticket_states = set(re.findall(r"^\| `([^`]+)` \|", ticket_block, re.MULTILINE))
    goal_declaration = re.search(r"Goals use ([^.]+)\.", goal_block)
    require(goal_declaration is not None, "workflow does not declare goal states")
    goal_states = set(re.findall(r"`([^`]+)`", goal_declaration.group(1)))
    assurance_values = set(re.findall(r"`([^`]+)`", assurance_block))
    require(ticket_states == enum("tickets", "properties", "tickets", "items", "properties", "status", "enum"), "workflow ticket states contradict the schema")
    require(goal_states == enum("goals", "properties", "goals", "items", "properties", "status", "enum"), "workflow goal states contradict the schema")
    require(enum("tickets", "properties", "tickets", "items", "properties", "priority", "enum") <= assurance_values, "workflow priorities contradict the schema")
    require(enum("tickets", "properties", "tickets", "items", "properties", "assurance", "properties", "readinessProtocol", "enum") <= assurance_values, "workflow Readiness Protocol levels contradict the schema")
    ticket_clearance = enum("tickets", "properties", "tickets", "items", "properties", "assurance", "properties", "clearanceProtocol", "enum")
    goal_clearance = enum("goals", "properties", "goals", "items", "properties", "assurance", "properties", "clearanceProtocol", "enum")
    require(ticket_clearance == goal_clearance and ticket_clearance <= assurance_values, "workflow Goal and Ticket Clearance Protocol levels contradict the schemas")
    transition = re.search(r"Work moves through `([^`]+)`", agents)
    require(transition is not None, "agent map omits the primary ticket path")
    primary_path = [state.strip() for state in transition.group(1).split("->")]
    require(
        len(primary_path) == len(set(primary_path))
        and set(primary_path) <= ticket_states
        and {"Ready", "In Progress", "In Review"} <= set(primary_path)
        and primary_path[0] == "Backlog"
        and primary_path[-1] == "Done"
        and primary_path.index("Ready") < primary_path.index("In Progress") < primary_path.index("In Review"),
        "agent map primary ticket path contradicts the workflow",
    )

    team_source = (baton / "lib/harness_team.py").read_text(encoding="utf-8")
    require("every applicable .baton/rules" not in team_source, "generated role config still selects only applicable rules")
    require(team_source.count("every mandatory rule") >= 5, "generated role configs do not route every role through all mandatory rules")

    verification = (baton / "rules/verification.md").read_text(encoding="utf-8").casefold()
    review = (baton / "skills/code-review/SKILL.md").read_text(encoding="utf-8").casefold()
    shared_concepts = {
        "incremental feedback": ("increment", "seam"),
        "validator control": ("known-bad", "known-good"),
        "bounded retry": ("retry-until-green",),
        "evidence identity": ("fingerprint", "invalidation"),
        "blocking threshold": ("p0", "p1", "confirmed", "proven"),
    }
    for concept, terms in shared_concepts.items():
        require(all(term in verification for term in terms), f"verification rule omits {concept}")
        require(all(term in review for term in terms), f"code review disagrees on {concept}")

    rubric = (root / "tests/evals/rubric.md").read_text(encoding="utf-8")
    require(all(gate in rubric for gate in ("HG-11", "HG-13", "HG-14")), "evaluation rubric omits bounded-iteration hard gates")
    for relative in (
        "tests/evals/scenarios/inputs/H-014.md",
        "tests/evals/scenarios/oracles/H-014.md",
        "tests/evals/scenarios/inputs/H-015.md",
        "tests/evals/scenarios/oracles/H-015.md",
        "tests/evals/scenarios/inputs/H-016.md",
        "tests/evals/scenarios/oracles/H-016.md",
    ):
        require((root / relative).is_file(), f"bounded verification scenario is missing: {relative}")
    for scenario_id in ("H-014", "H-015", "H-016"):
        relative = f"tests/evals/scenarios/contracts/{scenario_id}.json"
        require((root / relative).is_file(), f"scenario contract is missing: {relative}")
        contract = read_json(root / relative)
        require(contract.get("scenarioId") == scenario_id, f"scenario contract identity differs: {relative}")
        assertions = contract.get("assertions")
        require(isinstance(assertions, list) and assertions, f"scenario contract has no assertions: {relative}")


def check_executable_scenario_evaluation(root: Path) -> None:
    required = (
        "scripts/harness_scenario_eval.py",
        "tests/test_scenario_evaluator.py",
        "tests/evals/live-trace-schema.json",
        "tests/evals/scenarios/contracts/H-014.json",
        "tests/evals/scenarios/contracts/H-015.json",
        "tests/evals/scenarios/contracts/H-016.json",
    )
    missing = sorted(relative for relative in required if not (root / relative).is_file())
    require(not missing, f"executable scenario evaluation is incomplete: {missing}")

    runner = (root / "scripts/harness_scenario_eval.py").read_text(encoding="utf-8")
    for token in (
        "def run_scenario_once(",
        "def audit_live_trace(",
        '"privateMachineContract"',
        '"HG-13"',
        '"HG-14"',
        "A long assembled or human gate was used as the primary iteration loop",
        "Equivalent successful certification was repeated",
        "Certification evidence was reused with incomplete or invalidated",
    ):
        require(token in runner, f"scenario runner lacks executable mitigation: {token}")

    operator = (root / "tests/evals/operator-prompt.md").read_text(encoding="utf-8")
    judge = (root / "tests/evals/judge-prompt.md").read_text(encoding="utf-8")
    readme = (root / "tests/evals/README.md").read_text(encoding="utf-8")
    tests = (root / "tests/test_scenario_evaluator.py").read_text(encoding="utf-8")
    require("policy_evidence" in operator and "primary_debugging_loop" in operator, "candidate contract lacks structured testing evidence")
    require("private machine contract" in judge and "cannot turn a contract failure into a pass" in judge, "judge does not fail closed on private contracts")
    require("scripts/harness_scenario_eval.py scenario" in readme and "live-trace --trace" in readme, "executable scenario commands are undocumented")
    for token in (
        "test_private_contract_overrides_a_permissive_judge",
        "test_live_trace_rejects_expensive_primary_iteration",
        "test_live_trace_rejects_duplicate_or_stale_certification",
        "test_live_trace_requires_gate_duration",
    ):
        require(token in tests, f"scenario evaluator lacks negative regression: {token}")

    schema = read_json(root / "tests/evals/live-trace-schema.json")
    require(schema.get("type") == "object" and "events" in schema.get("properties", {}), "live trace schema lacks its event contract")


CHECKS: Sequence[Tuple[str, str, Callable[[Path], None]]] = (
    ("BT-001", "Baton v0.6.0 version", check_version),
    ("BT-002", "source repository identity", check_source_identity),
    ("BT-003", "isolated consumer source tree", check_consumer_layout),
    ("BT-004", "fail-closed template boundary", check_template_boundary),
    ("BT-005", "dual payload projection", check_payload_projection),
    ("BT-006", "release artifact contract", check_release_contract),
    ("BT-007", "stable installer surface", check_installer_surface),
    ("BT-008", "installed lifecycle surface", check_runtime_surface),
    ("BT-009", "source host-adapter semantics", check_source_config),
    ("BT-010", "consumer host-adapter semantics", check_consumer_config),
    ("BT-011", "single-source skill discovery", check_discovery),
    ("BT-012", "consumer path allowlist", check_integration_allowlist),
    ("BT-013", "consumer starter state and team validity", check_consumer_state),
    ("BT-014", "no automatic publication", check_no_publication),
    ("BT-015", "Python compatibility and cache hygiene", check_python_and_cache_hygiene),
    ("BT-016", "focused Baton smoke inventory", check_test_suite),
    ("BT-017", "bootstrap and company-memory integration", check_bootstrap_memory_integration),
    ("BT-018", "concise semantic contract coherence", check_contract_coherence),
    ("BT-019", "executable iteration and evidence evaluation", check_executable_scenario_evaluation),
)


def evaluate(root: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for identifier, title, function in CHECKS:
        try:
            function(root)
        except (EvaluationFailure, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            results.append({"id": identifier, "title": title, "ok": False, "error": str(error)})
        else:
            results.append({"id": identifier, "title": title, "ok": True})
    return results


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    result.add_argument("--json", action="store_true")
    result.add_argument(
        "--strict",
        action="store_true",
        help="run the fail-closed source contract (the default; retained as the documented explicit mode)",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    results = evaluate(root)
    passed = sum(1 for item in results if item["ok"])
    payload = {
        "ok": passed == len(results),
        "strict": args.strict,
        "version": VERSION,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for item in results:
            if item["ok"]:
                print(f"PASS {item['id']} {item['title']}")
            else:
                print(f"FAIL {item['id']} {item['title']}: {item['error']}")
        print(f"{'PASS' if payload['ok'] else 'FAIL'}: {passed}/{len(results)} Baton v{VERSION} source checks passed")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
