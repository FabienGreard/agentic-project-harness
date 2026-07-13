# Agentic Project Harness

[![GitHub stars](https://img.shields.io/github/stars/FabienGreard/agentic-project-harness?style=social)](https://github.com/FabienGreard/agentic-project-harness/stargazers)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

A reusable, evidence-driven multi-agent project orchestration template for software, games, research, operations, and other complex work.

This repository contains the coordination system—not an application. Use it as a GitHub template, define your project, register the permanent roles your environment supports, and let execution workers operate from bounded, reviewable assignments.

## Why “harness”?

An agent prompt describes one task. A harness defines how a whole project keeps moving safely over time:

- who owns direction, delivery, specialist judgment, and execution;
- when work is ready to start;
- how new requests affect active work;
- how independent work runs in parallel without file or system conflicts;
- how results return, integrate, and receive human review;
- when long-running roles pause instead of polling;
- how the orchestration system itself is evaluated.

## Core model

```mermaid
flowchart LR
    H["Human owner"] --> D["Project Director"]
    D --> L["Delivery Lead"]
    D --> S["Specialist Lead"]
    S --> L
    L --> W1["Execution worker"]
    L --> W2["Execution worker"]
    L --> W3["Execution worker"]
    W1 --> L
    W2 --> L
    W3 --> L
    L --> D
    S --> D
    E["Disposable Harness Evaluator"] -. read-only audit .-> D
```

- **Project Director:** owns intended outcomes, priority, scope, readiness, decisions, publication, and human-review gates.
- **Delivery Lead:** owns execution planning, worker dispatch, exclusive ownership, integration, verification, and run-to-idle delivery.
- **Specialist Lead:** the standard expert-definition and review role. It remains dormant until the project assigns a recurring domain such as design, legal, finance, safety, data, security, or art; Delivery remains the single dispatch center.
- **Execution workers:** implement only their assigned scopes and return evidence to Delivery.
- **Harness Evaluator:** a disposable, independent, read-only worker that grades orchestration behavior and never fixes what it evaluates.

## Start a project

### Quick installer

Run the interactive installer:

```sh
mkdir my-project && cd my-project
curl -fsSL https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh | bash
```

This executes the remote installer directly. Use the review-first flow in [docs/installation.md](docs/installation.md) when you want to inspect it before running.

The keyboard-first setup uses the current folder name and installs into `.` by default. Choose a project type, accept or edit the inferred name, then use a Balanced or Deep reasoning preset—or expand Custom to configure every role. Arrow keys, `j`/`k`, number keys, and Enter are supported. The destination must be empty; existing files are never overwritten.

### Install with your coding agent

Copy this prompt into Codex or another coding agent. Its scope is installation only:

```text
Install Agentic Project Harness in a new empty project folder.

First inspect the current directory. Never overwrite or delete existing files. If it is not empty, ask me for a new empty destination. Derive the project name from the destination folder. Ask me for the project type only if it is unclear; valid values are software-product, game-development, business-operations, research, and other. Use the balanced reasoning preset unless I request deep or custom.

Download and inspect the installer, then run it non-interactively:

curl -fsSLo /tmp/agentic-project-harness-install.sh https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh
bash /tmp/agentic-project-harness-install.sh --project-name "<derived project name>" --target "<empty destination>" --project-type "<project type>" --reasoning-preset balanced --yes

Confirm the installer checks pass and report the installed path. Do not customize the generated governance, create project implementation, commit, push, or publish during this installation task.
```

For an agent or non-interactive shell, the defaults reduce the command to:

```sh
curl -fsSL https://raw.githubusercontent.com/FabienGreard/agentic-project-harness/main/install.sh | \
  bash -s -- \
  --project-name "My Project" \
  --target ./my-project \
  --project-type software-product \
  --reasoning-preset balanced \
  --yes
```

The installer creates a clean Codex project, lets you choose the reasoning level for each agent role, generates native project-scoped custom agent files under `.codex/agents/`, installs generic rules under `.agents/rules/`, and installs the three project skills under `.agents/skills/`. Codex discovers those skills through the relative `.codex/skills` symlink, so there is one source of truth and no duplicated copies.

The project-scoped Codex config uses on-request approval with automatic approval review, workspace-write sandboxing, and network access inside that sandbox. It sets `max_threads = 4` as a concurrency ceiling—not a worker target—and keeps `max_depth = 1` so Delivery remains the single shallow dispatch center; an execution surface may enforce a lower cap. **Approve for me** / Auto-review can still be limited by the user's Codex app or managed workspace policy, and already-running conversations may retain their currently selected permission mode. The installer runs the static harness checks, initializes Git without committing, and refuses to overwrite a non-empty target.

See [docs/installation.md](docs/installation.md) for the review-first flow and all options.

### GitHub template

1. Click **Use this template** on GitHub and create a new repository.
2. Follow [TEMPLATE_CHECKLIST.md](TEMPLATE_CHECKLIST.md).
3. Replace the starter state in `docs/overview.md`, `docs/direction.md`, `docs/backlog.md`, and `docs/project-state.json`.
4. Register Director, Delivery, and Specialist Lead return paths. Keep the Specialist Lead dormant until a recurring expert acceptance domain is approved.
5. Register task/thread identifiers locally in `docs/thread-registry.md` without committing secrets.
6. Promote work to `Ready` only after the readiness contract is complete.
7. Run `python3 tools/harness_eval.py` before the first implementation handoff.

## Repository layout

```text
.
├── AGENTS.md                         # Navigation map into normative rules
├── .agents/
│   ├── rules/                        # Commonly templated governance modules
│   └── skills/                       # Generic project-scoped skills and metadata
├── .codex/skills -> ../.agents/skills # Relative Codex discovery link
├── install.sh                        # Interactive and agent-friendly bootstrapper
├── .codex/
│   ├── config.toml                   # Project-scoped concurrency defaults
│   └── agents/                       # Per-role Codex reasoning configuration
├── docs/
│   ├── overview.md                   # Current project truth and next action
│   ├── direction.md                  # Approved outcomes and constraints
│   ├── backlog.md                    # Human-readable work index
│   ├── active-work.md                # Ownership and integration state
│   ├── project-state.json            # Machine-readable state index
│   ├── workflow.md                   # Readiness, handoff, review, idle rules
│   ├── roles/                        # Permanent and disposable role contracts
│   ├── templates/                    # Decision, PRD, ticket, report templates
│   ├── schemas/                      # Machine-readable contracts
│   └── evals/harness/                # Static and scenario evaluation suite
├── examples/
│   ├── game-development/             # Optional game-domain adaptation
│   └── business-operations/          # Optional business-domain adaptation
├── tools/harness_eval.py             # Dependency-free static verifier
├── tests/                             # Local and standalone-download installer smoke checks
└── .github/                           # Issues, PRs, community health
```

## The baton rule

Every orchestration run ends in one explicit state:

- a named owner has the next meaningful action and return trigger;
- a result or review is pending from a named owner;
- a future action is waiting on a recorded trigger;
- progress is blocked on a precise decision that has been escalated once;
- no meaningful action remains and the smallest wake condition is recorded.

No role should poll work it has delegated. A new request does not automatically cancel active work; classify it as superseding, parallel, queued, or informational first.

## Worker-first, not worker-only

Substantial independent work should normally be dispatched to workers so Delivery remains available for coordination, review, and integration. Direct Lead implementation is still appropriate for small, tightly coupled, architecture-sensitive, integration, verification, or narrow revision work. The harness rewards useful parallelism and rejects artificial parallelism across shared files or unstable contracts.

## Harness evaluation

The included evaluation suite has four modes:

- deterministic repository checks;
- one-pass scenario smoke tests;
- repeated scenario release comparisons;
- independent audits of real task traces.

The evaluator checks hard failures first—such as non-ready execution, overlapping ownership, lost work, invented intent, skipped specialist/human gates, missing batons, contradictory state, and unproven completion—then scores scope, handoffs, safety, parallelism, advancement, and interruption efficiency.

See [docs/evals/harness/README.md](docs/evals/harness/README.md).

## Domain examples

- [Game development](examples/game-development/README.md): Project Director, Production Lead, the standard dormant Specialist Lead configured for Art/Design when approved, engineering and asset workers, playable-slice reviews.
- [Business operations](examples/business-operations/README.md): Program Director, Operations Lead, optional Finance/Legal/Domain Lead, analysis and process workers, approval checkpoints.

Examples are overlays, not separate frameworks. Keep the authority and handoff model; rename roles and gates to match the domain.

## Contributing

Issues, discussions, and pull requests are welcome. Good contributions add reproducible failure cases, improve clarity without weakening gates, or make the harness easier to adopt across domains.

Read [CONTRIBUTING.md](CONTRIBUTING.md). If this starter is useful, star the repository so other teams can find it.

## License

[MIT](LICENSE) © 2026 Fabien Gréard. Adapted upstream skill material is documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
