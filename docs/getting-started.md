# Getting started

## 1. Create from the template

Use GitHub's **Use this template** action. Do not fork unless you want to contribute changes back to the harness itself.

## 2. Define outcome before implementation

Replace `docs/direction.md` and `docs/overview.md` with verified project facts. Name the human owner, first usable outcome, constraints, non-goals, and external review gates.

## 3. Choose roles deliberately

Most projects need only a Project Director and Delivery Lead. Add a Specialist Lead when the same expert domain repeatedly defines readiness or accepts results. Use disposable expertise for one-off questions.

## 4. Create the first bounded work

Record durable choices under `docs/decisions/`, substantial requirements under `docs/prds/`, executable work under `docs/tickets/`, and results under `docs/implementation-reports/`.

## 5. Synchronize machine state

Update `docs/project-state.json` whenever ticket, active ownership, baton, or human-review status changes. Run the static evaluator before handoff.

## 6. Commit governance before execution

A durable baseline makes subsequent implementation reviewable and prevents conversation history from becoming the only source of truth.
