# Customize Baton without taking over the project

Baton separates product-managed runtime from project-owned intent. Customize through the supported ownership boundary; do not fork Baton's lifecycle inside the consuming repository.

## Know which layer you are changing

| Layer | Examples | Change path |
| --- | --- | --- |
| Baton-managed runtime | `.baton/bin/`, `.baton/lib/`, rules, schemas, shared roles, shared skills | Stable Baton update only |
| Generated config | `.baton/agents/*.toml`, `.baton/dashboard/index.html`, `.baton/thread-registry.md`, generated config proposal | Team/state/memory tools or activation/update |
| Project-owned Baton content | direction, goals, tickets, decisions, PRDs, reviews, implementation reports, active team choices, company memory | Validated project workflow or `$memory` |
| Narrow integration | Baton block in `AGENTS.md`, project Codex config registration, individual skill links | Installer/activation plus manual collision review |
| Surrounding project | identity, source, root docs, `VERSION`, package manifests, license, `.github/`, tests, tools, release system | Project owners only |

`.baton/metadata.json` records the exact ownership and baseline of installed paths. Do not hand-edit managed checksums, provenance, installation status, transaction IDs, cleanup candidates, or ownership classes to make a check pass.

## Keep role authorities stable

Project prose may use professional personas such as Product Manager or Game Director, but the common authority names remain Management, Operations, Consultants, Contractors, and Internal Audit. Include the common name when ambiguity is possible: “Game Director (Management)” or “Producer (Operations).”

Do not create a parallel dispatch role. Management owns outcomes and readiness; Operations alone dispatches and revises Contractor work; Consultants define and accept only their approved domains; Contractors execute bounded assignments; Internal Audit independently evaluates Baton behavior.

## Extend expertise with Consultants

The supported presets are Software Product, Game Development, Business Operations, and Research. A preset selects professional context, reasoning defaults, a finite Consultant catalog, and a Contractor capability bench. It does not change authority.

Use the project skills for recurring expert domains:

```text
$hire-consultant
$fire-consultant
```

`$hire-consultant` can select a preset Consultant or prepare a custom definition that matches `.baton/schemas/consultant.schema.json`. A custom Consultant needs a unique lowercase hyphen-case ID, title, headline, domain, readiness requirements, evidence requirements, and acceptance authority. Every Consultant keeps the fixed non-authorities: no overall priority, Contractor dispatch, technical integration, or publication.

`$fire-consultant` marks the Consultant inactive and preserves history. It removes only an unchanged generated agent config. A modified config is retained with an exact manual action.

Do not hire a permanent Consultant for one implementation or one-off question; Operations can use a disposable Contractor. Multiple Consultants are valid when their recurring acceptance domains are distinct.

## Change project state transactionally

Canonical project records live under `.baton/state/`. Narrative intent and evidence live in `.baton/docs/`, `.baton/decisions/`, `.baton/prds/`, `.baton/review-packets/`, and `.baton/implementation-reports/`.

Use the public check before relying on state:

```sh
.baton/bin/baton check --json
```

Use Baton's role and skill workflows for authorized state and team changes; their deterministic mutation plumbing is intentionally not a public CLI. Apply one schema-valid state transition at a time and keep project, goals, tickets, ownership, reviews, team, narrative evidence, and the generated dashboard consistent.

Never hand-edit `.baton/dashboard/index.html` or `.baton/thread-registry.md`. They are generated local views; memory and team transactions refresh them together when task or personnel state changes.

## Manage company memory through one skill

Current company, user, and coworker memory lives in `.baton/memory/memory.json`; the value-minimized company chronology lives in `.baton/memory/history.jsonl`. The files are project-owned and inspectable, but accepted mutation, redaction, revision, and cross-record behavior belongs to `$memory` and its hidden deterministic writer.

Use `$memory` to remember, inspect, confirm or reject a candidate, correct, forget, or explicitly retrieve more context. Do not add a second memory command, global store, import/sync layer, transcript archive, personnel database, or project-management mirror. Tickets, PRDs, decisions, ownership, approvals, and evidence remain authoritative in their existing records; memory may link to them without copying their contents.

Only confirmed claims can enter automatic role briefings. The automatic packet is selected for the role and assignment and stops at 10 claims or the conservative 600-token budget. Candidates, superseded claims, raw history, old reviews, inactive coworkers, and assignment text already present are excluded. Explicit retrieval does not silently enlarge future automatic packets.

Forgetting removes the active value, clears matching candidates, redacts matching local chronology values, refreshes generated views, and returns an external report and rollback location. Baton warns that earlier Git commits and retained external backups may still contain the value; it never rewrites Git history or deletes backups automatically.

Names and bounded professional working styles may be edited through the supported memory flow. Stable IDs, generation seeds, task registrations, employment history, and evidence links must remain coherent. Permanent Management, Operations, or Consultant seat replacement requires explicit user approval; Operations may select and replace disposable Contractors inside approved delivery work.

## Tune assurance explicitly

The project record defines `assuranceDefaults`. Every ticket still records its resolved `assurance`:

- `Lean` gives focused changed-behavior proof plus explicit ticket verification.
- `Standard` adds affected regression and applicable runtime or operational evidence.
- `Thorough` adds broader regression, negative/failure paths, and applicable operational or experiential evidence.

Human review is an explicit subset of `Readiness`, `Acceptance`, and `Release`; `[]` means none. A ticket that differs from project defaults requires a human-authorized `overrideReason`. Safety, legal, compliance, irreversible-action, and publication gates cannot be waived by a lower test-rigor label.

Readiness gates execution, Acceptance gates `Done`, and Release remains a separate publication boundary.

## Keep project and Baton versions separate

`batonVersion` identifies the installed Baton runtime and comes from immutable stable provenance. `projectVersion` is optional project information and may remain `null`.

Do not rename, replace, or repurpose a root `VERSION`, package manifest, Git tag, or domain-specific release record for Baton. Conversely, do not set `batonVersion` from project data. If the project later integrates `projectVersion`, use an approved supported transition; do not hand-edit metadata.

## Preserve root integrations

### `AGENTS.md`

Keep project instructions outside Baton's marked block. Baton owns only the content between `<!-- BATON:START -->` and `<!-- BATON:END -->`. Nested project `AGENTS.md` files remain project-owned and continue to scope local instructions.

### Codex config

When the project already owns `.codex/config.toml`, Baton preserves it and writes `.baton/integration/codex-config.toml` as a merge proposal. Merge semantically: retain project settings, register the needed `.baton/agents/*.toml` files, and resolve any permission difference deliberately. Do not replace the project file wholesale.

The Baton base contract is:

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_mode = "workspace-write"

[agents]
max_threads = 4
max_depth = 1

[sandbox_workspace_write]
network_access = true
```

These are defaults in a trusted project config. The active permission selection, CLI overrides, closer configs, profiles, and managed requirements may take precedence. Auto-review changes the reviewer for eligible requests, not the sandbox boundary. Workspace-write may still protect `.git/` and `.codex/`; command network access does not grant browser, connector, app, Computer Use, account, or publication access. Subagents inherit the parent turn's live permission mode.

See OpenAI's [project config](https://learn.chatgpt.com/docs/config-file/config-advanced#project-config-files-codexconfigtoml), [sandbox](https://learn.chatgpt.com/docs/sandboxing), and [Auto-review](https://learn.chatgpt.com/docs/sandboxing/auto-review) documentation.

### Skill discovery

The source of truth is `.baton/skills/<name>`. Codex discovers supported Baton skills through individual `.agents/skills/<name>` links. Preserve any collision and decide manually whether to keep the existing project skill, rename project-owned content, or add a different approved discovery path. Do not create a duplicate skill tree or root `.codex/skills` link.

## Treat mature-adoption artifacts as quarantine

While `.baton/metadata.json` says `Needs Integration`, nothing in `.baton/integration/starter/` is authoritative. Build a separate non-template proposal from verified mature-project facts, review it, and use the generated `.baton/bin/baton _activate --from PATH` handoff only after human confirmation.

Activation does not authorize cleanup. Keep starter material, legacy records, transaction reports, and backups until a human reviews the direct GitHub compare/file links and approves exact archival or deletion candidates.

## Source-repository changes

Contributors changing Baton itself work in this normal source/product repository. The root `.baton/` belongs to Baton's own project and must never become consumer content. Consumer runtime changes originate under `template/.baton/`.

Consumer runtime changes belong under `template/.baton/`. Files there are shared by default; starter state and the adoption-only integration guide follow the explicit path conventions documented in [Architecture](architecture.md). The release builder rejects any consumer source elsewhere under `template/` and records the exact projected files in the generated manifest.

Do not place consumer source at repository root to make packaging easier. `scripts/`, tests, docs, release files, and the source evaluator are outside the only eligible payload root and cannot appear in either consumer archive. The release builder publishes `scripts/install.sh` as the separate top-level installer asset without installing it into projects.

See [Architecture](architecture.md) for projection-to-payload mapping and [Releasing](releasing.md) for candidate verification.
