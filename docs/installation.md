# Install and bootstrap with Codex

The installer creates a new project from this harness and configures native project-scoped Codex agents. It supports interactive humans and fully specified agent/non-interactive execution.

Requirements: Bash, Python 3.9 or newer, and `tar`; remote installation also needs `curl`, while Git initialization needs `git` unless `--no-git` is selected.

## Quick installation

Run the interactive installer:

```sh
mkdir example-project && cd example-project
curl -fsSL https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh | bash
```

This executes the remote installer directly. Use the review-first flow below when you want to inspect it before running.

The guided flow is keyboard-first:

1. Choose Software/Product, Game Development, Business Operations, Research, or Other.
2. Accept or edit the project name inferred from the current folder.
3. Accept or edit the destination; it defaults to `.`.
4. Choose Balanced, Deep, or Custom reasoning. Balanced and Deep continue immediately; Custom opens one reasoning menu for Director, Delivery, Specialist, worker, and Evaluator roles.

Use arrow keys or `j`/`k` to move, Enter to select, or number keys for direct selection. Set `NO_COLOR=1` for a plain numbered-menu fallback. The destination must be empty, so the `.` default is intended for a freshly created project folder.

## Review-first installation

```sh
curl -fsSLo /tmp/agentic-project-harness-install.sh \
  https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh
less /tmp/agentic-project-harness-install.sh
bash /tmp/agentic-project-harness-install.sh
```

## Non-interactive installation

```sh
curl -fsSL https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh | \
  bash -s -- \
  --project-name "Example Project" \
  --target ./example-project \
  --project-type software-product \
  --reasoning-preset balanced \
  --yes
```

The Specialist Lead is always installed. Use `--specialist-reasoning LEVEL` to override its preset reasoning in non-interactive mode.

## Reasoning choices

Each role accepts `inherit`, `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, or `ultra`. `inherit` omits the role-specific override so the agent inherits the parent Codex session. The selected Codex model and account determine which explicit levels are available; `max`, `xhigh`, `ultra`, `minimal`, and `none` are model-dependent.

The defaults are:

| Agent role | Default | Why |
| --- | --- | --- |
| Project Director | `high` | Outcome, scope, readiness, and review decisions need careful reasoning. |
| Delivery Lead | `high` | Dispatch, ownership, integration, and verification cross multiple workstreams. |
| Specialist Lead | `high` | Expert definition and acceptance often require edge-case analysis. |
| Execution worker | `medium` | Bounded implementation normally benefits from balanced speed and depth. |
| Harness Evaluator | `xhigh` | Independent audits need maximum practical contradiction and safety detection. |

All execution worker instances share the starter worker profile. Add narrower custom agent files later when a stable worker specialization justifies a different level.

The **Balanced** preset uses the defaults above. **Deep** uses `xhigh` for Director, Delivery, Specialist, and Evaluator roles, with `high` for execution workers. **Custom** exposes every supported level for every role. Explicit per-role flags override the selected preset in non-interactive mode.

## Options

| Option | Meaning |
| --- | --- |
| `--project-name NAME` | Human-readable project name |
| `--target DIRECTORY` | New empty destination |
| `--project-type TYPE` | `software-product`, `game-development`, `business-operations`, `research`, or `other` |
| `--reasoning-preset PRESET` | `balanced`, `deep`, or `custom` |
| `--director-reasoning LEVEL` | Project Director reasoning level |
| `--delivery-reasoning LEVEL` | Delivery Lead reasoning level |
| `--worker-reasoning LEVEL` | Execution worker reasoning level |
| `--evaluator-reasoning LEVEL` | Harness Evaluator reasoning level |
| `--specialist-reasoning LEVEL` | Specialist Lead reasoning level |
| `--ref REF` | GitHub branch or tag to download; default `main` |
| `--repo OWNER/NAME` | Alternate public template fork |
| `--yes` | Non-interactive mode; requires project name and target |
| `--no-git` | Do not initialize a new local Git repository |
| `--dry-run` | Validate inputs and print the plan without writing |
| `--help` | Usage |

Maintainers can exercise the exact standalone download path at a pushed commit with `bash tests/install_remote_smoke.sh COMMIT_SHA` before tagging a release.

## Generated Codex configuration

The installer writes `.codex/config.toml` plus one file per active role under `.codex/agents/`. The default `max_threads = 4` is a concurrency ceiling rather than a worker target, reducing peak token and local-resource use while retaining useful parallel execution. `max_depth = 1` preserves the shallow single-dispatch-center topology and prevents recursive worker fan-out. The active Codex surface may impose a lower concurrency cap. Each custom agent file includes its role contract and selected `model_reasoning_effort`; the model is deliberately not pinned. The installer also adds the generic governance map and rules under `.agents/rules/`, and the `brainstorm`, `improve-codebase-architecture`, and `code-review` skills under `.agents/skills/`. `.codex/skills` is a relative symlink to that directory, keeping Codex discovery on one non-drifting copy.

## Project permissions

Fresh projects use this exact project-scoped configuration:

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_mode = "workspace-write"

[agents]
max_threads = 4
max_depth = 1

[sandbox_workspace_write]
network_access = true
```

This requests automatic review when an action needs approval while retaining workspace-write sandboxing and explicit network access within that sandbox. **Approve for me** / Auto-review availability may still be constrained by the user's Codex app, organization, or managed workspace settings. Existing conversations can retain the permission mode already selected for that conversation; start a new task or explicitly change its mode when the project config must take effect.

Permanent top-level tasks do not automatically become a custom subagent. When creating the Project Director, Delivery Lead, and Specialist Lead as separate Codex tasks, select the matching reasoning level in the task composer and give each its corresponding role prompt. The Specialist Lead remains dormant until its recurring expert domain is approved. The durable `.codex/agents/` files remain the auditable source for the intended setting.

See the official Codex documentation for [custom agents and per-agent reasoning](https://learn.chatgpt.com/codex/agent-configuration/subagents) and the [`model_reasoning_effort` configuration reference](https://learn.chatgpt.com/codex/config-file/config-reference).

## Safety boundary

- The target must not exist or must be empty; there is intentionally no force-overwrite flag.
- No existing component supplied in the target path may be a symbolic link, preventing a requested absolute path from redirecting installation into another location even when the final target directory already exists. Relative targets are anchored to the physical current directory before this check.
- Target paths containing a `..` segment are rejected before normalization so a symlink followed by parent traversal cannot hide the path actually written.
- Installation never starts Codex, spends model credits, logs in, selects a paid model, or changes global configuration.
- A missing Codex CLI produces a warning rather than a failed installation, allowing desktop or remote use.
- Git initialization creates `main` but does not stage or commit; the agent and human must review the customized governance baseline first.
- Local checkout installs record `local-working-tree` provenance and whether that source was dirty. A standalone or piped installer always downloads the declared repository and ref.
- The generated project remains in template mode until the inline **First project prompt** in `README.md` is completed and strict harness checks pass.
- `python3 tools/harness_eval.py` verifies the map-only `AGENTS.md`, common rule template, skill metadata/support files, relative discovery symlink, and Director/Delivery review integration.

## First agent run

Open the generated `README.md`, find **First project prompt**, and copy that complete fenced block into a new Codex task using the Project Director reasoning level. The prompt is inline so there is no separate bootstrap file to find or keep synchronized. It deliberately forbids implementation during onboarding; its job is to establish verified direction, roles, readiness, and the first explicit baton.
