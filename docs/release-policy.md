# Baton release policy

Baton releases are stable-only, human-authorized, immutable, and reproducible. Technical completion does not authorize a tag, push, GitHub release, latest-release redirect, or any other release publication action. BATON-001's separately authorized repository rename to Baton and conversion out of template mode are complete; those repository setting changes are not release authorization.

## Current boundary

Version `0.6.0` in this checkout is an unpublished candidate. BATON-001 explicitly excludes publication. Its code, docs, tests, and local artifacts may be prepared and verified, but they must return to Management for a separate human `Release` decision.

Until that decision and publication succeed, [Agentic Project Harness v0.5.0](https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.5.0) remains the latest published stable release. Do not make the README's future `FabienGreard/baton` install URL appear usable early.

## Stable channel only

- Publish one stable semantic version and matching `v<version>` tag from one exact full commit.
- Never use a branch archive, draft, prerelease, development checkout, mutable fork, or local candidate as an install/update origin.
- Do not publish a prerelease to test the stable updater. Use local release-directory fixtures and source smokes instead.
- Never replace an immutable release asset in place. Correct a bad candidate before release or issue a new version after release.
- `releases/latest` may point to the new version only after all stable assets exist and immutable remote smoke passes.

## Human authority

Management owns release readiness and presents the exact candidate, verification evidence, limitations, and independent review. A declared human `Release` review is the publication gate.

Approval must identify the candidate commit and intended stable version. General permission to continue development, tolerate worktree drift, merge, or prepare artifacts is not publication approval.

Operations may integrate and verify the candidate but does not publish merely because checks pass. Contractors, Consultants, and Internal Audit cannot authorize publication.

## Source and payload integrity

Every tracked source file has exactly one committed class: `source-only`, `template-only`, `adoption-runtime`, or `shared`. Missing, stale, or policy-inconsistent classification blocks the build.

The release builder must start from a clean committed source tree and produce exactly five uploaded assets:

- `install.sh`
- `baton-new-project.tar.gz`
- `baton-adoption.tar.gz`
- `baton-manifest.json`
- `SHA256SUMS`

Both payload archives contain only `.baton/` entries generated from `packages/consumer/`. This repository's root `.baton/`, product identity, docs, tests, tools, evaluator, examples, legal/community files, version history, and release machinery remain source-only.

The manifest binds the version/tag, official repository, full candidate commit, source-classification digest, state schema, supported origins, exact payload path lists, source paths, file classes, kinds, and checksums. `SHA256SUMS` binds the installer, both archives, and manifest.

## Upgrade origins and history

Only reviewed stable releases may appear as automatic upgrade origins. Each origin uses a full commit SHA. Origins with a release-manifest contract also require that manifest's exact SHA-256.

Historical evidence must remain intact:

- preserve prior `CHANGELOG.md` sections, tags, release pages, commits, and asset checksums;
- do not rewrite Agentic Project Harness history as though it had always been Baton;
- do not invent a v0.4.0 stable release—none was published; and
- treat v0.4 compatibility as a migration fixture, not a stable manifest origin.

## Consumer safety

A release blocks unless verification proves:

- empty-project installation activates valid starter state without a commit;
- mature adoption preserves project identity, `VERSION`, licensing/community files, `.github/`, docs, source, tests, tools, releases, existing governance, and unrelated dirty work;
- starter state stays quarantined until reviewed activation;
- existing `AGENTS.md`, Codex config, and skill collisions are preserved under their specific contracts;
- `batonVersion` comes only from immutable Baton provenance while `projectVersion` remains separate;
- supported v0.2-v0.5 migration preserves all legacy paths and backups;
- modified managed files, unsafe paths, ambiguous provenance, checksum mismatch, and concurrent conflicts fail closed; and
- ignored root/nested vendor trees do not create false consumer failures.

## Cleanup and rollback

Retired or legacy paths are cleanup candidates, never automatic deletions. Every update/adoption report must retain exact paths and checksums, backup/transaction locations, stable release evidence, an immutable direct GitHub comparison, and direct target-file links.

Only a human may approve archival or deletion after validation. `--yes`, activation, update success, an LLM recommendation, or release approval does not authorize deletion of project-owned files, legacy evidence, or transaction backups.

Rollback must restore every touched project path or report exact recovery failures. External transaction evidence remains available after success and failure.

## Publication acceptance

Publication is accepted only when:

1. the exact clean committed candidate passes the full verification matrix;
2. source classification and both payload manifests validate with zero drift;
3. two-axis review and independent disposable Internal Audit have no blocking finding;
4. Management presents exact evidence and the human `Release` review approves the candidate;
5. the matching tag and GitHub release contain all five checksum-matched assets;
6. immutable-commit remote installation/adoption/update smoke passes; and
7. public tag, release, assets, checksums, and latest-stable redirect are verified.

See [Stable release procedure](releasing.md) for commands and the explicit no-publication checkpoint.
