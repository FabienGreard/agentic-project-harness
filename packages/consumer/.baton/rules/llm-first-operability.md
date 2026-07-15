# LLM-first Operability, Human-governed Authority

Title:
LLM-first Operability, Human-governed Authority

Type:
Rule

Purpose:
Make operational work legible and actionable to an LLM while preserving human authority over consequential decisions.

Scope:
Installation, adoption, updates, migrations, operational state, generated guidance, cleanup, rollback, and external transactions.

Definition:
Baton exposes a small, deterministic operational surface: canonical schema-versioned JSON for coordination state, narrative Markdown for intent and rationale, and generated human-readable views. LLMs may inspect evidence, propose or apply validated state operations, and generate copy-ready guidance within approved commands. Humans retain authority for intent, unresolved ambiguity, destructive deletion, external commitments, security or compliance decisions, and publication. Operational tooling must fail closed, preserve user-owned files, and leave auditable provenance and recovery evidence rather than creating a second maintenance control plane.

How to Apply:

1. Load the canonical operational JSON and validate it with `.baton/bin/baton _state check` before relying on it.
2. Use the documented `apply` operation only for an authorized, schema-defined state transition; keep narrative direction, decisions, and reports in Markdown.
3. For installation, adoption, update, migration, or rollback, inspect local status and the recorded `.baton/metadata.json` provenance before proposing a change.
4. Treat modified managed files, ambiguous provenance, unsupported baselines, and incomplete external transactions as blockers; preserve evidence and return the smallest authorized next action.
5. Generate cleanup instructions from exact local and immutable GitHub evidence, and require a human decision before any deletion.

Do:

- Use one stable release `install.sh` bootstrap lifecycle and the installed `.baton/bin/baton status`, `update`, and `check` commands.
- Install and update only from approved stable GitHub release assets and immutable recorded provenance.
- Keep updates atomic: require the origin's full commit and manifest digest before planning from the recorded baseline, current local state, and target release; preserve external transaction backups and documented rollback recovery.
- Support non-empty repositories only through additive Adoption mode; never overwrite, rename, delete, stage, or commit user files.
- Record installation version, stable provenance, ownership classes, checksums, status, and migrations in `.baton/metadata.json`.
- Preserve legacy source records during a one-time supported migration and verify the official stable-release baseline before reconstructing provenance.
- Include exact checksums, preserved paths, manual actions, rollback paths, release/diff/file links, validation commands, and the human deletion boundary in generated LLM cleanup prompts.

Don't:

- Treat generated Markdown, an LLM response, or a message as canonical operational state.
- Update from a moving branch, prerelease, development build, or unverified fork.
- Guess provenance, resolve a three-way conflict automatically, silently delete legacy material, or delete transaction backups.
- Let an LLM authorize product intent, external commitments, publication, destructive actions, or security/compliance decisions.
- Add another updater or repository-maintenance control plane.

Example:

- In a non-empty repository, an LLM runs local status, finds no conflicting managed path, proposes additive Adoption mode from a stable release asset, and returns the generated cleanup prompt for human review; it does not remove any pre-existing file.

Validation:
The state tool validates canonical JSON, the generated dashboard reflects that state, `.baton/metadata.json` supplies verifiable provenance and recovery evidence, and every consequential action remains at its authorized human or role boundary.

References:

- `.baton/guide.md`
- `.baton/integration/README.md`
- `.baton/workflow.md`
- `.baton/roles/contractor.md`

Notes:

- This rule defines the Baton v0.6 operational contract. Availability of a command, migration, generated dashboard, or release asset still requires its own implementation and verification evidence.
