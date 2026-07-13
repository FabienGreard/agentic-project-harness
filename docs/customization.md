# Customizing the harness

## Rename roles without changing authority

Examples:

| Generic | Software/game | Business/operations | Research |
| --- | --- | --- | --- |
| Project Director | Game/Product Director | Program Sponsor | Principal Investigator |
| Delivery Lead | Production/Engineering Lead | Operations Lead | Research Operations Lead |
| Specialist Lead | Art/Security/Data Lead | Finance/Legal/Compliance Lead | Methods/Ethics Lead |
| Execution worker | Engineer/artist/tester | Analyst/operator | Researcher/data worker |

Keep one dispatch center even when names change.

The starter `.codex/config.toml` uses on-request approvals with `approvals_reviewer = "auto_review"`, workspace-write sandboxing, and network access within that sandbox. It uses `max_threads = 4` as a ceiling, not a worker target. Keep `max_depth = 1` to prevent recursive worker fan-out and preserve Delivery as the single dispatch center. A Codex execution surface may impose a lower concurrency cap, **Approve for me** / Auto-review may be restricted by app or managed-workspace policy, and existing conversations may retain their selected permission mode.

## Discover rules and skills

`AGENTS.md` is the navigation map; keep normative instructions in `.agents/rules/` using the existing common section template. The generic skills live in `.agents/skills/` and are discovered through `.codex/skills`, a relative symlink that must remain the only discovery copy. Keep the three skill names and their metadata/support notice intact unless a deliberate governance change is reviewed.

## Add gates proportionally

Use Specialist readiness and human approvals only where judgment, impact, or irreversibility justifies them. Too few gates create unsafe invention; too many convert orchestration into ceremony.

## Keep the harness small

- Prefer two permanent Leads initially.
- Keep the Specialist Lead dormant until a recurring authority boundary is approved, then rename and configure it for that domain.
- Use workers for execution and disposable evaluators for audits.
- Record project discoveries as tickets rather than continually expanding role prompts.
- Add a regression scenario before adding a broad new policy.
