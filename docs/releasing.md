# Stable release procedure

Releases are human-authorized and stable-only. Do not build lifecycle assets from a dirty tree, moving branch archive, fork with unknown provenance, draft, or prerelease.

## Candidate gates

1. Set `VERSION`, `.agent-harness.json`, README/docs, tests, and CHANGELOG to the same candidate version.
2. Run the static evaluator, team/state/dashboard drift checks, focused smokes, full installer/update smoke, interactive preset/custom smoke, two-axis review, and independent disposable Internal Audit.
3. Commit the exact candidate. Do not tag or publish until the human release decision.
4. Build the four assets outside the source worktree:

```sh
python3 tools/release_bundle.py build \
  --source . \
  --output /tmp/agentic-project-harness-v0.5.0 \
  --tag v0.5.0 \
  --supported-upgrade-origin v0.2.0=8c3f9da8b08fca2408fa37bbf2a52d94e3fe8ad8 \
  --supported-upgrade-origin v0.3.0=a8c041c2737f0cdec0834e5307906a4f9f15fabf \
  --state-schema-version 1
python3 tools/release_bundle.py validate --bundle /tmp/agentic-project-harness-v0.5.0
```

The asset set is exactly `install.sh`, `agentic-project-harness-template.tar.gz`, `harness-manifest.json`, and `SHA256SUMS`. The manifest pins the candidate commit and every supported stable origin to a full commit; the checksums bind the installer, archive, and manifest. For a schema-v2 origin, append its immutable manifest digest as `TAG=COMMIT,MANIFEST_SHA256`. Legacy origins without release manifests use the reviewed full-commit anchors above. Never add a moving tag or an unpublished version as an origin.

## Publication boundary

After explicit human approval, create the matching stable tag and GitHub release from the exact candidate commit, upload all four assets, and use GitHub's immutable-release protections when available. Do not mark the release as a prerelease.

Run the standalone release-asset smoke against the immutable commit recorded in the manifest:

```sh
bash tests/install_remote_smoke.sh v0.5.0 <full-candidate-commit-sha>
```

Confirm `releases/latest/download/install.sh` resolves successfully only after the stable release exists. A failed immutable-SHA smoke blocks release acceptance; it never authorizes changing an existing immutable asset in place.
