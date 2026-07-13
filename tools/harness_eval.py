#!/usr/bin/env python3
"""Dependency-free, read-only static checks for Agentic Project Harness."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STATUSES = {
    "Queued",
    "In Progress",
    "Dispatched",
    "Blocked",
    "Integration",
    "Verification",
    "In Review",
}
REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "docs/overview.md",
    "docs/direction.md",
    "docs/backlog.md",
    "docs/active-work.md",
    "docs/project-state.json",
    "docs/workflow.md",
    "docs/thread-registry.md",
    "docs/roles/project-director.md",
    "docs/roles/delivery-lead.md",
    "docs/roles/specialist-lead.md",
    "docs/roles/execution-worker.md",
    "docs/roles/harness-evaluator.md",
    "docs/roles/worker-task-template.md",
    "docs/evals/harness/rubric.md",
]
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERNS = [
    re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


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

    def record(self, check: str, ok: bool, evidence: str) -> None:
        self.findings.append(Finding(check, ok, evidence))

    def run(self) -> None:
        self.required_files()
        self.markdown_links()
        self.json_files()
        self.text_integrity()
        if self.state:
            self.ticket_state()
            self.ownership_and_baton()
            self.template_hygiene()
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
        for relative in [
            "docs/project-state.json",
            "docs/schemas/project-state.schema.json",
            "docs/evals/harness/report-schema.json",
        ]:
            try:
                parsed = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                if relative == "docs/project-state.json":
                    self.state = parsed
            except (OSError, json.JSONDecodeError) as error:
                failures.append(f"{relative}: {error}")
        self.record("ST-003", not failures, "; ".join(failures) if failures else "state and schemas parse")

    def text_integrity(self) -> None:
        problems: list[str] = []
        text_suffixes = {".md", ".json", ".yml", ".yaml", ".py", ".txt"}
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

    def ticket_state(self) -> None:
        tickets = self.state.get("tickets", [])
        ticket_map = {ticket.get("id"): ticket for ticket in tickets}
        ids = [ticket.get("id") for ticket in tickets]
        paths_missing = [ticket.get("path", "") for ticket in tickets if not (ROOT / ticket.get("path", "")).is_file()]
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

        mismatches = [item.get("ticket", "") for item in active if item.get("ticket") in ticket_map and ticket_map[item["ticket"]].get("status") != item.get("status")]
        self.record("ST-013", not mismatches, "status mismatch: " + ", ".join(mismatches) if mismatches else "ticket and active status agree")

        unready: list[str] = []
        for ticket in tickets:
            if ticket.get("status") == "Ready":
                incomplete = [dependency for dependency in ticket.get("dependencies", []) if ticket_map.get(dependency, {}).get("status") != "Completed"]
                if incomplete:
                    unready.append(f"{ticket.get('id')}: {','.join(incomplete)}")
        self.record("ST-014", not unready, "; ".join(unready) if unready else "Ready dependencies completed")

        missing_reports: list[str] = []
        for ticket in tickets:
            if ticket.get("status") == "Completed":
                report = ticket.get("reportPath", "")
                if not report or not (ROOT / report).is_file():
                    missing_reports.append(ticket.get("id", ""))
        self.record("ST-015", not missing_reports, "missing reports: " + ", ".join(missing_reports) if missing_reports else "Completed ticket reports present")

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
