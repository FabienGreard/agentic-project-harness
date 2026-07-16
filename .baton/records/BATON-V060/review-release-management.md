# BATON-V060-RELEASE — Clearance

Status: Approved
Reviewer: Fabien Greard
Goal or Ticket: Goal `BATON-V060`
Stage: Release

## Outcome and change

Exact commit `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` and its validated five-asset set are approved as Baton `v0.6.0`, replacing the older pending v0.6 branch. The only branch remaining locally and remotely after release must be `main`.

## Criteria and Evidence

The exact candidate passed 19/19 source checks, 139/139 tests on Python 3.13 and 3.9, two independent code reviews, and fresh Internal Audit. Its authentic public-v0.5 adoption preserves every legacy skill path and creates zero partial v0.6 links; coherent forged-baseline and incomplete-set cases fail atomically. The validated asset digests are:

- `baton-manifest.json`: `088370b07d46b06ddc37d2cd98dc6cae9a9e76cadb664621458834e082e41627`
- `baton-adoption.tar.gz`: `09032ab5a2e6abe051be13b3c025cd5fdead0dbb4be23464fc1ec1e736ae6933`
- `baton-new-project.tar.gz`: `96d4f87ebb2aee1407063fb1ce57421d6a394d944795cc4563d05faea4cf4f0f`
- `install.sh`: `8b4e697f62ceee9fab0058be9941466f08f1c25d7892e57d76e6444624b6a240`
- `SHA256SUMS`: `07dbdd354fb9ddc193fc383e0ab312f9b2c0fcece6761219e064779ed8eb4637`

Nothing was pushed, tagged, merged, or published when this packet was returned. In response, the user required that no branch other than `main` remain on the machine or remote, approving continuation with that terminal condition.

## Risks or deferred work

No failed review, failing verification, mutable-source mismatch, incomplete asset set, or unproven remote installation may be waived by this decision.

## Decision

Approved for publication of exactly commit `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` with exactly the five validated assets above. Publication is incomplete until immutable remote smoke passes and both local and remote branch inventories contain only `main`.
