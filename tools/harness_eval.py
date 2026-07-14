#!/usr/bin/env python3
"""Dependency-free, read-only static checks for Agentic Project Harness."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True

from codex_config_contract import assert_codex_config


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STATUSES = {
    "Assigned",
    "Building",
    "Blocked",
    "Integrating",
    "Verifying",
    "Awaiting Review",
}
OWNERSHIP_TICKET_STATUS = {
    "Assigned": "In Progress",
    "Building": "In Progress",
    "Blocked": "Blocked",
    "Integrating": "In Progress",
    "Verifying": "In Progress",
    "Awaiting Review": "In Review",
}
REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    ".agent-harness.json",
    ".codex/config.toml",
    ".codex/agents/management.toml",
    ".codex/agents/operations.toml",
    ".codex/agents/contractor.toml",
    ".codex/agents/internal-audit.toml",
    "install.sh",
    "tests/install_smoke.sh",
    "tests/install_remote_smoke.sh",
    "tests/harness_lifecycle_smoke.py",
    "tests/install_update_smoke.py",
    "tests/harness_state_smoke.py",
    "tests/release_bundle_smoke.py",
    "tools/codex_config_contract.py",
    "tools/harness_lifecycle.py",
    "tools/harness_lock.py",
    "tools/harness_state.py",
    "tools/harness_team.py",
    "tools/json_schema_contract.py",
    "tools/team-presets.json",
    "tools/release_bundle.py",
    "docs/installation.md",
    "docs/releasing.md",
    "docs/overview.md",
    "docs/direction.md",
    "docs/index.html",
    "docs/state/project.json",
    "docs/state/goals.json",
    "docs/state/tickets.json",
    "docs/state/ownership.json",
    "docs/state/reviews.json",
    "docs/state/team.json",
    "docs/schemas/project.schema.json",
    "docs/schemas/goals.schema.json",
    "docs/schemas/tickets.schema.json",
    "docs/schemas/ownership.schema.json",
    "docs/schemas/reviews.schema.json",
    "docs/schemas/operation.schema.json",
    "docs/schemas/consultant.schema.json",
    "docs/schemas/team.schema.json",
    "docs/workflow.md",
    "docs/thread-registry.md",
    "docs/roles/management.md",
    "docs/roles/operations.md",
    "docs/roles/consultant.md",
    "docs/roles/contractor.md",
    "docs/roles/internal-audit.md",
    "docs/roles/contractor-assignment-template.md",
    "docs/decisions/ADR-0001-task-message-wake-only.md",
    "docs/evals/harness/rubric.md",
    "docs/evals/harness/scenarios/inputs/H-011.md",
    "docs/evals/harness/scenarios/oracles/H-011.md",
    "docs/evals/harness/scenarios/inputs/H-012.md",
    "docs/evals/harness/scenarios/oracles/H-012.md",
    "docs/evals/harness/scenarios/inputs/H-013.md",
    "docs/evals/harness/scenarios/oracles/H-013.md",
]
REQUIRED_SKILLS = (
    "brainstorm",
    "improve-codebase-architecture",
    "code-review",
    "hire-consultant",
    "fire-consultant",
)
REQUIRED_RULES = (
    "repository-truth",
    "authority-boundaries",
    "lifecycle-and-idle",
    "incoming-change-triage",
    "codebase-design",
    "testing",
    "risk-based-findings",
    "dispatch-and-ownership",
    "transactional-state",
    "readiness-and-scope",
    "completion-and-review",
    "harness-evaluation",
    "external-notifications",
    "repository-safety",
    "llm-first-operability",
)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERNS = [
    re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def repository_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    candidate = ROOT.joinpath(*path.parts)
    parent = candidate.parent.resolve(strict=False)
    root = ROOT.resolve()
    if parent != root and root not in parent.parents:
        return None
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        return None
    return candidate


@dataclass
class Finding:
    check: str
    ok: bool
    evidence: str


class Evaluator:
    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.findings: list[Finding] = []
        self.state: dict = {}
        self.metadata: dict = {}

    def record(self, check: str, ok: bool, evidence: str) -> None:
        self.findings.append(Finding(check, ok, evidence))

    def run(self) -> None:
        self.required_files()
        self.markdown_links()
        self.json_files()
        self.team_contract()
        self.codex_agent_configs()
        self.text_integrity()
        self.governance_modules()
        self.skill_discovery()
        self.role_integration()
        self.permanent_task_lifecycle()
        self.lifecycle_contract()
        self.state_contract()
        self.assurance_contract()
        self.risk_based_review_contract()
        if self.state:
            self.goal_state()
            self.ticket_state()
            self.ownership_and_baton()
            self.template_hygiene()
            self.provider_consistency()
        self.secret_hygiene()

    def required_files(self) -> None:
        missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
        self.record("ST-001", not missing, "missing: " + ", ".join(missing) if missing else f"{len(REQUIRED_FILES)} required files present")

    def markdown_links(self) -> None:
        broken: list[str] = []
        files = list(ROOT.rglob("*.md"))
        for file in files:
            if ".git" in file.parts or ".artifacts" in file.parts:
                continue
            text = file.read_text(encoding="utf-8")
            for raw_target in LINK_RE.findall(text):
                target = raw_target.strip().strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "#", "thread:", "plugin:")):
                    continue
                path_part = unquote(target.split("#", 1)[0])
                if not path_part:
                    continue
                candidate = (file.parent / path_part).resolve()
                if not candidate.exists():
                    broken.append(f"{file.relative_to(ROOT)} -> {target}")
        self.record("ST-002", not broken, "; ".join(broken[:20]) if broken else f"{len(files)} Markdown files checked")

    def json_files(self) -> None:
        failures: list[str] = []
        parsed_state: dict[str, dict] = {}
        for relative in [
            ".agent-harness.json",
            "docs/state/project.json",
            "docs/state/goals.json",
            "docs/state/tickets.json",
            "docs/state/ownership.json",
            "docs/state/reviews.json",
            "docs/state/team.json",
            "docs/schemas/project.schema.json",
            "docs/schemas/goals.schema.json",
            "docs/schemas/tickets.schema.json",
            "docs/schemas/ownership.schema.json",
            "docs/schemas/reviews.schema.json",
            "docs/schemas/operation.schema.json",
            "docs/schemas/consultant.schema.json",
            "docs/schemas/team.schema.json",
            "docs/evals/harness/report-schema.json",
        ]:
            try:
                parsed = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                if relative.startswith("docs/state/"):
                    parsed_state[Path(relative).stem] = parsed
                elif relative == ".agent-harness.json":
                    self.metadata = parsed
            except (OSError, json.JSONDecodeError) as error:
                failures.append(f"{relative}: {error}")
        if set(parsed_state) == {"project", "goals", "tickets", "ownership", "reviews", "team"}:
            project_record = parsed_state["project"]
            project = project_record.get("project", {})
            self.state = {
                "templateMode": project.get("templateMode"),
                "project": project,
                "baton": project_record.get("baton", {}),
                "goals": parsed_state["goals"].get("goals", []),
                "tickets": parsed_state["tickets"].get("tickets", []),
                "activeWork": parsed_state["ownership"].get("ownership", []),
                "humanReviews": parsed_state["reviews"].get("reviews", []),
                "team": parsed_state["team"],
            }
        self.record("ST-003", not failures, "; ".join(failures) if failures else "metadata, state, and schemas parse")

    def team_contract(self) -> None:
        failures: list[str] = []
        catalog_path = ROOT / "tools/team-presets.json"
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f"team catalog cannot be parsed: {error}")
            catalog = {}
        expected = {
            "game-development": ("Game Development", "Game Director", "Producer", ["art-director"]),
            "software-product": ("Software Product", "Product Manager", "Engineering Manager", ["product-designer"]),
            "business-operations": ("Business Operations", "Program Director", "Operations Manager", ["change-manager"]),
            "research": ("Research", "Principal Investigator", "Research Program Manager", ["research-methodologist"]),
        }
        presets = catalog.get("presets", {}) if isinstance(catalog, dict) else {}
        if set(presets) != set(expected):
            failures.append("team catalog must expose exactly the four approved project presets")
        for identifier, (label, management, operations, defaults) in expected.items():
            preset = presets.get(identifier, {})
            if (
                preset.get("label") != label
                or preset.get("management", {}).get("title") != management
                or preset.get("operations", {}).get("title") != operations
                or preset.get("defaultConsultants") != defaults
            ):
                failures.append(f"preset {identifier} persona/default contract drift")
            if not preset.get("consultants") or not preset.get("contractorBench"):
                failures.append(f"preset {identifier} lacks Consultant or Contractor definitions")
            example = ROOT / "examples" / identifier / "README.md"
            example_text = example.read_text(encoding="utf-8") if example.is_file() else ""
            default_titles = {
                item.get("id"): item.get("title")
                for item in preset.get("consultants", [])
                if isinstance(item, dict)
            }
            required_example_values = [management, operations, *(default_titles.get(item, "") for item in defaults)]
            if not example_text or any(value not in example_text for value in required_example_values):
                failures.append(f"example {identifier} does not match its catalog personas/defaults")
        if catalog.get("commonNames") != {
            "management": "Management",
            "operations": "Operations",
            "consultants": "Consultants",
            "contractors": "Contractors",
            "internalAudit": "Internal Audit",
        }:
            failures.append("common team vocabulary drift")
        if catalog.get("consultantNonAuthorities") != [
            "overall priority", "Contractor dispatch", "technical integration", "publication"
        ]:
            failures.append("Consultant authority exclusions drift")
        process = subprocess.run(
            [sys.executable, str(ROOT / "tools/harness_team.py"), "check", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode:
            failures.append(process.stderr.strip() or process.stdout.strip() or "team check failed")
        for command in ("hire", "fire"):
            if (ROOT / command).exists():
                failures.append(f"{command} must remain skill-only, not a root command")
        skill_commands = {
            "hire-consultant": "tools/harness_team.py hire",
            "fire-consultant": "tools/harness_team.py fire",
        }
        for skill, command in skill_commands.items():
            text = (ROOT / ".agents/skills" / skill / "SKILL.md").read_text(
                encoding="utf-8"
            )
            if command not in text:
                failures.append(f"{skill} does not use the deterministic team engine")
        for relative in (
            "AGENTS.md",
            "README.md",
            "HARNESS.md",
            "docs/customization.md",
            "docs/getting-started.md",
            "docs/installation.md",
        ):
            user_text = (ROOT / relative).read_text(encoding="utf-8")
            if re.search(r"tools/harness_team\.py\s+(?:hire|fire)\b", user_text):
                failures.append(
                    f"{relative} bypasses the skill-only Consultant lifecycle"
                )
        operation_schema = json.loads(
            (ROOT / "docs/schemas/operation.schema.json").read_text(encoding="utf-8")
        )
        operation_records = operation_schema["properties"]["records"]["properties"]
        if "team" in operation_records:
            failures.append("generic state operations must not accept team state")
        tickets_schema = json.loads(
            (ROOT / "docs/schemas/tickets.schema.json").read_text(encoding="utf-8")
        )
        ticket_item = tickets_schema["properties"]["tickets"]["items"]
        if "requiredConsultantIds" not in ticket_item.get("required", []):
            failures.append("tickets do not require explicit Consultant identities")
        reviews_schema = json.loads(
            (ROOT / "docs/schemas/reviews.schema.json").read_text(encoding="utf-8")
        )
        if "consultantReviews" not in reviews_schema.get("required", []):
            failures.append("reviews do not model Consultant readiness and acceptance")
        self.record(
            "ST-047",
            not failures,
            "; ".join(failures)
            if failures
            else "four presets, common vocabulary, typed Consultant gates, and skill-only team operations agree",
        )

    def codex_agent_configs(self) -> None:
        required_agents = [
            ".codex/agents/management.toml",
            ".codex/agents/operations.toml",
            ".codex/agents/contractor.toml",
            ".codex/agents/internal-audit.toml",
        ]
        team = self.state.get("team", {})
        for consultant in team.get("consultants", []):
            if isinstance(consultant, dict) and consultant.get("status") == "active":
                required_agents.append(str(consultant.get("configPath", "")))
        allowed = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
        failures: list[str] = []
        files = required_agents
        for relative in files:
            path = ROOT / relative
            if not path.is_file():
                failures.append(f"missing {relative}")
                continue
            text = path.read_text(encoding="utf-8")
            for key in ["name", "description", "developer_instructions"]:
                if not re.search(rf"^{key}\s*=", text, re.MULTILINE):
                    failures.append(f"{relative}: missing {key}")
            if ".agents/rules/" not in text:
                failures.append(f"{relative}: startup does not load applicable modular rules")
            match = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', text, re.MULTILINE)
            if match and match.group(1) not in allowed:
                failures.append(f"{relative}: unsupported reasoning {match.group(1)}")
        config = ROOT / ".codex/config.toml"
        if config.is_file():
            try:
                assert_codex_config(config)
            except (AssertionError, OSError, ValueError) as error:
                failures.append(f".codex/config.toml: {error}")
        self.record("ST-005", not failures, "; ".join(failures) if failures else f"{len(files)} Codex role configs valid")

    def text_integrity(self) -> None:
        problems: list[str] = []
        text_suffixes = {".md", ".json", ".yml", ".yaml", ".py", ".sh", ".toml", ".txt"}
        for file in ROOT.rglob("*"):
            if not file.is_file() or ".git" in file.parts or ".artifacts" in file.parts:
                continue
            if file.suffix not in text_suffixes and file.name not in {"LICENSE", "VERSION", ".gitignore", ".editorconfig"}:
                continue
            text = file.read_text(encoding="utf-8")
            if re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.MULTILINE):
                problems.append(f"{file.relative_to(ROOT)}: conflict marker")
            for index, line in enumerate(text.splitlines(), start=1):
                if line.endswith((" ", "\t")):
                    problems.append(f"{file.relative_to(ROOT)}:{index}: trailing whitespace")
                    break
        self.record("ST-004", not problems, "; ".join(problems[:20]) if problems else "no conflict markers or trailing whitespace")

    def governance_modules(self) -> None:
        agents = ROOT / "AGENTS.md"
        rules_dir = ROOT / ".agents/rules"
        all_rule_files = sorted(rules_dir.glob("*.md")) if rules_dir.is_dir() else []
        failures: list[str] = []
        if not agents.is_file():
            failures.append("AGENTS.md missing")
        else:
            text = agents.read_text(encoding="utf-8")
            # AGENTS is deliberately a navigational index. Normative bullets and
            # procedural headings belong in .agents/rules instead.
            if re.search(r"^\s*(?:[-*]|\d+[.)])\s+", text, re.MULTILINE):
                failures.append("AGENTS.md contains normative list items")
            links = LINK_RE.findall(text)
            if not links:
                failures.append("AGENTS.md has no rule-map links")
            for target in links:
                target = target.strip().strip("<>").split("#", 1)[0]
                if target.startswith(("http://", "https://", "mailto:", "#", "thread:", "plugin:")):
                    continue
                if not (agents.parent / unquote(target)).resolve().exists():
                    failures.append(f"AGENTS.md broken link: {target}")
            required_map_targets = {
                *(f".agents/rules/{name}.md" for name in REQUIRED_RULES),
                ".agents/rules/_template.md",
                *(f".agents/rules/{path.name}" for path in all_rule_files),
                *(f".agents/skills/{name}/SKILL.md" for name in REQUIRED_SKILLS),
                "docs/overview.md",
                "docs/direction.md",
                "docs/index.html",
                "docs/state/project.json",
                "docs/state/goals.json",
                "docs/state/tickets.json",
                "docs/state/ownership.json",
                "docs/state/reviews.json",
                "docs/state/team.json",
                "docs/roles/management.md",
                "docs/roles/operations.md",
                "docs/roles/consultant.md",
                "docs/roles/internal-audit.md",
                "docs/roles/contractor.md",
                "docs/workflow.md",
                "docs/releasing.md",
            }
            normalized_targets = {
                unquote(target.strip().strip("<>").split("#", 1)[0]) for target in links
            }
            missing_map_targets = sorted(required_map_targets - normalized_targets)
            if missing_map_targets:
                failures.append("AGENTS.md missing map targets: " + ", ".join(missing_map_targets))
            if re.search(r"^##\s+(?:Core rules|Rules|Instructions|Operating rules)\s*$", text, re.MULTILINE | re.IGNORECASE):
                failures.append("AGENTS.md contains a normative rule section")
        required_rule_names = {"_template.md", *(f"{name}.md" for name in REQUIRED_RULES)}
        actual_rule_names = {path.name for path in all_rule_files}
        missing_rule_names = sorted(required_rule_names - actual_rule_names)
        if missing_rule_names:
            failures.append(
                "required rule files missing: " + ", ".join(missing_rule_names)
            )
        rule_files = [rule for rule in all_rule_files if rule.name != "_template.md"]
        section_sets: set[tuple[str, ...]] = set()
        common_sections = ("Title", "Type", "Purpose", "Scope", "Definition", "How to Apply", "Do", "Don't", "Example", "Validation", "References", "Notes")
        for rule in all_rule_files:
            text = rule.read_text(encoding="utf-8")
            sections = tuple(re.findall(r"^([A-Za-z][A-Za-z ']+):\s*$", text, re.MULTILINE))
            if not text.lstrip().startswith("# ") or sections != common_sections:
                failures.append(f"{rule.relative_to(ROOT)} lacks the common section template")
            section_sets.add(sections)
        if len(section_sets) > 1:
            failures.append("rule section headings differ between rule modules")
        self.record("ST-040", not failures, "; ".join(failures) if failures else f"AGENTS map-only; {len(rule_files)} rules and template share one section contract")

    def skill_discovery(self) -> None:
        skills_root = ROOT / ".agents/skills"
        discovery = ROOT / ".codex/skills"
        failures: list[str] = []
        for skill in REQUIRED_SKILLS:
            path = skills_root / skill
            skill_file = path / "SKILL.md"
            if not skill_file.is_file():
                failures.append(f"missing {skill}/SKILL.md")
                continue
            text = skill_file.read_text(encoding="utf-8")
            if not text.startswith("---\n") or not re.search(rf"^name:\s*{re.escape(skill)}\s*$", text, re.MULTILINE):
                failures.append(f"{skill}/SKILL.md lacks matching frontmatter name")
            if not re.search(r"^#\s+", text, re.MULTILINE) or not re.search(r"\$" + re.escape(skill) + r"\b", text):
                failures.append(f"{skill}/SKILL.md lacks title or explicit $ invocation")
            metadata_file = path / "agents/openai.yaml"
            if not metadata_file.is_file():
                failures.append(f"missing {skill}/agents/openai.yaml")
            else:
                metadata_text = metadata_file.read_text(encoding="utf-8")
                if not all(key in metadata_text for key in ("display_name:", "short_description:", "default_prompt:")):
                    failures.append(f"{skill}/agents/openai.yaml lacks interface metadata")
                if not re.search(r"^\s*allow_implicit_invocation:\s*false\s*$", metadata_text, re.MULTILINE):
                    failures.append(f"{skill}/agents/openai.yaml must require explicit invocation")
        required_support = (
            skills_root / "improve-codebase-architecture/references/report-format.md",
            skills_root / "code-review/references/review-axes.md",
        )
        for path in required_support:
            if not path.is_file():
                failures.append(f"missing {path.relative_to(ROOT)}")
        if not discovery.is_symlink():
            failures.append(".codex/skills is not a discovery symlink")
        else:
            target = discovery.readlink()
            if target != Path("../.agents/skills"):
                failures.append(f".codex/skills target is {target!s}, expected ../.agents/skills")
            if discovery.resolve() != skills_root.resolve():
                failures.append(".codex/skills does not resolve to .agents/skills")
        if discovery.is_dir() and not discovery.is_symlink():
            failures.append(".codex/skills contains a duplicated copy")
        metadata = skills_root / "skills.json"
        support = [skills_root / name for name in ("README.md", "ATTRIBUTION.md", "NOTICE.md")]
        support += [ROOT / "THIRD_PARTY_NOTICES.md"]
        if not metadata.is_file():
            failures.append(".agents/skills/skills.json missing")
        else:
            try:
                manifest = json.loads(metadata.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                failures.append(f".agents/skills/skills.json invalid: {error}")
            else:
                if manifest.get("skills") != list(REQUIRED_SKILLS) or manifest.get("invocation") != "explicit" or manifest.get("discovery") != "../.agents/skills":
                    failures.append(".agents/skills/skills.json does not match the discovery contract")
        if not any(path.is_file() for path in support):
            failures.append("skill attribution/support notice missing")
        notice = ROOT / "THIRD_PARTY_NOTICES.md"
        if notice.is_file() and "Copyright (c) 2026 Matt Pocock" not in notice.read_text(encoding="utf-8"):
            failures.append("third-party notice does not preserve the upstream copyright line")
        self.record("ST-041", not failures, "; ".join(failures) if failures else "five skills, metadata, support notice, and relative discovery symlink valid")

    def role_integration(self) -> None:
        failures: list[str] = []
        role_files = {
            "management": ROOT / "docs/roles/management.md",
            "operations": ROOT / "docs/roles/operations.md",
            "consultant": ROOT / "docs/roles/consultant.md",
            "contractor": ROOT / "docs/roles/contractor.md",
            "internal_audit": ROOT / "docs/roles/internal-audit.md",
        }
        texts = {name: path.read_text(encoding="utf-8") if path.is_file() else "" for name, path in role_files.items()}
        failures.extend(f"missing {name} role contract" for name, text in texts.items() if not text)
        failures.extend(
            f"{name} role startup does not load applicable modular rules"
            for name, text in texts.items()
            if text and "applicable rule" not in text.casefold()
        )
        required_phrases = {
            "management": (
                "## Final audit",
                "Operations' pinned boundary",
                "independent two-axis findings",
                "applicable Consultant acceptance",
                "Never dispatch or steer Contractors directly",
            ),
            "operations": (
                "Before substantial acceptance",
                "standards/architecture and specification/evidence",
                "Contractor dispatch",
                "Consultant domain acceptance",
            ),
            "consultant": (
                "Do not own overall priority, Contractor dispatch, technical integration, or publication",
                "Never dispatch or steer Contractors directly",
            ),
            "contractor": (
                "exclusive ownership",
                "return exact evidence to Operations",
            ),
            "internal_audit": (
                "Evaluate whether the orchestration harness produces safe, efficient, evidence-backed advancement",
                "not product QA",
                "Do not edit",
            ),
        }
        for role, phrases in required_phrases.items():
            folded = texts[role].casefold()
            missing = [phrase for phrase in phrases if phrase.casefold() not in folded]
            if missing:
                failures.append(f"{role} role missing required contract: " + "; ".join(missing))
        self.record("ST-042", not failures, "; ".join(failures) if failures else "Management/Operations integration and Consultant/Contractor/Internal Audit boundaries present")

    def permanent_task_lifecycle(self) -> None:
        failures: list[str] = []
        sources = {
            "rule": ROOT / ".agents/rules/lifecycle-and-idle.md",
            "management": ROOT / "docs/roles/management.md",
            "operations": ROOT / "docs/roles/operations.md",
            "consultant": ROOT / "docs/roles/consultant.md",
            "management_config": ROOT / ".codex/agents/management.toml",
            "operations_config": ROOT / ".codex/agents/operations.toml",
            "consultant_config": ROOT / ".codex/agents/consultant-product-designer.toml",
            "workflow": ROOT / "docs/workflow.md",
            "registry": ROOT / "docs/thread-registry.md",
            "decision": ROOT / "docs/decisions/ADR-0001-task-message-wake-only.md",
            "guide": ROOT / "HARNESS.md",
            "generator": ROOT / "tools/harness_lifecycle.py",
            "operator": ROOT / "docs/evals/harness/operator-prompt.md",
            "input": ROOT / "docs/evals/harness/scenarios/inputs/H-011.md",
            "oracle": ROOT / "docs/evals/harness/scenarios/oracles/H-011.md",
        }
        texts = {
            name: path.read_text(encoding="utf-8") if path.is_file() else ""
            for name, path in sources.items()
        }
        for name, text in texts.items():
            if not text:
                failures.append(f"missing permanent-task lifecycle source: {name}")

        shared_contracts = {
            "rule": (
                "permanent top-level tasks",
                "sole wake mechanism",
                "superseding any older onboarding prompt",
                "complete goal controls",
                "legacy automatic continuation",
                "no speculative work",
            ),
            "management_config": (
                "permanent top-level task",
                "task-message-only wake",
                "Never operate a persistent Codex goal",
            ),
            "operations_config": (
                "permanent top-level task",
                "task-message-only wake",
                "Never operate a persistent Codex goal",
            ),
            "consultant_config": (
                "permanent top-level task",
                "task-message-only wake",
                "Never operate a persistent Codex goal",
            ),
            "management": (
                "permanent top-level task",
                "sole wake mechanism",
                "supersedes older prompts",
                "Never create, inspect, resume",
                "legacy auto-resume without a new task message",
                "performs no work",
            ),
            "operations": (
                "permanent top-level task",
                "woken only by a new task message",
                "Never operate a persistent Codex goal",
                "legacy auto-resume without a new task message",
                "performs no work",
            ),
            "consultant": (
                "permanent top-level task",
                "woken only by a new task message",
                "Never operate a persistent Codex goal",
                "inactive",
            ),
            "workflow": (
                "Permanent-task wake policy",
                "sole wake mechanism",
                "supersedes older onboarding prompts",
                "complete goal controls",
                "automatic continuation",
                "no repository refresh, speculative work",
            ),
            "registry": (
                "sole wake mechanism",
                "complete goal controls",
                "supersedes older onboarding prompts",
                "legacy auto-resume",
                "no speculative work",
            ),
            "decision": (
                "Status: Accepted",
                "sole wake mechanism",
                "supersedes every older onboarding prompt",
                "complete controls",
                "automatic continuation without a new task message",
                "no speculative work or goal operation",
            ),
            "guide": (
                "sole wake mechanism",
                "complete controls exist",
                "supersedes older onboarding prompts",
                "auto-resumes a permanent role without a new task message",
                "no repository refresh, speculative work",
            ),
            "generator": (
                "task messages are the sole wake mechanism",
                "complete goal controls exist",
                "supersedes older onboarding prompts",
                "auto-resumes a task without a new message",
                "no speculative work or goal operation",
            ),
            "operator": (
                "persistent_goal_operations",
                "sole wake mechanism",
                "complete goal controls exist",
                "older onboarding instructions request one",
                "automatic continuation without a new task message",
            ),
            "input": (
                "Complete persistent-goal controls",
                "create, inspect, pause, resume, and clear",
                "Older onboarding instruction",
                "No new message",
                "automatically continues",
            ),
            "oracle": (
                "non-wake event",
                "full create, inspect, pause, resume, and clear controls",
                'persistent_goal_operations`: `[]`',
                "no goal operation, repository refresh, speculative work",
                "user or administrative removal",
            ),
        }
        for name, phrases in shared_contracts.items():
            folded = texts[name].casefold()
            missing = [phrase for phrase in phrases if phrase.casefold() not in folded]
            if missing:
                failures.append(
                    f"{name} omits permanent-task lifecycle contract: "
                    + "; ".join(missing)
                )

        self.record(
            "ST-046",
            not failures,
            "; ".join(failures)
            if failures
            else "Management, Operations, and active Consultants are message-woken, persistent-goal-free, and covered by H-011",
        )

    def lifecycle_contract(self) -> None:
        failures: list[str] = []
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        metadata = self.metadata
        if type(metadata.get("schemaVersion")) is not int or metadata.get("schemaVersion") != 2:
            failures.append(".agent-harness.json must use metadata schemaVersion 2")
        if metadata.get("harnessVersion") != version:
            failures.append("metadata harnessVersion does not match VERSION")
        if type(metadata.get("stateSchemaVersion")) is not int or metadata.get("stateSchemaVersion") != 1:
            failures.append("metadata stateSchemaVersion must be 1")
        default_reasoning = {
            "management": "high",
            "operations": "high",
            "consultants": "high",
            "contractors": "medium",
            "internalAudit": "xhigh",
        }
        if metadata.get("installationStatus") == "Template" and (
            metadata.get("reasoningPreset") != "medium"
            or metadata.get("reasoning") != default_reasoning
        ):
            failures.append("template metadata must use the Medium reasoning preset")
        if metadata.get("installationStatus") not in {
            "Template", "Installed", "Needs Integration", "Migration Blocked", "Legacy"
        }:
            failures.append("metadata installationStatus is invalid")
        source = metadata.get("source")
        status = metadata.get("installationStatus")
        if not isinstance(source, dict) or set(source) != {"repository", "channel", "tag", "commit", "manifestSha256"}:
            failures.append("metadata source provenance has an invalid shape")
        elif source.get("repository") != "FabienGreard/agentic-project-harness":
            failures.append("metadata source repository is not official")
        elif status == "Template":
            if source.get("channel") != "unreleased-template" or any(source.get(key) is not None for key in ("tag", "commit", "manifestSha256")):
                failures.append("template provenance must remain explicitly unreleased")
        elif source.get("channel") == "stable":
            if source.get("tag") != f"v{version}" or not re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit"))) or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("manifestSha256"))):
                failures.append("stable provenance must pin matching tag, commit, and manifest checksum")
        elif source.get("channel") == "local-development":
            if source.get("tag") != "local-working-tree" or not re.fullmatch(r"(?:[0-9a-f]{40}|local-working-tree)", str(source.get("commit"))) or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("manifestSha256"))):
                failures.append("local-development provenance is incomplete")
        else:
            failures.append("installed provenance channel is unsupported")
        managed = metadata.get("managedFiles")
        if not isinstance(managed, dict):
            failures.append("metadata managedFiles must be an object")
        else:
            for path, record in managed.items():
                if not isinstance(path, str) or not isinstance(record, dict):
                    failures.append("metadata contains an invalid managed-file record")
                    break
                if record.get("ownership") not in {"harness-managed", "generated-config", "project-owned"}:
                    failures.append(f"metadata ownership is invalid for {path}")
                    break
                digest = record.get("baselineSha256")
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    failures.append(f"metadata baseline checksum is invalid for {path}")
                    break
        pending = metadata.get("pendingIntegration")
        if not isinstance(pending, list):
            failures.append("metadata pendingIntegration must be an array")
        elif metadata.get("installationStatus") == "Needs Integration" and not pending:
            failures.append("Needs Integration metadata must identify preserved collisions")
        elif metadata.get("installationStatus") != "Needs Integration" and pending:
            failures.append("pendingIntegration requires Needs Integration status")
        else:
            seen_pending: set[str] = set()
            for record in pending:
                if not isinstance(record, dict) or set(record) != {"path", "targetSha256", "targetOwnership"}:
                    failures.append("metadata contains an invalid pendingIntegration record")
                    break
                path = record.get("path")
                if not isinstance(path, str) or not path or path in seen_pending:
                    failures.append("metadata pendingIntegration paths must be unique non-empty strings")
                    break
                seen_pending.add(path)
                if record.get("targetOwnership") not in {"harness-managed", "generated-config", "project-owned"} or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("targetSha256"))):
                    failures.append(f"metadata pendingIntegration target is invalid for {path}")
                    break

        lifecycle_source = (ROOT / "tools/harness_lifecycle.py").read_text(
            encoding="utf-8"
        )
        lock_source = (ROOT / "tools/harness_lock.py").read_text(encoding="utf-8")
        installer_source = (ROOT / "install.sh").read_text(encoding="utf-8")
        bundle_source = (ROOT / "tools/release_bundle.py").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "verify_installed_baselines",
            "upgradeOrigins",
            "manifestSha256",
            "project-owned path is never retired automatically",
            "target path must not contain a '..' segment",
        ):
            if phrase not in lifecycle_source:
                failures.append(f"lifecycle engine omits immutable safety contract: {phrase}")
        mutation_sources = {
            "lifecycle": lifecycle_source,
            "state": (ROOT / "tools/harness_state.py").read_text(encoding="utf-8"),
            "team": (ROOT / "tools/harness_team.py").read_text(encoding="utf-8"),
        }
        if (
            "fcntl.flock" not in lock_source
            or "LOCK_EX" not in lock_source
            or "O_NOFOLLOW" not in lock_source
            or "agentic-project-harness-{os.getuid()}" not in lock_source
            or "XDG_STATE_HOME" in lock_source
        ):
            failures.append("shared mutation lock is not an exclusive cross-process lock")
        for surface, source in mutation_sources.items():
            if "mutation_lock" not in source:
                failures.append(f"{surface} mutations bypass the shared project lock")
        if "TAG=COMMIT[,MANIFEST_SHA256]" not in bundle_source:
            failures.append("release bundle does not require immutable origin anchors")
        reasoning_contract = (
            'REASONING_PRESET="medium"',
            'menu_select "How much reasoning should the team use?" 1',
            'REASONING_PRESET=low; MANAGEMENT_REASONING=medium; OPERATIONS_REASONING=medium',
            'CONSULTANT_REASONING=medium; CONTRACTOR_REASONING=low; AUDIT_REASONING=high',
            'REASONING_PRESET=high; MANAGEMENT_REASONING=xhigh; OPERATIONS_REASONING=xhigh',
            'CONSULTANT_REASONING=xhigh; CONTRACTOR_REASONING=high; AUDIT_REASONING=xhigh',
            '"Software Product — app, service, platform, or library"',
            '"Game Development — playable or interactive experience"',
            '"Business Operations — process, policy, or service delivery"',
            '"Research — investigation or evidence program"',
        )
        for phrase in reasoning_contract:
            if phrase not in installer_source:
                failures.append(f"installer omits reasoning preset contract: {phrase}")

        help_result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if help_result.returncode:
            failures.append("install.sh --help failed")
        else:
            help_text = help_result.stdout
            for token in ("status", "update", "--json", "--yes", "--help"):
                if token not in help_text:
                    failures.append(f"install.sh help omits {token}")
            for retired in ("--project-name", "--target", "--reasoning-preset", " uninstall ", " migrate "):
                if retired in help_text:
                    failures.append(f"install.sh exposes retired public surface {retired.strip()}")
        self.record(
            "ST-043",
            not failures,
            "; ".join(failures)
            if failures
            else "metadata v2, the shared mutation lock, and the install/status/update lifecycle surface agree",
        )

    def state_contract(self) -> None:
        failures: list[str] = []
        state_source = (ROOT / "tools/harness_state.py").read_text(encoding="utf-8")
        schema_source = (ROOT / "tools/json_schema_contract.py").read_text(
            encoding="utf-8"
        )
        if "schema_errors(" not in state_source:
            failures.append("state writer does not execute the committed JSON schemas")
        for required_keyword in ("uniqueItems", "additionalProperties", "$ref", "allOf"):
            if required_keyword not in schema_source:
                failures.append(
                    f"schema executor omits required JSON Schema keyword {required_keyword}"
                )
        process = subprocess.run(
            [sys.executable, str(ROOT / "tools/harness_state.py"), "check", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode:
            failures.append(process.stderr.strip() or process.stdout.strip() or "state check failed")
        else:
            try:
                result = json.loads(process.stdout)
            except json.JSONDecodeError as error:
                failures.append(f"state check did not emit JSON: {error}")
            else:
                if result.get("ok") is not True:
                    failures.append("state check returned ok=false")
        self.record(
            "ST-044",
            not failures,
            "; ".join(failures)
            if failures
            else "committed schemas, canonical JSON records, and generated dashboard agree",
        )

        rule = (ROOT / ".agents/rules/llm-first-operability.md").read_text(encoding="utf-8")
        docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/workflow.md", "docs/customization.md")
        )
        llm_ok = all(
            phrase.casefold() in (rule + "\n" + docs).casefold()
            for phrase in (
                "LLM-first",
                "human-governed",
                "tools/harness_state.py",
                "docs/index.html",
                "destructive",
                "release",
            )
        )
        self.record(
            "ST-045",
            llm_ok,
            "LLM-readable state and deterministic tools remain subordinate to human authority" if llm_ok else "LLM-first/human-governed contract is incomplete",
        )

    def assurance_contract(self) -> None:
        failures: list[str] = []
        project = json.loads(
            (ROOT / "docs/state/project.json").read_text(encoding="utf-8")
        )["project"]
        if project.get("assuranceDefaults") != {
            "testRigor": "Standard",
            "humanReviewStages": [],
        }:
            failures.append("generated project assurance defaults must be Standard and explicitly no human review")

        ticket_schema = json.loads(
            (ROOT / "docs/schemas/tickets.schema.json").read_text(encoding="utf-8")
        )["properties"]["tickets"]["items"]
        assurance = ticket_schema.get("properties", {}).get("assurance", {})
        if "assurance" not in ticket_schema.get("required", []):
            failures.append("tickets do not require explicit resolved assurance")
        if assurance.get("required") != [
            "testRigor",
            "humanReviewStages",
            "overrideReason",
        ]:
            failures.append("ticket assurance fields drift")
        if assurance.get("properties", {}).get("testRigor", {}).get("enum") != [
            "Lean",
            "Standard",
            "Thorough",
        ]:
            failures.append("test-rigor vocabulary drift")
        expected_stages = ["Readiness", "Acceptance", "Release"]
        if assurance.get("properties", {}).get("humanReviewStages", {}).get(
            "items", {}
        ).get("enum") != expected_stages:
            failures.append("human-review stage vocabulary drift")

        reviews_schema = json.loads(
            (ROOT / "docs/schemas/reviews.schema.json").read_text(encoding="utf-8")
        )["properties"]["reviews"]["items"]
        if "stage" not in reviews_schema.get("required", []):
            failures.append("human review records do not require timing stage")
        if reviews_schema.get("properties", {}).get("stage", {}).get("enum") != expected_stages:
            failures.append("human review records use inconsistent stages")
        approval_requirements = [
            branch.get("then", {}).get("required", [])
            for branch in reviews_schema.get("allOf", [])
            if branch.get("if", {}).get("properties", {}).get("status", {}).get("const")
            == "Approved"
        ]
        if not approval_requirements or not {
            "reviewer",
            "recordedAt",
        }.issubset(approval_requirements[0]):
            failures.append("Approved human reviews do not require durable attribution")

        state_source = (ROOT / "tools/harness_state.py").read_text(encoding="utf-8")
        test_source = (ROOT / "tests/harness_state_smoke.py").read_text(encoding="utf-8")
        update_test_source = (ROOT / "tests/install_update_smoke.py").read_text(
            encoding="utf-8"
        )
        schema_contract_source = (
            ROOT / "tools/json_schema_contract.py"
        ).read_text(encoding="utf-8")
        if "_json_equal" not in schema_contract_source:
            failures.append("JSON const/enum equality is not type-aware")
        docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                ".agents/rules/testing.md",
                ".agents/rules/readiness-and-scope.md",
                ".agents/rules/completion-and-review.md",
                "docs/workflow.md",
                "docs/customization.md",
                "docs/tickets/README.md",
            )
        )
        for phrase in (
            "human-authorized overrideReason",
            "lacks approved human review for",
            "Test rigor",
            "Default assurance",
        ):
            if phrase not in state_source:
                failures.append(f"state writer/dashboard omits assurance contract: {phrase}")
        for phrase in (
            "Lean",
            "Standard",
            "Thorough",
            "Readiness",
            "Acceptance",
            "Release",
            "empty array explicitly means no human review",
        ):
            if phrase.casefold() not in docs.casefold():
                failures.append(f"assurance documentation omits: {phrase}")
        for phrase in (
            "unreasoned-assurance-override",
            "missing-human-readiness",
            "missing-human-acceptance",
            "pending-release-after-completion",
            "boolean-operation-version",
            "boolean-record-version",
            "unattributed-human-readiness",
            "generic-human-readiness",
            "symlink-human-readiness",
            "conflicting-human-readiness",
            "conflicting-consultant-readiness",
        ):
            if phrase not in test_source:
                failures.append(f"assurance smoke coverage omits {phrase}")
        for phrase in (
            "missing-installed-evidence",
            "UPDATE-EVIDENCE-GOAL",
            "UPDATE-REVIEW.md",
            "project-proof.txt",
        ):
            if phrase not in update_test_source:
                failures.append(f"update evidence smoke coverage omits {phrase}")

        self.record(
            "ST-048",
            not failures,
            "; ".join(failures)
            if failures
            else "project defaults, resolved ticket rigor, staged human gates, overrides, dashboard, and smoke coverage agree",
        )

    def risk_based_review_contract(self) -> None:
        sources = {
            "rule": ROOT / ".agents/rules/risk-based-findings.md",
            "testing": ROOT / ".agents/rules/testing.md",
            "skill": ROOT / ".agents/skills/code-review/SKILL.md",
            "axes": ROOT / ".agents/skills/code-review/references/review-axes.md",
            "workflow": ROOT / "docs/workflow.md",
            "rubric": ROOT / "docs/evals/harness/rubric.md",
            "operator": ROOT / "docs/evals/harness/operator-prompt.md",
            "report": ROOT / "docs/evals/harness/report-template.md",
            "scenario_index": ROOT / "docs/evals/harness/scenarios/README.md",
            "h12_input": ROOT / "docs/evals/harness/scenarios/inputs/H-012.md",
            "h12_oracle": ROOT / "docs/evals/harness/scenarios/oracles/H-012.md",
            "h13_input": ROOT / "docs/evals/harness/scenarios/inputs/H-013.md",
            "h13_oracle": ROOT / "docs/evals/harness/scenarios/oracles/H-013.md",
        }
        contracts = {
            "rule": (
                "Confirmed",
                "Proven",
                "Plausible",
                "Hypothetical",
                "blocking credible P0",
                "confirmed or proven P1",
                "one initial review",
                "at most one follow-up review",
                "Reopen a closed finding only for new evidence",
                "at most three",
                "explicitly authorized new bounded review task",
            ),
            "testing": (
                "Use `Lean` for isolated, reversible, low-impact behavior",
                "`Thorough` for changes with material security, privacy, authorization, money",
                "speculative findings",
            ),
            "skill": (
                "risk-based-findings.md",
                "stable ID, confidence, severity, trigger",
                "at most three P2/P3 items",
                "Use `REVISE` only",
                "one initial review and at most one follow-up review",
                "new evidence",
                "explicitly authorized new bounded review task",
            ),
            "axes": (
                "stable finding ID",
                "`Hypothetical` concerns",
                "credible supported path",
                "Only a confirmed or proven P1 blocks",
            ),
            "workflow": (
                "risk-based findings rule",
                "credible P0 or Confirmed/Proven P1 as a blocker",
                "at most three P2/P3 follow-ups",
                "one initial review and at most one fix-focused follow-up",
            ),
            "rubric": ("HG-12", "P2, P3, or Hypothetical", "new evidence"),
            "operator": (
                "blocking finding IDs",
                "at most three non-blocking follow-ups",
                "stop reason",
            ),
            "report": (
                "stable ID",
                "confidence",
                "supported reachability",
                "Hypothetical concerns are residual uncertainty",
            ),
            "scenario_index": ("H-012", "H-013"),
            "h12_input": ("F-101", "F-102", "F-103"),
            "h12_oracle": ("`REVISE` for `F-101` only", "non-blocking", "Hypothetical"),
            "h13_input": ("single follow-up", "No new reachable P0", "Confirmed/Proven P1"),
            "h13_oracle": ("`APPROVE`", "stop", "without new evidence"),
        }
        failures: list[str] = []
        for name, path in sources.items():
            if not path.is_file():
                failures.append(f"missing risk-based review source: {name}")
                continue
            text = path.read_text(encoding="utf-8")
            missing = [phrase for phrase in contracts[name] if phrase not in text]
            if missing:
                failures.append(
                    f"{name} omits risk-based review contract: " + "; ".join(missing)
                )
        self.record(
            "ST-049",
            not failures,
            "; ".join(failures)
            if failures
            else "finding confidence, severity, blocking thresholds, bounded passes, and H-012/H-013 coverage agree",
        )

    def ticket_state(self) -> None:
        tickets = self.state.get("tickets", [])
        ticket_map = {ticket.get("id"): ticket for ticket in tickets}
        ids = [ticket.get("id") for ticket in tickets]
        paths_missing = [
            ticket.get("narrativePath", "")
            for ticket in tickets
            if ticket.get("narrativePath")
            and (
                repository_path(ticket["narrativePath"]) is None
                or not repository_path(ticket["narrativePath"]).is_file()
            )
        ]
        unique = len(ids) == len(set(ids)) and None not in ids
        self.record("ST-010", unique and not paths_missing, "duplicate IDs or missing paths: " + ", ".join(filter(None, paths_missing)) if not (unique and not paths_missing) else f"{len(ids)} ticket IDs and paths valid")

        bad_dependencies: list[str] = []
        for ticket in tickets:
            for dependency in ticket.get("dependencies", []):
                if dependency not in ticket_map or dependency == ticket.get("id"):
                    bad_dependencies.append(f"{ticket.get('id')} -> {dependency}")
        self.record("ST-011", not bad_dependencies, "; ".join(bad_dependencies) if bad_dependencies else "dependency references valid")

        active = self.state.get("activeWork", [])
        missing_active = [item.get("ticket", "") for item in active if item.get("ticket") not in ticket_map]
        invalid_active = [item.get("ticket", "") for item in active if item.get("status") not in ACTIVE_STATUSES]
        self.record("ST-012", not missing_active and not invalid_active, f"missing={missing_active}, invalid={invalid_active}" if missing_active or invalid_active else f"{len(active)} active records valid")

        mismatches = [
            item.get("ticket", "")
            for item in active
            if item.get("ticket") in ticket_map
            and ticket_map[item["ticket"]].get("status")
            != OWNERSHIP_TICKET_STATUS.get(item.get("status"))
        ]
        self.record(
            "ST-013",
            not mismatches,
            "status mismatch: " + ", ".join(mismatches)
            if mismatches
            else "ownership steps map to ticket statuses",
        )

        unready: list[str] = []
        for ticket in tickets:
            if ticket.get("status") == "Ready":
                incomplete = [dependency for dependency in ticket.get("dependencies", []) if ticket_map.get(dependency, {}).get("status") != "Done"]
                if incomplete:
                    unready.append(f"{ticket.get('id')}: {','.join(incomplete)}")
        self.record("ST-014", not unready, "; ".join(unready) if unready else "Ready dependencies are Done")

        missing_reports: list[str] = []
        for ticket in tickets:
            if ticket.get("status") == "Done":
                report = ticket.get("reportPath", "")
                report_file = repository_path(report)
                if report_file is None or not report_file.is_file():
                    missing_reports.append(ticket.get("id", ""))
        self.record("ST-015", not missing_reports, "missing reports: " + ", ".join(missing_reports) if missing_reports else "Done ticket reports present")

    def goal_state(self) -> None:
        goals = self.state.get("goals", [])
        goal_map = {goal.get("id"): goal for goal in goals}
        ids = [goal.get("id") for goal in goals]
        current_goal = self.state.get("project", {}).get("currentGoal", "")
        current_ok = (
            not current_goal
            or (
                current_goal in goal_map
                and goal_map[current_goal].get("status") != "Done"
            )
        )
        self.record(
            "ST-016",
            len(ids) == len(set(ids)) and None not in ids and current_ok,
            f"goals={len(ids)}, current={current_goal or 'none'}",
        )

        bad_dependencies = [
            f"{goal.get('id')} -> {dependency}"
            for goal in goals
            for dependency in goal.get("dependencies", [])
            if dependency not in goal_map or dependency == goal.get("id")
        ]
        remaining = {
            goal.get("id"): {
                dependency
                for dependency in goal.get("dependencies", [])
                if dependency in goal_map
            }
            for goal in goals
        }
        while True:
            resolved = {identifier for identifier, dependencies in remaining.items() if not dependencies}
            if not resolved:
                break
            remaining = {
                identifier: dependencies - resolved
                for identifier, dependencies in remaining.items()
                if identifier not in resolved
            }
        if remaining:
            bad_dependencies.append(
                "cycle among " + ", ".join(sorted(remaining))
            )
        self.record(
            "ST-017",
            not bad_dependencies,
            "; ".join(bad_dependencies) if bad_dependencies else "goal dependencies valid",
        )

        unlinked = [
            ticket.get("id", "")
            for ticket in self.state.get("tickets", [])
            if ticket.get("status") in {
                "Ready", "In Progress", "Blocked", "In Review", "Done",
            }
            and ticket.get("goal") not in goal_map
        ]
        self.record(
            "ST-018",
            not unlinked,
            "unlinked executable tickets: " + ", ".join(unlinked)
            if unlinked
            else "executable tickets link to goals",
        )

        missing_evidence = []
        for goal in goals:
            if goal.get("status") != "Done":
                continue
            paths = goal.get("evidencePaths", [])
            if not goal.get("completedAt") or not goal.get("resultSummary") or not paths or any(
                repository_path(path) is None or not repository_path(path).is_file()
                for path in paths
            ):
                missing_evidence.append(goal.get("id", ""))
        self.record(
            "ST-019",
            not missing_evidence,
            "completed goals missing evidence: " + ", ".join(missing_evidence)
            if missing_evidence
            else "completed goal result summaries and evidence present",
        )

    def ownership_and_baton(self) -> None:
        active = self.state.get("activeWork", [])
        overlaps: list[str] = []
        claimed: list[tuple[str, str]] = []
        for item in active:
            owner = item.get("owner", "")
            for raw_scope in item.get("scopes", []):
                scope = raw_scope.rstrip("/")
                for other_scope, other_owner in claimed:
                    if owner != other_owner and (scope == other_scope or scope.startswith(other_scope + "/") or other_scope.startswith(scope + "/")):
                        overlaps.append(f"{other_owner}:{other_scope} <> {owner}:{scope}")
                claimed.append((scope, owner))
        self.record("ST-020", not overlaps, "; ".join(overlaps) if overlaps else "active scopes exclusive")

        baton = self.state.get("baton", {})
        baton_ok = all(isinstance(baton.get(key), str) and baton[key].strip() for key in ["owner", "action", "returnTrigger"])
        self.record("ST-021", baton_ok, json.dumps(baton, ensure_ascii=False) if not baton_ok else f"owner={baton.get('owner')}")

        bad_active = [item.get("ticket", "") for item in active if not item.get("owner") or not item.get("scopes") or not item.get("status") or not item.get("returnDestination")]
        self.record("ST-022", not bad_active, "incomplete active records: " + ", ".join(bad_active) if bad_active else "active baton fields complete")

        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
        self.record("ST-023", ".artifacts/" in ignore, ".artifacts/ ignored" if ".artifacts/" in ignore else ".artifacts/ missing from .gitignore")

    def secret_hygiene(self) -> None:
        bad_names: list[str] = []
        bad_content: list[str] = []
        secret_names = {".env", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"}
        for file in ROOT.rglob("*"):
            if not file.is_file() or ".git" in file.parts or ".artifacts" in file.parts:
                continue
            if file.name in secret_names or file.suffix in {".pem", ".key", ".p12", ".pfx"}:
                bad_names.append(str(file.relative_to(ROOT)))
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                bad_content.append(str(file.relative_to(ROOT)))
        self.record("ST-030", not bad_names and not bad_content, f"secret-like names={bad_names}, content={bad_content}" if bad_names or bad_content else "no obvious committed secrets")

    def template_hygiene(self) -> None:
        registry = (ROOT / "docs/thread-registry.md").read_text(encoding="utf-8")
        unresolved = re.findall(r"<(?:configure|optional)>", registry)
        template_mode = self.state.get("templateMode") is True
        strict_ok = not unresolved and not template_mode
        self.record("ST-031", strict_ok if self.strict else True, f"strict unresolved={len(unresolved)}, templateMode={template_mode}" if self.strict else "template placeholders allowed")
        self.record("ST-032", isinstance(self.state.get("templateMode"), bool), f"templateMode={self.state.get('templateMode')}")

    def provider_consistency(self) -> None:
        state_provider = self.state.get("project", {}).get("agentProvider")
        metadata_provider = self.metadata.get("provider")
        source = self.metadata.get("source", {})
        source_channel = source.get("channel") if isinstance(source, dict) else None
        metadata_ok = (
            self.metadata.get("schemaVersion") == 2
            and isinstance(self.metadata.get("harnessVersion"), str)
            and bool(self.metadata.get("harnessVersion"))
            and isinstance(source, dict)
            and source.get("repository") == "FabienGreard/agentic-project-harness"
            and source_channel in {"unreleased-template", "local-development", "stable"}
        )
        provider_ok = state_provider == "codex" and metadata_provider == "codex" and metadata_ok
        self.record(
            "ST-033",
            provider_ok,
            f"state={state_provider}, metadata={metadata_provider}, sourceChannel={source_channel}" if not provider_ok else "Codex provider metadata agrees",
        )

        if self.metadata.get("installationStatus") == "Template":
            self.record("ST-034", True, "template role defaults accepted")
            return

        expected = self.metadata.get("reasoning", {})
        file_map = {
            "management": [".codex/agents/management.toml"],
            "operations": [".codex/agents/operations.toml"],
            "contractors": [".codex/agents/contractor.toml"],
            "internalAudit": [".codex/agents/internal-audit.toml"],
            "consultants": [
                str(item.get("configPath"))
                for item in self.state.get("team", {}).get("consultants", [])
                if isinstance(item, dict) and item.get("status") == "active"
            ],
        }
        mismatches: list[str] = []
        for role, relatives in file_map.items():
            intended = expected.get(role)
            if intended is None:
                mismatches.append(f"{role}: missing metadata reasoning")
                continue
            for relative in relatives:
                path = ROOT / relative
                if not path.is_file():
                    mismatches.append(f"{role}: missing {relative}")
                    continue
                text = path.read_text(encoding="utf-8")
                match = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', text, re.MULTILINE)
                actual = match.group(1) if match else "inherit"
                if actual != intended:
                    mismatches.append(f"{role}: metadata={intended}, {relative}={actual}")
        self.record("ST-034", not mismatches, "; ".join(mismatches) if mismatches else "installed role reasoning matches metadata")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail template placeholders and templateMode for customized projects")
    parser.add_argument("--json", action="store_true", help="Emit JSON rather than text")
    args = parser.parse_args()

    evaluator = Evaluator(strict=args.strict)
    evaluator.run()
    failed = [finding for finding in evaluator.findings if not finding.ok]

    if args.json:
        print(json.dumps({"verdict": "FAIL" if failed else "PASS", "strict": args.strict, "findings": [asdict(item) for item in evaluator.findings]}, indent=2, ensure_ascii=False))
    else:
        for finding in evaluator.findings:
            print(f"{'PASS' if finding.ok else 'FAIL'} {finding.check} {finding.evidence}")
        print(f"\n{'FAIL' if failed else 'PASS'}: {len(evaluator.findings) - len(failed)}/{len(evaluator.findings)} checks passed")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
