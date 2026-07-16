# Releasing

Baton publishes only stable, immutable, reproducible, human-approved releases. A source checkout is never an installation artifact. Checks, commits, and built assets do not authorize publication.

## Release contract

One approved version and full commit produce exactly five assets:

```text
install.sh
baton-new-project.tar.gz
baton-adoption.tar.gz
baton-manifest.json
SHA256SUMS
```

Consumer archives come only from tracked `template/.baton/` content and contain only `.baton/` paths. The manifest binds the version, source commit, paths, and checksums. Published assets are never replaced.

## 1. Prepare the candidate

Confirm:

- `VERSION` and changelog agree;
- root `.baton/` remains source-only;
- consumer source exists only under `template/.baton/`;
- the seven public skills still match their CLI families;
- state, team, memory, adoption, update, and rollback contracts are current; and
- the diff contains only intended work.

Invoke `$doctor` first. Then run the source checks:

```sh
python3 scripts/harness_eval.py --strict
bash tests/install_smoke.sh
bash -n tests/install_remote_smoke.sh
git diff --check
```

Repeat the Python suite on Python 3.9 when available. Keep evidence for:

- empty install, mature adoption, and activation;
- collisions, updates, migration, rollback, unsafe targets, and locks;
- State, team, Memory, and `$boot` native and fallback paths; and
- manifests, links, and ignored-vendor boundaries.

Invoke `$code-review` on the exact candidate, then run disposable Internal Audit. A credible P0 or Confirmed/Proven P1 blocks release.

## 2. Pin immutable origins

Update origins must be verified stable releases with a full commit and, when available, a manifest SHA-256. Older releases without trusted file baselines remain migration evidence. Never invent an unpublished release or rename historical products.

Current reviewed anchors:

| Release | Full commit | Manifest SHA-256 |
| --- | --- | --- |
| v0.1.0 | `2bea1a571ca4584a56d3fb231fe583f9710ccb95` | none |
| v0.2.0 | `8c3f9da8b08fca2408fa37bbf2a52d94e3fe8ad8` | none |
| v0.3.0 | `a8c041c2737f0cdec0834e5307906a4f9f15fabf` | none |
| v0.5.0 | `4191fe4be3a8da1ce3cea075bfb8f81a8d0d737c` | `744041e438990c37f3303666560c49cfbb919dec84e937e15307bae1fad3c88a` |

Verify these SHAs before building a release.

## 3. Create the clean candidate

Only with explicit commit authority:

1. stage intended files only;
2. rerun strict checks against the staged boundary;
3. create the approved conventional commit;
4. record the full SHA; and
5. rerun the complete matrix from that clean commit.

Stop before publication unless separately authorized.

## 4. Build and test local assets

```sh
python3 scripts/release_bundle.py build \
  --source . \
  --output /tmp/baton-release \
  --tag v<VERSION> \
  --repository FabienGreard/baton \
  --supported-upgrade-origin v0.5.0=4191fe4be3a8da1ce3cea075bfb8f81a8d0d737c,744041e438990c37f3303666560c49cfbb919dec84e937e15307bae1fad3c88a \
  --state-schema-version 2 \
  --memory-schema-version 1

python3 scripts/release_bundle.py validate --bundle /tmp/baton-release
```

Exercise the assets without GitHub. Use `$terminal` and `$doctor` for manual inspection; the scripted release proof may call their CLI families directly:

```sh
target=$(mktemp -d)
target=$(CDPATH= cd -- "$target" && pwd -P)
BATON_RELEASE_DIR=/tmp/baton-release \
  bash /tmp/baton-release/install.sh --target "$target" --yes --json
"$target/.baton/bin/baton" terminal status --json
"$target/.baton/bin/baton" doctor check --json
```

Repeat with a non-empty target and every supported update origin. Prove Project-owned roots remain unchanged, mature-repository starter State remains quarantined until reviewed activation, and authentic legacy discovery either completes or reaches its documented human-approved integration boundary without partial links.

## 5. Request Release approval

Return a Release packet with:

- version, full commit, and exact diff;
- asset and payload checksums;
- commands and results;
- migration, collision, and rollback evidence;
- review findings and the Internal Audit verdict;
- limitations; and
- a clear statement that nothing has been published.

Management requests the separate human `Release` decision. Without it, stop.

## 6. Publish the approved candidate

After approval only:

1. push or merge the exact approved commit;
2. create `v<VERSION>` at that commit;
3. create a non-prerelease release;
4. upload the five already validated assets without rebuilding;
5. enable immutable protection when available; and
6. verify the public tag, commit, assets, checksums, and notes.

Any identity or checksum difference blocks further publication.

## 7. Verify remotely

```sh
bash tests/install_remote_smoke.sh v<VERSION> <full-commit-sha>
```

Verify empty install, mature adoption, reviewed activation, `$terminal`, `$doctor`, `$upgrade`, `$scrap`, checksums, and the latest-stable redirect.

A failed remote smoke blocks acceptance. It never authorizes replacing assets or weakening provenance.

Record the final tag, commit, release URL, checksums, smoke output, redirect verification, limitations, and remaining human cleanup boundaries.
