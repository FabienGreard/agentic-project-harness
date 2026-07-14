# Preserve Repository Integrity and Existing Work

Title:
Preserve Repository Integrity and Existing Work

Type:
Rule

Purpose:
Prevent accidental loss, overlap, secret exposure, destructive operations, and unusable output.

Scope:
Every edit, generated artifact, command, ownership transfer, verification action, and Git operation.

Definition:
Agents preserve unrelated work, respect registered ownership, modify only authorized boundaries, and leave the repository functional. Destructive operations and publication require explicit authority.

How to Apply:

1. Inspect branch, worktree status, relevant diff, and ownership before editing.
2. Separate the assigned boundary from unrelated changes.
3. Make the narrowest required edits.
4. Review the resulting diff and verify proportionally.
5. Stage, commit, push, tag, or publish only with explicit authority.

Do:

- Treat a dirty worktree as evidence to preserve and understand.
- Keep staging intentional and secrets outside versioned files.
- Stop only the affected scope when unexpected overlap appears.

Don't:

- Discard, overwrite, clean, or rewrite unrelated work.
- Modify another owner's path.
- Commit, publish, or force-update history without authorization.

Example:

- A Contractor adds files within its registered directory while leaving unrelated modified documentation byte-for-byte unchanged.

Validation:
The final diff contains only intended paths, unrelated work remains intact, no secret is introduced, and checks pass.

References:

- `docs/state/ownership.json`
- `docs/workflow.md`
- `.gitignore`

Notes:

- A dirty worktree is not a failure; an unexplained destructive action is.
