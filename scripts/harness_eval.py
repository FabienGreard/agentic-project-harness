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
ADOPTION_ONLY_PATH = "template/.baton/integration/README.md"
STARTER_PATH = "template/.baton/thread-registry.md"
STARTER_PREFIXES = (
    "template/.baton/state/",
    "template/.baton/dashboard/",
    "template/.baton/docs/",
    "template/.baton/decisions/",
    "template/.baton/implementation-reports/",
    "template/.baton/prds/",
    "template/.baton/review-packets/",
    "template/.baton/tickets/",
)
SKILLS = (
    "brainstorm",
    "code-review",
    "fire-consultant",
    "hire-consultant",
    "improve-codebase-architecture",
)
CACHE_SCAN_SCOPES = (
    ".baton",
    "template/.baton",
    "scripts",
    "tests",
)
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
    require(STARTER_PATH in template_paths, f"starter source is missing: {STARTER_PATH}")
    return sorted(template_paths)


def projection_for(source_path: str) -> str:
    require(source_path.startswith(TEMPLATE_PREFIX), f"consumer source is outside template/.baton: {source_path}")
    if source_path == ADOPTION_ONLY_PATH:
        return "adoption-only"
    if source_path == STARTER_PATH or source_path.startswith(STARTER_PREFIXES):
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
        return ".baton/integration/starter/" + relative.removeprefix(".baton/")
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
    require((root / "VERSION").read_text(encoding="utf-8") == VERSION + "\n", "VERSION is not exactly 0.6.0")


def check_source_identity(root: Path) -> None:
    root_agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    require("<!-- BATON:START -->" in root_agents and ".baton/AGENTS.md" in root_agents, "root AGENTS.md does not expose Baton discovery")
    metadata = read_json(root / ".baton/metadata.json")
    require(metadata.get("schemaVersion") == 3, "source metadata schema is not 3")
    require(metadata.get("batonVersion") == VERSION, "source metadata Baton version differs from VERSION")
    require(metadata.get("installationStatus") == "Source Repository", "root .baton is not source-only state")
    require(metadata.get("projectVersion") is None, "source metadata must not derive projectVersion from VERSION")
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
        ".baton/integration/README.md",
        ".baton/lib/baton_cli.py",
        ".baton/lib/baton_lifecycle.py",
        ".baton/lib/harness_state.py",
        ".baton/lib/harness_team.py",
        ".baton/state/project.json",
        ".baton/team-presets.json",
    }
    missing = sorted(required - set(paths))
    require(not missing, f"consumer source is incomplete: {missing}")
    require(".baton/metadata.json" not in paths, "consumer source contains release-specific metadata")


def check_template_boundary(root: Path) -> None:
    sources = template_sources(root)
    require(all(path.startswith(TEMPLATE_PREFIX) for path in sources), "consumer source escaped template/.baton")
    require(not (root / "scripts/source-classification.json").exists(), "obsolete source-classification inventory remains")
    require(projection_for(ADOPTION_ONLY_PATH) == "adoption-only", "adoption-only projection is not explicit")
    require(projection_for(STARTER_PATH) == "starter", "starter projection is not explicit")


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
    require(not any(path.startswith(".baton/integration/starter/") for path in projected["new-project"]), "new-project payload contains quarantined starter paths")
    require(any(path.startswith(".baton/integration/starter/state/") for path in projected["adoption"]), "adoption payload does not quarantine starter state")
    require(".baton/state/project.json" in projected["new-project"], "new-project payload lacks canonical starter state")
    require(".baton/state/project.json" not in projected["adoption"], "adoption payload activates starter state")
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
    for value in ("BATON_RELEASE_DIR", "baton-new-project.tar.gz", "baton-adoption.tar.gz", ".baton/lib/baton_lifecycle.py", ".baton/metadata.json"):
        require(value in source, f"installer is missing {value}")
    require("APH_RELEASE_DIR" not in source, "installer retains the obsolete APH release override")
    require("./install.sh status" not in source, "installer advertises a root installed lifecycle command")


def check_runtime_surface(root: Path) -> None:
    cli = (root / "template/.baton/lib/baton_cli.py").read_text(encoding="utf-8")
    lifecycle = (root / "template/.baton/lib/baton_lifecycle.py").read_text(encoding="utf-8")
    for command in ('add_parser("status"', 'add_parser("update"', 'add_parser("check"', 'add_parser("_activate"'):
        require(command in cli, f"installed Baton CLI lacks {command}")
    require('METADATA_PATH = ".baton/metadata.json"' in lifecycle, "lifecycle metadata is not namespaced")
    require('"schemaVersion": 3' in lifecycle, "lifecycle does not emit metadata schema 3")
    require('"projectVersion": None' in lifecycle, "lifecycle derives the project version")
    require("legacyCleanupCandidates" in lifecycle and "Needs Integration" in lifecycle, "migration preservation/quarantine contract is absent")
    require("def activate_adoption(" in lifecycle and 'activate.add_argument("--from"' in lifecycle, "reviewed adoption activation is absent")
    for relative in (
        "template/.baton/bin/baton",
        "template/.baton/lib/baton_cli.py",
        "template/.baton/lib/baton_lifecycle.py",
        "template/.baton/lib/harness_state.py",
        "template/.baton/lib/harness_team.py",
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
    managed,generated,manual=module.integration_plan(prepared,project,'Installed',['management','operations','contractor','internal_audit','consultant_product_designer'])
    print(json.dumps({{'managed': managed, 'generated': generated, 'manual': manual}}))
"""
    completed = run(root, [sys.executable, "-c", script])
    require(completed.returncode == 0, f"cannot inspect integration plan: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    expected = {"AGENTS.md", ".codex/config.toml", *(f".agents/skills/{name}" for name in SKILLS)}
    require(set(payload["managed"]) == expected, f"consumer integration writes exceed the allowlist: {payload['managed']!r}")
    require(payload["generated"] == [], f"empty project integration unexpectedly generates collision artifacts: {payload['generated']!r}")
    require(payload["manual"] == [], f"empty project integration unexpectedly needs manual actions: {payload['manual']!r}")


def check_source_state(root: Path) -> None:
    completed = run(root, [str(root / ".baton/bin/baton"), "check", "--json"])
    require(completed.returncode == 0, f"source state/team check failed: {completed.stdout}{completed.stderr}")


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


def check_test_suite(root: Path) -> None:
    expected = {
        "tests/baton_testkit.py",
        "tests/test_release.py",
        "tests/test_lifecycle.py",
        "tests/test_state_team.py",
        "tests/test_interactive.py",
        "tests/test_evaluator.py",
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
    }
    missing = sorted(path for path in expected if not (root / path).is_file())
    require(not missing, f"focused Baton smoke suite is incomplete: {missing}")
    public_docs = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "docs").rglob("*")
        if path.is_file() or path.is_symlink()
    )
    expected_docs = [
        "docs/architecture.md",
        "docs/customization.md",
        "docs/getting-started.md",
        "docs/installation.md",
        "docs/releasing.md",
    ]
    require(public_docs == expected_docs, f"docs is not exclusively public product documentation: {public_docs}")
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


CHECKS: Sequence[Tuple[str, str, Callable[[Path], None]]] = (
    ("BT-001", "Baton v0.6.0 version", check_version),
    ("BT-002", "source repository identity", check_source_identity),
    ("BT-003", "isolated consumer source tree", check_consumer_layout),
    ("BT-004", "fail-closed template boundary", check_template_boundary),
    ("BT-005", "dual payload projection", check_payload_projection),
    ("BT-006", "release artifact contract", check_release_contract),
    ("BT-007", "stable installer surface", check_installer_surface),
    ("BT-008", "installed lifecycle surface", check_runtime_surface),
    ("BT-009", "source Codex semantics", check_source_config),
    ("BT-010", "consumer Codex semantics", check_consumer_config),
    ("BT-011", "skill discovery without .codex/skills", check_discovery),
    ("BT-012", "consumer path allowlist", check_integration_allowlist),
    ("BT-013", "source state and team validity", check_source_state),
    ("BT-014", "no automatic publication", check_no_publication),
    ("BT-015", "Python compatibility and cache hygiene", check_python_and_cache_hygiene),
    ("BT-016", "focused Baton smoke inventory", check_test_suite),
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
