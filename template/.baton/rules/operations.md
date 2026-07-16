# Deterministic operations

Baton exposes canonical schema-versioned JSON for coordination, Markdown for intent and rationale, and generated human-readable views. Agents may inspect evidence and execute authorized validated operations. Humans retain consequential authority. Operational tools fail closed, preserve user-owned files, and leave provenance and recovery evidence.

Validate with `.baton/bin/baton doctor check` and use only documented schema-defined transitions. The stable installer acquires or updates Baton; `boot`, `control`, `roster`, `terminal`, `upgrade`, `doctor`, and `scrap` are the complete public management CLI. Their matching skills never call private engines.

Install or update only from approved stable release assets and immutable provenance. Require the origin full commit and manifest digest before comparing the recorded baseline, local State, and target. Modified managed files, ambiguous provenance, unsupported baselines, unsafe paths, and incomplete external transactions block. Updates are atomic and serialize through the shared per-Repository lock.

Adoption into a non-empty repository is additive: never overwrite, rename, delete, stage, or commit project-owned files. Preserve legacy records during supported migration. Generated cleanup guidance names checksums, preserved paths, manual actions, rollback, immutable links, and validation; deletion remains human-authorized. Never update from a moving branch, guess a merge, silently delete legacy material, remove transaction backups, or create another maintenance control plane.

Public skill discovery is all-or-nothing: an occupied short skill name that is not Baton's exact link blocks installation. `scrap` requires an immutable reviewed plan, exact current-tree verification, an external backup, and rollback; it never deletes that backup or a preserved collision.

Generated Markdown and dashboards are views, not authority. Availability of a command or generated artifact is not evidence that its behavior works; verify the exact candidate and recovery path.
