# Customization

Change Project intent and team choices without forking Baton.

## Ownership layers

| Layer | Examples | Change with |
| --- | --- | --- |
| Baton-managed | runtime, rules, schemas, shared roles and skills | `$upgrade` |
| Generated | role config, dashboard, team task view | Baton skills |
| Project-owned | State, scoped Records, Memory | `$control` and the Project workflow |
| Host integration | marked `AGENTS.md` block, provider config, skill links | Installer/activation plus collision review |
| Repository | source, root docs, versioning, CI, license, releases | Project owners |

`.baton/metadata.json` records path ownership and baselines. Never hand-edit it or a generated view to make validation pass.

## Team

Stable authority names are Management, Operations, Consultants, Contractors, and Internal Audit. Presets add professional context, not authority.

Use:

```text
$roster
```

`$roster` shows the current team before making changes. Add a Consultant only for recurring expertise and acceptance. Use a disposable Contractor for bounded work. Custom Consultants must satisfy `.baton/schemas/consultant.schema.json` and never gain Management or Operations authority.

Offboarding preserves history and removes only an unchanged generated config. Modified files remain for human review.

## State and protocols

Approved direction and coordination live under `.baton/state/`. Project-wide Records use `.baton/records/PROJECT/`; Goal and Ticket Records use `.baton/records/<GOAL-ID>/` and `.baton/records/<TICKET-ID>/`.

Invoke `$control` to inspect or change Project controls. It shows the current values and validates any human-approved update.

Each Ticket selects one Readiness Protocol:

- `Waived`: explicitly unverified;
- `Field Check`: focused proof of the change;
- `Standard Protocol`: Field Check plus affected regression and runtime proof; or
- `Full Certification`: broader regression, failure-path, and operational proof.

Each Goal and Ticket also selects one Clearance Protocol:

- `Autonomous`: no routine Clearance;
- `Release Clearance`: approve the completed Goal before release;
- `Completion Clearance`: also approve each completed Ticket; or
- `Continuous Clearance`: also approve Goal and Ticket readiness.

An override needs human authority and a reason. See [language](../template/.baton/language.md) and [workflow](../template/.baton/workflow.md) for exact rules.

## Company Memory

Memory is an internal service used by `$boot`, `$roster`, and role workflows. It has no public skill. Do not edit Memory files or create another store. Advanced users can use the privacy-filtered commands in the [CLI reference](cli.md).

Automatic briefings contain only confirmed, relevant claims: at most 10 claims and 1,800 UTF-8 bytes. Memory can link to State, Records, and Evidence but never replaces them. Forgetting cannot erase Git history, remotes, clones, caches, or backups.

## Host integration

Baton owns only its marked block in root `AGENTS.md`. Surrounding instructions and nested maps remain project-owned.

During mature adoption, Baton may place a provider-config proposal under `.baton/migration/`. Later `$roster` conflicts preserve the Repository config and return a checksummed proposal. Skill links are created only when every target path is free; a collision stops the change.

## Contributing to Baton

Consumer runtime source belongs only under `template/.baton/`. Root `.baton/` is Baton's own control plane and is never shipped. Public docs, scripts, tests, evaluator material, and release tooling stay source-only.

Next: [Architecture](architecture.md).
