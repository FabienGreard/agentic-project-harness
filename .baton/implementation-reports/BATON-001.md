# BATON-001 — Implementation report

Completed/returned: 2026-07-15

Reviewed by: Operations

Goal ID: BATON-GOAL-001

## Outcome

Baton is now a normal source/product repository rather than a GitHub project template. Reusable consumer content has one canonical source under `template/.baton/`; the source repository operates from its own source-only `.baton/` control plane. The release builder projects exact new-project and mature-adoption payloads without copying project identity, licensing, community, source, scripts, tests, evaluator, or release infrastructure into consuming repositories.

The architecture begins at `9ecef4486784d1412d590ee9b9a1e42c2fc73402` and its first implementation commit is `0353fc33061b7ce1e4fc74fbcec84a763b1a3917`. Review fixes and source-state reconciliation follow that commit. The final unpublished candidate SHA is supplied in the external release handoff because a commit cannot embed its own immutable SHA.

## Changed files, systems, or outputs

- Renamed active product identity to Baton and changed the public GitHub repository to `FabienGreard/baton` with template mode disabled.
- Added source-only Baton project state under root `.baton/` and individual source skill-discovery links under `.agents/skills/`.
- Added canonical consumer source under `template/.baton/`, with no second drifting copy.
- Added exact source classification and separate new-project/adoption payload projection.
- Unified stable installation and update through one release `install.sh`; installed lifecycle commands live at `.baton/bin/baton`.
- Added schema-v3 Baton provenance, separate nullable `projectVersion`, immutable source commit/manifest evidence, managed baselines, external transactions, rollback, cleanup candidates, and direct GitHub source/compare links.
- Added mature-repository `Needs Integration` quarantine and explicit validated `_activate --from PATH` promotion.
- Added exact project-scoped Codex semantics, four-thread/depth-one limits, role presets, individual skills, Consultant hire/fire reconciliation, and no-persistent-goal lifecycle policy.
- Replaced legacy template smokes with a 36-test deterministic release/install/adoption/update/state/team/evaluator matrix.

## Important choices

- Root project identity and legal/community files are always source-only; adoption payloads contain only `.baton/` paths.
- New-project scaffolding becomes `.baton/integration/starter/` during mature adoption and is never authoritative until explicit activation.
- Baton v0.6.0 is the first schema-v3 release and has no automatic schema-v3 upgrade origins. Legacy v0.2-v0.4 schemas have no per-file baselines, so Baton preserves every non-metadata path and records available evidence instead of guessing cleanup candidates. Authentic remote v0.2/v0.3 fixtures retain their missing installed revision and separately label verified official stable tag/commit anchors. v0.5 only surfaces unchanged checksum-verified managed/generated paths; project-owned, modified, missing, or invalid entries remain preserved.
- Future v0.6+ updates require both the exact origin commit and manifest SHA-256.
- Project-owned state and modified managed files are never overwritten automatically; conflicts produce manual actions and an external rollback location.
- Permanent Management, Operations, and Consultant tasks wake only from a new task message; persistent goals are never role identity or lifecycle control.

## Acceptance coverage

- Current source classification: 173 files—97 source-only, 62 shared, 13 template-only, and 1 adoption-runtime, with zero unclassified paths.
- Rehearsal payloads: 75 new-project paths and 76 adoption paths, all under `.baton/`.
- Fresh direct and stdin-piped installs produced only `.git`, `.baton`, `.agents`, `.codex`, and the marked `AGENTS.md` at repository root.
- Mature adoption, activation, legacy preservation, state-preserving updates, starter advancement, collision behavior, rollback, unsafe targets, and concurrent locking are covered by deterministic fixtures.
- Review-driven regressions cover unsafe `AGENTS.md` preservation, exactly one managed block, all-managed-file integrity before activation/update, lock-time compare-and-swap checks, rollback during report/prompt finalization, exact five-asset validation, and version-accurate legacy metadata.
- Generated configuration parses to `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, `sandbox_mode = "workspace-write"`, `max_threads = 4`, `max_depth = 1`, and workspace-write network access enabled.
- The public GitHub repository is `FabienGreard/baton`, public, on `main`, and `isTemplate = false`; historical v0.5.0 and its four original assets remain intact.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/harness_eval.py --strict --json` — PASS, 16/16.
- `PYTHONDONTWRITEBYTECODE=1 python3 tests/run_smokes.py` — PASS, 36/36.
- `PYTHONDONTWRITEBYTECODE=1 python3.9 tests/run_smokes.py` — PASS, 36/36.
- `PYTHONDONTWRITEBYTECODE=1 .baton/bin/baton check --json` — PASS.
- `bash -n scripts/install.sh tests/install_smoke.sh tests/install_remote_smoke.sh` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/release_bundle.py classify --source .` — PASS with zero drift at the reviewed code boundary.
- `python3 scripts/release_bundle.py build ...` and `validate` — the previous architecture candidate passed; the reorganized exact candidate rebuild remains required after its source commit.
- Direct and stdin-piped fresh installs from the local release directory, followed by `status` and `check` — PASS. `/tmp` was correctly rejected on macOS because it traverses a symlink; canonical `/private/tmp` passed.

Resolved test rigor: Thorough.

Required human review stages and current status: Release — pending; no release action has occurred.

## Consultant review

None. `requiredConsultantIds` is empty; Internal Audit remains independent and outside the project team.

## Integration review

- Standards/architecture follow-up: **APPROVE** at `30d14ae`; SA-01 through SA-05 were closed. Its one non-blocking P2 documentation clarification for unsafe `AGENTS.md` activation was incorporated.
- Specification/evidence follow-up: **REVISE** at `30d14ae` for one remaining P1: the v0.2/v0.3 fixtures incorrectly supplied an installed commit that authentic remote metadata did not contain. Commit `039acf1` now uses authentic null revisions, labels separately verified official version anchors, and reruns the migration and full dual-runtime matrices. The single permitted follow-up review loop ended there.
- Disposable independent Internal Audit at clean `039acf1`: **PASS** for the previous architecture boundary, 12/12 scenarios, 100/100 mean, no hard gates, and no P0-P3 findings. It does not cover the reorganized candidate and must be rerun against its exact source commit.
- Staged layout revision review: standards/architecture reported SA-01 (P3 dangling obsolete-path detection); specification/evidence reported SE-001 (P1 exact-candidate verification pending), SE-002 (P2 stale inventory/commands), and SE-003 (P3 stale release-guide paths). SA-01, SE-002, and SE-003 are corrected in the candidate; SE-001 remains the explicit pre-completion verification boundary.

## Human review

Human Release approval remains pending. Candidate preparation, a local commit, and GitHub repository-setting changes do not authorize push, merge, tag, release, asset upload, or modification of `releases/latest`.

## Known limitations and risks

- The immutable standalone remote smoke cannot run until an approved v0.6.0 release and all five assets exist publicly; it remains a hard post-publication acceptance gate.
- The stable installer URL intentionally continues to resolve to historical v0.5.0 until publication. The candidate README warns that v0.6.0 is unpublished.
- Auto-review availability may be constrained by Codex/app or managed-workspace settings, and already-running tasks can retain their selected permission mode.
- Mature-state activation is deliberately not inferred from existing Markdown; an LLM or human must prepare and approve complete schema-valid records.

## Follow-up work

- Rebuild and validate the exact final candidate assets after this source-only evidence/state reconciliation.
- Await an explicit human Release decision before any push, merge, tag, GitHub release, or upload.
- After any authorized publication, run the immutable-SHA standalone remote smoke before treating the stable release as fully accepted.

## Ownership returned

Operations will return the fully verified unpublished candidate only after the reorganized clean commit passes exact bundle construction, asset smokes, and disposable Internal Audit. Publication remains human-gated.
