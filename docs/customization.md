# Customize without breaking the operating layer

## Keep common names stable

Users and repository rules speak about Management, Operations, Consultants, Contractors, and Internal Audit. The selected preset supplies professional context—such as Game Director or Product Manager—but does not create a second vocabulary or change authority.

Do not rename generated common-role files by hand. If project prose uses a professional title, include its common name at the first mention: “Game Director (Management)” or “Producer (Operations).” Contractor capability labels are routing hints, not mandatory conversational names.

## Choose a preset, then hire expertise

The supported project presets are exactly Game Development, Software Product, Business Operations, and Research. They are deliberately opinionated; there is no generic Other/custom preset.

Consultants are the extension point. Invoke `$hire-consultant` for a recurring domain that defines readiness or accepts evidence. Prefer the preset catalog. If none fits, the skill prepares a JSON definition matching `docs/schemas/consultant.schema.json` and passes it to the internal deterministic team engine. Do not invoke the mutation engine directly from user workflows.

A custom Consultant must use lowercase hyphen-case for its ID and define title, headline, domain, non-empty readiness requirements, non-empty evidence requirements, and acceptance authority. It automatically inherits the fixed exclusions: no overall priority, Contractor dispatch, technical integration, or publication authority.

Do not hire a permanent Consultant for one bounded implementation or one-off question; Operations can dispatch a disposable Contractor. Any number of Consultants may be active when their domains are distinct.

Invoke `$fire-consultant` to offboard an active Consultant. Never delete its state record or config manually. The skill uses the same engine to preserve history and modified configs and remove only an unchanged generated config.

## State and dashboard

Keep `.agent-harness.json` as installation/provenance metadata, canonical JSON under `docs/state/` as operational state, Markdown as narrative context, and generated `docs/index.html` as a view. Do not add another updater or maintenance-state hierarchy.

Prepare schema-valid operations for `python3 tools/harness_state.py apply`; do not hand-edit the dashboard. `docs/state/team.json` is updated only by installation and the deterministic team engine. Run both checks after a material change:

```sh
python3 tools/harness_team.py check --json
python3 tools/harness_state.py check --json
```

For dashboard design review only, open `docs/index.html?mock=1`. Mock data is illustrative and never project evidence.

## Balance pace and assurance

Set the project default in `project.assuranceDefaults`, then resolve `assurance` explicitly on every ticket. The generated default is `Standard` test rigor with no universal human review stage. Use `Lean` for a smaller focused proof boundary and `Thorough` for broader failure-path and operational evidence.

Human review timing is an explicit list: `Readiness`, `Acceptance`, and/or `Release`. An empty list means explicitly none. A ticket may differ from project defaults only with a human-authorized `overrideReason`; separately governing safety, legal, compliance, irreversible-action, and publication approvals remain mandatory. Apply changes transactionally through a schema-valid state operation, then use the dashboard to inspect each ticket's resolved rigor and review timing.

This structure is LLM-first and human-governed. Optimize IDs, schemas, commands, reports, and links for reliable machine use while retaining human authority for intent, ambiguity, destructive actions, external commitments, security/compliance, and release or publication.

## Rules, skills, and Codex settings

`AGENTS.md` remains a navigation map. Put normative instructions in `.agents/rules/` using the shared template. Project skills live once under `.agents/skills/` and are discovered through the relative `.codex/skills` symlink. Preserve attribution when adapting skill material.

Keep the project-scoped `.codex/config.toml` semantic contract unless an approved governance change replaces it: on-request approvals, automatic approval review, workspace-write sandboxing, network access, `max_threads = 4`, and `max_depth = 1`. Four threads is a ceiling; depth one preserves the shallow Operations dispatch topology. App or workspace policy can still restrict Auto-review, and already-running conversations can retain their selected permission mode.
