# Architecture Review Report Format

Create a single timestamped HTML file outside the repository. Keep it readable without a build step. Use inline CSS and optional Mermaid loaded from a CDN only for graph-shaped dependency, flow, or sequence diagrams. Escape all repository-derived text before inserting it into HTML.

## Required report contract

The document must identify the repository, review date, scanned scope, current Git reference, and legend. State that proposed-after diagrams are hypotheses, not approved changes. Use solid boxes for modules, dashed lines for seams, red arrows for leaked knowledge, and a thick dark box for a proposed deep module.

Include at most three candidate cards. Each card must include a short title and stable anchor; recommendation-strength and dependency-category badges; exact files, callers, and relevant tests; evidence and problem; a deepening direction without inventing an interface; gains in depth, leverage, locality, or test surface; accepted ADR support or conflict; ownership/readiness; and side-by-side **Current** and **Proposed direction — not approved** diagrams.

End with one top recommendation naming the strongest evidence, safe checkpoint or blocker, and a link to its card. Do not turn the recommendation into authorization to refactor.

## Diagram and language rules

Use Mermaid only when needed for dependency, call-flow, lifecycle, or sequence diagrams. Use `seam` for a replaceable location. Keep `boundary` for package, authority, ownership, or task scope. Prefer observable wins such as “tests use one interface” or “policy returns to one owner.”
