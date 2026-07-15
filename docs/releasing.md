# Stable release procedure

Baton releases are stable-only and human-authorized. This procedure separates candidate preparation from publication.

> **BATON-001 stop boundary:** v0.6.0 is currently an unpublished candidate. The authorized source-repository rename to `FabienGreard/baton` and conversion out of GitHub template mode are complete. Complete local preparation and verification, then return the exact evidence to Management. Those repository setting changes do not authorize a push, merge, tag, release, asset upload, or change to `releases/latest`.

## Release policy

Baton releases are stable-only, human-authorized, immutable, and reproducible. Technical completion does not authorize a tag, push, GitHub release, latest-release redirect, or any other publication action.

### Current boundary and human authority

Version `0.6.0` in this checkout is an unpublished candidate. BATON-001 explicitly excludes publication. Until a separate human Release decision approves an exact commit and stable version, [Agentic Project Harness v0.5.0](https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.5.0) remains the latest published stable release and the future `FabienGreard/baton` install URL must not be presented as live.

Management owns release readiness and presents the exact candidate, evidence, limitations, and independent review. Operations may integrate and verify but does not publish merely because checks pass. Contractors, Consultants, and Internal Audit cannot authorize publication. General permission to continue, tolerate drift, merge, or prepare artifacts is not release authorization.

### Stable and immutable channel

- Publish one stable semantic version and matching `v<version>` tag from one exact full commit.
- Never use a branch archive, draft, prerelease, development checkout, mutable fork, or local candidate as an install or update origin.
- Never publish a prerelease to test the stable updater; use local release-directory fixtures and source smokes.
- Never replace a published asset in place. Correct a candidate before release or issue a new version afterward.
- Allow `releases/latest` to point to a new version only after all assets exist and immutable remote smoke passes.

### Source and payload integrity

Every tracked source file has exactly one committed class: `source-only`, `template-only`, `adoption-runtime`, or `shared`. Missing, stale, or policy-inconsistent classification blocks the build.

The release builder starts from a clean committed source tree and produces exactly five uploaded assets:

- `install.sh`, published from `scripts/install.sh`;
- `baton-new-project.tar.gz`;
- `baton-adoption.tar.gz`;
- `baton-manifest.json`; and
- `SHA256SUMS`.

Both archives contain only `.baton/` entries generated from `template/`. This repository's root `.baton/`, product identity, docs, scripts, tests, evaluator, legal/community files, version history, and release machinery remain source-only.

The manifest binds the version/tag, official repository, full candidate commit, source-classification digest, state schema, supported origins, exact payload path lists, source paths, file classes, kinds, and checksums. `SHA256SUMS` binds the installer, both archives, and manifest.

### Upgrade history

Only reviewed stable releases may appear as automatic upgrade origins, using a full commit SHA and, where the release-manifest contract exists, its exact SHA-256. Preserve prior changelog sections, tags, release pages, commits, and checksums. Do not rewrite Agentic Project Harness history as though it had always been Baton or invent a v0.4.0 stable release; v0.4 remains a migration fixture.

### Consumer safety, cleanup, and rollback

A release blocks unless verification proves empty-project installation, mature adoption preservation, quarantined starter state, collision-safe root integration, separate Baton/project versions, supported legacy migration without deletion, fail-closed unsafe or ambiguous states, and ignored/vendor-safe validation.

Retired and legacy paths are cleanup candidates, never automatic deletions. Reports retain exact paths and checksums, backup and transaction locations, stable evidence, immutable comparisons, and direct target-file links. Only a human may approve archival or deletion after validation; `--yes`, activation, update success, an LLM recommendation, or release approval does not authorize deletion. Rollback must restore every touched path or report exact recovery failures, and external transaction evidence remains available after success or failure.

### Publication acceptance

Publication is accepted only when:

1. the exact clean committed candidate passes the full verification matrix;
2. source classification and both payload manifests validate with zero drift;
3. two-axis review and independent disposable Internal Audit have no blocking finding;
4. Management presents exact evidence and the human Release review approves the candidate;
5. the matching tag and GitHub release contain all five checksum-matched assets;
6. immutable-commit remote installation, adoption, and update smoke passes; and
7. the public tag, release, assets, checksums, and latest-stable redirect are verified.

## 1. Pin the candidate contract

Before release-grade verification, confirm:

- `VERSION` contains exactly `0.6.0`;
- active product text says Baton while historical Agentic Project Harness evidence remains historically accurate;
- `CHANGELOG.md` has an unreleased v0.6.0 candidate section and all prior sections/links remain intact;
- root `.baton/` is Baton's source-repository control plane and cannot enter a consumer payload;
- consumer source exists only under `template/.baton/`;
- both payloads contain only `.baton/` paths;
- the stable-URL `install.sh` remains a release bootstrap asset and is not installed in consumers;
- the public installed CLI is exactly `status`, `update`, and `check`; and
- mature adoption activates only non-template reviewed state through `.baton/bin/baton _activate --from PATH` while starter state stays quarantined.

Review the exact source diff and exclude unrelated work. Release construction requires a clean committed source tree, but preparing docs or running pre-commit checks is not publication.

## 2. Regenerate and review source classification

Every tracked path must appear once in `release/source-classification.json` as `source-only`, `template-only`, `adoption-runtime`, or `shared`.

When tracked files change, regenerate from the staged candidate path set, review the result, and stage the classification again:

```sh
python3 scripts/release_bundle.py classify --source . --write
python3 scripts/release_bundle.py classify --source .
```

The second command must report zero drift. Verify especially that:

- root `.baton/`, `README.md`, `VERSION`, `CHANGELOG.md`, docs, `scripts/`, tests, evaluator, legal/community files, and release infrastructure are `source-only`;
- `template/.baton/integration/README.md` is `adoption-runtime`;
- starter state/narrative/report scaffolding is `template-only`; and
- shared runtime, rules, roles, schemas, skills, agents, and lifecycle code are `shared`.

Do not hand-classify a root source file into a payload. The builder enforces the approved source-layout policy.

## 3. Run the Thorough candidate matrix

Run the current repository commands recorded by BATON-001. At minimum, the accepted candidate must include passing evidence for:

```sh
.baton/bin/baton check --json
python3 scripts/harness_eval.py --strict
python3 tests/run_smokes.py
bash tests/install_smoke.sh
bash -n tests/install_remote_smoke.sh
git diff --check
```

Repeat `python3 tests/run_smokes.py` with Python 3.9. The focused suite owns the release bundle, local and piped installs, both interactive PTY paths, adoption, activation, updates, legacy migration fixtures, rollback, unsafe targets, concurrent locking, state/team behavior, evaluator regressions, and exact Codex semantics. The remote smoke is syntax-checked before publication and executed against the immutable tag only after all five assets are public.

The verification owner must also retain exact results for:

- fresh new-project install outside the source repository;
- mature non-empty adoption with forbidden root-path snapshots;
- non-template proposal review, quarantine, `_activate --from`, and post-activation checks;
- v0.2, v0.3, v0.4 fixture, and v0.5 migration smokes with no automatic deletion;
- status, stable update, same-version provenance, collision, rollback, symlink, unreadable-target, injected-failure, and concurrent-lock paths;
- marked `AGENTS.md`, existing Codex config, custom-agent registration, and per-skill discovery collisions;
- ignored root and nested vendor traversal regression;
- canonical state, dashboard, team, assurance, and lifecycle behavior;
- Python 3.9 and the current supported Python runtime;
- exact new-project/adoption manifest path lists and checksums;
- independent two-axis review; and
- disposable Internal Audit tied to the exact candidate.

If a listed command has changed during candidate integration, the implementation report must name the replacement and why. Do not silently omit a required verification category.

## 4. Preserve immutable historical origins

The v0.6 manifest may support only verified stable origins. The reviewed historical anchors are:

| Release | Full release commit | Manifest SHA-256 | v0.6 treatment |
| --- | --- | --- | --- |
| v0.1.0 | `2bea1a571ca4584a56d3fb231fe583f9710ccb95` | none | Historical only; not an automatic v0.6 origin |
| v0.2.0 | `8c3f9da8b08fca2408fa37bbf2a52d94e3fe8ad8` | none | Legacy additive migration fixture; not a schema-v3 update origin |
| v0.3.0 | `a8c041c2737f0cdec0834e5307906a4f9f15fabf` | none | Legacy additive migration fixture; not a schema-v3 update origin |
| v0.5.0 | `4191fe4be3a8da1ce3cea075bfb8f81a8d0d737c` | `744041e438990c37f3303666560c49cfbb919dec84e937e15307bae1fad3c88a` | Legacy additive migration fixture; not a schema-v3 update origin |

No v0.4.0 stable Git tag or GitHub release was published. v0.4 migration coverage proves compatibility with legacy development-shaped state; it must not appear as an invented stable origin. Baton v0.6.0 is the first schema-v3 release and therefore has no automatic `supportedUpgradeOrigins`. Future v0.6+ updates must pin both the origin's full commit and manifest SHA-256 as `TAG=COMMIT,MANIFEST_SHA256`.

Before any future release build, re-verify these anchors against local tags and the public historical release assets. If history or checksum evidence differs, stop and resolve the contradiction rather than editing this table opportunistically.

## 5. Create the clean candidate commit only with authority

Release bundles are tied to `HEAD^{commit}` and reject a dirty source worktree. Once Operations has integrated every scoped return and the user authorizes candidate commit work:

1. stage only the intended candidate;
2. rerun classification against the staged path set;
3. commit with the approved conventional commit message;
4. record the full candidate SHA; and
5. rerun the complete release-grade verification from that exact clean commit.

A candidate commit is still not a release. Stop before push/merge/tag/publication unless those actions were separately authorized.

## 6. Build and validate the five local assets

Build outside the source worktree from the clean candidate:

```sh
python3 scripts/release_bundle.py build \
  --source . \
  --output /tmp/baton-v0.6.0 \
  --tag v0.6.0 \
  --repository FabienGreard/baton \
  --state-schema-version 1

python3 scripts/release_bundle.py validate --bundle /tmp/baton-v0.6.0
```

The output directory must contain exactly:

```text
install.sh
baton-new-project.tar.gz
baton-adoption.tar.gz
baton-manifest.json
SHA256SUMS
```

Inspect `baton-manifest.json` and retain:

- full source commit and official repository;
- version/tag/channel and state schema;
- source-classification digest;
- every supported origin and required manifest digest;
- exact sorted file list for both payloads; and
- installer, archive, manifest, and per-file checksums.

The `install.sh` file is uploaded only as the stable URL bootstrapper. Neither archive may contain it, and lifecycle installation must not copy it into a consumer.

## 7. Run local release-asset smokes

Before publication, exercise the built assets through the release-directory fixture rather than GitHub:

```sh
target=$(mktemp -d)
BATON_RELEASE_DIR=/tmp/baton-v0.6.0 \
  bash /tmp/baton-v0.6.0/install.sh --target "$target" --yes --json
"$target/.baton/bin/baton" status --json
"$target/.baton/bin/baton" check --json
```

Run a separate non-empty target for Adoption mode. Prove its project-owned root snapshot is unchanged, status is `Needs Integration`, starter state is quarantined, and activation accepts only reviewed non-template state. Exercise updates from all supported origins with the same assets.

Do not use `releases/latest` for this phase; v0.6.0 does not exist there yet.

## 8. Return the unpublished candidate for approval

The release packet must identify:

- candidate version and full commit;
- exact changed-file boundary;
- five asset paths and SHA-256 values;
- source classification count by class;
- exact path count/checksum for each payload;
- full commands and results for the Thorough matrix;
- migration before/after manifests and cleanup candidates;
- collision, rollback, quarantine, activation, ignored-vendor, and Python compatibility evidence;
- two-axis review findings and dispositions;
- independent Internal Audit verdict;
- limitations and non-blocking follow-ups; and
- explicit statement that no push, tag, GitHub release, latest redirect, or publication has occurred.

Management audits that packet and requests the separate human `Release` decision. Without approval, stop here.

## 9. Publication after a later explicit approval

Only after the human approves the exact candidate may the release owner:

1. verify the official repository is the intended normal source repository and not configured as a template;
2. push/merge the exact approved candidate through the authorized workflow;
3. create tag `v0.6.0` at the approved full commit;
4. create a non-prerelease GitHub release from that tag;
5. upload all five locally validated assets without rebuilding from another commit;
6. enable immutable-release protection when available; and
7. verify public tag, release, assets, checksums, source commit, and release notes.

Do not mutate an uploaded asset in place. If any identity or checksum differs, stop and publish nothing further.

## 10. Immutable remote verification

After assets exist publicly, run the standalone smoke against the full commit recorded by `baton-manifest.json`:

```sh
bash tests/install_remote_smoke.sh v0.6.0 <full-candidate-commit-sha>
```

Then verify:

- `https://github.com/FabienGreard/baton/releases/tag/v0.6.0` resolves to the approved tag and commit;
- all five custom assets download and match `SHA256SUMS`;
- both payload records and archives still validate;
- `https://github.com/FabienGreard/baton/releases/latest/download/install.sh` resolves only now, after stable publication;
- empty install, mature adoption, reviewed activation, status, check, and update work from public assets; and
- generated cleanup evidence uses direct immutable links:

```text
https://github.com/FabienGreard/baton/compare/<origin-full-sha>...<target-full-sha>
https://github.com/FabienGreard/baton/blob/<target-full-sha>/template/<source-path>
```

A failed immutable remote smoke blocks release acceptance. It never authorizes replacing release assets or weakening provenance checks.

## 11. Final release handoff

Record the final tag, candidate commit, release URL, five asset checksums, remote smoke output, latest-redirect verification, limitations, and any exact human cleanup boundary. Reconcile source state and release records only after public verification succeeds.

The policy and procedure above are one release contract; neither technical completion nor local verification authorizes publication.
