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
- Kept `docs/` exclusively for the five public product/contributor guides, moved source-only evaluator specifications to `tests/evals/`, and removed the retired root `release/` directory.
- Replaced the redundant repository-wide source-classification inventory with a strict `template/.baton/` payload root, shared defaults, explicit starter/adoption-only projections, and exact generated manifests.
- Unified stable installation and update through one release `install.sh`; installed lifecycle commands live at `.baton/bin/baton`.
- Added schema-v3 Baton provenance, separate nullable `projectVersion`, immutable source commit/manifest evidence, managed baselines, external transactions, rollback, cleanup candidates, and direct GitHub source/compare links.
- Added mature-repository `Needs Integration` quarantine and explicit validated `_activate --from PATH` promotion.
- Added exact project-scoped Codex semantics, four-thread/depth-one limits, role presets, individual skills, Consultant hire/fire reconciliation, and no-persistent-goal lifecycle policy.
- Replaced legacy template smokes with a 40-test deterministic release/install/adoption/update/state/team/evaluator matrix.

## Important choices

- Root project identity and legal/community files are structurally outside the only eligible payload root; adoption payloads contain only `.baton/` paths.
- New-project scaffolding becomes `.baton/integration/starter/` during mature adoption and is never authoritative until explicit activation.
- Baton v0.6.0 is the first schema-v3 release and has no automatic schema-v3 upgrade origins. Legacy v0.2-v0.4 schemas have no per-file baselines, so Baton preserves every non-metadata path and records available evidence instead of guessing cleanup candidates. Authentic remote v0.2/v0.3 fixtures retain their missing installed revision and separately label verified official stable tag/commit anchors. v0.5 only surfaces unchanged checksum-verified managed/generated paths; project-owned, modified, missing, or invalid entries remain preserved.
- Future v0.6+ updates require both the exact origin commit and manifest SHA-256.
- Project-owned state and modified managed files are never overwritten automatically; conflicts produce manual actions and an external rollback location.
- Permanent Management, Operations, and Consultant tasks wake only from a new task message; persistent goals are never role identity or lifecycle control.

## Acceptance coverage

- Current projection: 75 new-project paths and 76 adoption paths derived only from tracked `template/.baton/`; all other source-repository paths are ineligible without a duplicate inventory.
- Source-layout assertions require exactly the five public guides under `docs/`, the evaluator contract under `tests/evals/`, absence of root `release/`, `docs/evals/`, and `scripts/source-classification.json`, and rejection of consumer source outside `template/.baton/`.
- Rehearsal payloads: 75 new-project paths and 76 adoption paths, all under `.baton/`.
- Fresh direct and stdin-piped installs produced only `.git`, `.baton`, `.agents`, `.codex`, and the marked `AGENTS.md` at repository root.
- Mature adoption, activation, legacy preservation, state-preserving updates, starter advancement, collision behavior, rollback, unsafe targets, and concurrent locking are covered by deterministic fixtures.
- Review-driven regressions cover unsafe `AGENTS.md` preservation, exactly one managed block, all-managed-file integrity before activation/update, lock-time compare-and-swap checks, rollback during report/prompt finalization, exact five-asset validation, and version-accurate legacy metadata.
- Generated configuration parses to `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, `sandbox_mode = "workspace-write"`, `max_threads = 4`, `max_depth = 1`, and workspace-write network access enabled.
- The public GitHub repository is `FabienGreard/baton`, public, on `main`, and `isTemplate = false`; historical v0.5.0 and its four original assets remain intact.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/harness_eval.py --strict --json` — PASS, 16/16.
- `PYTHONDONTWRITEBYTECODE=1 python3 tests/run_smokes.py` — PASS, 37/37 independently rerun by Internal Audit at `206705bf653b713c0af8fcee6c5b4217f50aae30`.
- `PYTHONDONTWRITEBYTECODE=1 python3.9 tests/run_smokes.py` — PASS, 37/37.
- `PYTHONDONTWRITEBYTECODE=1 .baton/bin/baton check --json` — PASS.
- `bash -n scripts/install.sh tests/install_smoke.sh tests/install_remote_smoke.sh` — PASS.
- `git diff --check` — PASS.
- Strict template-boundary projection — PASS; the obsolete classification command and manifest digest are absent.
- Reopened source-layout revision: strict evaluation 16/16; full current-Python and Python 3.9 matrices 40/40 each; source Markdown links, Baton state, shell syntax, and staged diff checks PASS. The exact clean-commit bundle, install/adoption, and independent-audit evidence is recorded after the implementation commit below.
- `python3 scripts/release_bundle.py build ...` and `validate` against clean implementation commit `206705bf653b713c0af8fcee6c5b4217f50aae30` — PASS; exactly five assets, 75 new-project paths, and 76 adoption paths.
- Exact implementation-commit assets: `install.sh` `e256ddd5c92dc924b4de6274c77090c465a553ff16e3a1e1e215535f384937d0`; new-project archive `f1bef229bb79987a1cc2c771f59acd13cd85725b25c41a53e3f2ed1100d1a177`; adoption archive `8be073c5b5e008d4e82151753a7c063093dbd9abc3ed406e9133c79f70a1c36e`; manifest `9300a650d61cded2811a1957d62b486a7803a038307fbfe9b939bee5e2ca3de4`; checksum file `9234c49a9aaa559c96b2ce64c37c6e811958772d48579f72c4b7da670ab88dd2`.
- Direct and stdin-piped fresh installs plus mature adoption from those exact assets — PASS. Fresh status was `Installed`, mature status was `Needs Integration`, 53 installed local Markdown links resolved, mature identity files were unchanged, and new installations created `.baton/metadata.json` without creating `.agent-harness.json`.
- Exact source-layout implementation commit `dab40c1a8b5599ef4943cbc54ea65fa117e8445d`: bundle build/validate PASS with 75 new-project and 76 adoption paths. Asset SHA-256 values: `install.sh` `e256ddd5c92dc924b4de6274c77090c465a553ff16e3a1e1e215535f384937d0`; new-project archive `f1bef229bb79987a1cc2c771f59acd13cd85725b25c41a53e3f2ed1100d1a177`; adoption archive `8be073c5b5e008d4e82151753a7c063093dbd9abc3ed406e9133c79f70a1c36e`; manifest `613c3708f2c0fd33f5975004809161b453ca21c9eef58d634180d656c15b3f4e`; checksum file `fb50a62e090b2c398c57dd1e1a8005a49b0f353e9e499888695cc8c0d3aaede3`.
- Direct and stdin-piped fresh installs plus mature non-empty adoption from the exact source-layout assets — PASS. Fresh status was `Installed`; mature status was `Needs Integration`; all three checks passed; mature `VERSION`, `LICENSE`, `.github`, `tests`, and `tools` fixtures remained byte-identical; archives exactly matched their manifests and stayed under `.baton/`.
- Exact payload-projection implementation commit `08245272b69108eb50d918518cf9db08c953d1c9`: strict evaluation 16/16; current Python 40/40; Python 3.9 40/40; Baton state, shell syntax, source links, and diff checks PASS. Bundle build/validate produced 62 shared, 13 starter, and 1 adoption-only source; 75 new-project paths and 76 adoption paths. Asset SHA-256 values: `install.sh` `e256ddd5c92dc924b4de6274c77090c465a553ff16e3a1e1e215535f384937d0`; new-project archive `8ac0e847c2b6f278f304b27fc890daf3533ecf362ea093df5dd112588c7de9dd`; adoption archive `9e74436b76b9ba387b78d95e7aae66c1d3cf4339447286a44003e67f6ba9b34f`; manifest `7cbe2649293be4ccf67e3c1875e207823d5520989407050efe0ed658f36368cb`; checksum file `8507995d700b8b4309e737017d520b11eb31187114116173cbd7012925158535`.
- Direct and stdin-piped fresh installs from those exact assets returned `Installed`, passed status/check, and resolved 53/53 local Markdown links. Mature non-empty adoption returned `Needs Integration`, quarantined starter state, passed check, and preserved every pre-existing `VERSION`, `LICENSE`, `.github`, documentation, test, and tool fixture byte-for-byte. The canonical `/private/tmp` rerun passed after the first `/tmp` spelling was intentionally rejected because macOS exposes it through a symbolic link.

Resolved test rigor: Thorough.

Required human review stages and current status: Release — pending; no release action has occurred.

## Consultant review

None. `requiredConsultantIds` is empty; Internal Audit remains independent and outside the project team.

## Integration review

- Standards/architecture follow-up: **APPROVE** at `30d14ae`; SA-01 through SA-05 were closed. Its one non-blocking P2 documentation clarification for unsafe `AGENTS.md` activation was incorporated.
- Specification/evidence follow-up: **REVISE** at `30d14ae` for one remaining P1: the v0.2/v0.3 fixtures incorrectly supplied an installed commit that authentic remote metadata did not contain. Commit `039acf1` now uses authentic null revisions, labels separately verified official version anchors, and reruns the migration and full dual-runtime matrices. The single permitted follow-up review loop ended there.
- Disposable independent Internal Audit at clean `039acf1`: **PASS** for the previous architecture boundary, 12/12 scenarios, 100/100 mean, no hard gates, and no P0-P3 findings. It does not cover the reorganized candidate and must be rerun against its exact source commit.
- Layout revision review: standards/architecture reported SA-01 (P3 dangling obsolete-path detection); specification/evidence reported SE-001 (P1 exact-candidate verification pending), SE-002 (P2 stale inventory/commands), and SE-003 (P3 stale release-guide paths). SA-01, SE-002, and SE-003 closed in the single follow-up review; SE-001 closed through the exact committed bundle, asset smokes, and independent audit below.
- Disposable Internal Audit `IA-20260715-206705b-STATIC-01` at clean implementation commit `206705bf653b713c0af8fcee6c5b4217f50aae30`: **PASS**, 97/100, no hard gates. It independently reran strict evaluation 16/16 and the current-Python matrix 37/37, validated the exact five assets and 75/76 projections, confirmed the new source topology and legacy migration behavior, and reported only IA-001 (P2 state/report completion mismatch) and IA-002 (P3 stale 36-test count). This evidence-only reconciliation closes both findings. The audit did not rerun scenario smoke or Python 3.9; Operations independently reran Python 3.9 at 37/37.
- Reopened source-layout standards/architecture review at staged boundary `64089d1e5b794affeebbd0747fca29f2f8b79b5c4e34af7b9df9584abecaa120`: **APPROVE**. SA-001 (P2) correctly identified the temporary mismatch between the reopened canonical state and this previously completed report; this revision and the final transactional return reconcile it.
- Reopened source-layout specification/evidence review: **REVISE** only for SE-001 (P1), requiring exact-commit Internal Audit before return; the reviewer otherwise confirmed the intended layout and evidence. Disposable Internal Audit `IA-20260715-dab40c1-STATIC-01` at exact clean implementation commit `dab40c1a8b5599ef4943cbc54ea65fa117e8445d`: **PASS**, 100/100, no hard gates and no P0-P3 findings. It independently reran strict evaluation 16/16, classification, Baton state, focused tests 12/12, exact bundle build/validation, installed-link checks, and targeted layout/reference checks. This closes SE-001.
- Payload-projection simplification review: specification/evidence **APPROVE**; standards/architecture initially **REVISE** for SA-001 (P1), because the release validator and installed lifecycle trusted a checksum-consistent manifest's `sourcePath` and `projection` claims. The accepted correction independently recomputes the source-to-projection-to-destination invariant in both surfaces. The one bounded follow-up review at staged diff `17463332802970c28997076ffe5cde4d65ac4743ebc9a80f2b5be2b9873e2e65` returned **APPROVE** with no P0-P3 findings: re-signed false-provenance fixtures fail closed, focused tamper tests pass 2/2, affected release/lifecycle tests pass 29/29, and the full dual-runtime matrix passes 40/40.
- Disposable Internal Audit `IA-20260715-08245272-STATIC-01` at clean implementation commit `08245272b69108eb50d918518cf9db08c953d1c9`: **PASS**, 100/100, no hard gates and no P0-P3 findings. It independently reran Baton state, strict evaluation 16/16, current Python 40/40, Python 3.9 40/40, local installer smoke 40/40, shell/diff checks, exact bundle construction, projection recomputation, provenance-tamper rejection, direct/piped fresh installation, and mature adoption preservation. It recommends accepting this as the unpublished candidate for Management handoff.

## Human review

Human Release approval remains pending. Candidate preparation, a local commit, and GitHub repository-setting changes do not authorize push, merge, tag, release, asset upload, or modification of `releases/latest`.

## Known limitations and risks

- The immutable standalone remote smoke cannot run until an approved v0.6.0 release and all five assets exist publicly; it remains a hard post-publication acceptance gate.
- The stable installer URL intentionally continues to resolve to historical v0.5.0 until publication. The candidate README warns that v0.6.0 is unpublished.
- Auto-review availability may be constrained by Codex/app or managed-workspace settings, and already-running tasks can retain their selected permission mode.
- Mature-state activation is deliberately not inferred from existing Markdown; an LLM or human must prepare and approve complete schema-valid records.

## Follow-up work

- Await an explicit human Release decision before any push, merge, tag, GitHub release, or upload.
- After any authorized publication, run the immutable-SHA standalone remote smoke before treating the stable release as fully accepted.

## Ownership returned

BATON-001 is returned to Management with the fully verified unpublished candidate, closed review findings, exact local asset evidence, limitations, and release boundary. Operations ownership is cleared. Publication remains human-gated and requires a new explicit Release instruction.
