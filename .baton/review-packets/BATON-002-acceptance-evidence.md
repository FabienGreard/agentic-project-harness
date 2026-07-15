# BATON-002 implementation acceptance evidence

## Boundary

This packet records the corrected unpublished Baton v0.7.0 WIP boundary on `feat/baton-bootstrap-memory`, based on `ebb65efc252e854bbeb4d3f76fa10790a3ec38e1`. It is source-repository evidence, not a consumer payload or release authorization.

No user-owned permanent task was created for this exercise. The user authorized implementation of BATON-002, not an adopter `$bootstrap-baton` run. The live task-provider surface and read-only probes are recorded in [`BATON-002-provider-capability-trace.json`](BATON-002-provider-capability-trace.json): list, create, stable returned identity, read, and send-wake operations are present; list and read succeeded; create and send were deliberately not invoked outside their authorization boundary.

## Agent-rendered conversation recordings

Two disposable read-only tasks exercised the actual installed skill contracts without editing the repository:

- Bootstrap/Management recording: task `019f67c9-1474-7031-af06-9f397ce711c4`.
- Memory recording: task `019f67c9-12a4-73d3-a459-1c2a1e6a4c89`.

Both read the live source contract, produced actual agent-rendered turns, disclosed that the scenario was simulated, and created no task, goal, memory mutation, project intent, or repository file. The complete task outputs remain inspectable by stable task ID; the representative transcript below preserves every required interaction state without private or fabricated live data.

### Bootstrap transcript

| Scenario | Agent-rendered status and content | Single decision question |
| --- | --- | --- |
| Fresh start | `Creating task` then `Online` for Management; Management introduces its named Product Manager identity and asks no project question yet. After the preferred name, Operations and the active Product Designer Consultant are introduced with stable authority labels. | `What name should I use for you?` |
| Project identity | Prior answer is labeled provisional and non-durable. | `What project should this company help you create?` |
| Users | Project identity/purpose remain provisional. | `Who should ClinicFlow serve?` |
| Outcome | Users remain provisional. | `What observable outcome should ClinicFlow produce for them?` |
| Constraints | Outcome remains provisional. | `What known constraints must the team respect?` |
| Unresolved items | Constraints remain provisional. | `What remains unresolved before delivery planning?` |
| Final confirmation | `Ready for confirmation`; one summary covers project, purpose, users, outcome, constraints, team readiness, and unresolved items. It states that confirmation does not authorize tickets, delivery, publication, external commitments, or destructive action. | `Does this summary represent our shared project intent?` |
| Confirmed | `Complete`; the recording states that a real run would show transaction/report/backup paths and that this read-only exercise created none. The playful onboarding tone ends here. | `Should the next Management wake begin outcome-readiness definition?` |
| 768 interruption/resume | `Resumed`; completed provisional answers and all online seats are listed, incomplete questions are listed, no introduction is replayed, and focus returns to the first incomplete item. | `What known constraints must the team respect?` |
| Mixed roster | Management and Operations are `Online`; Product Designer is `Awaiting task`; its prompt includes Consultant ID/title/domain/config path/acceptance boundary. `Discovery available` and `Delivery blocked` are shown together. | `Would you like to continue project discovery while the Product Designer remains Awaiting task?` |
| Task failure/retry | `Could not create task`; the affected Operations seat, preserved progress, exact recovery action, discovery availability, and delivery blocker are named. Retry registers the returned identity/wake path before `Online`. | `Should I retry creating the Operations task now?` |
| Duplicate reconciliation | Exact registered task/personnel/wake identity is reused; display name alone is rejected as identity evidence; no duplicate is created. | `Should I continue from the first incomplete discovery question?` |
| Mature adoption | `Needs Integration`; normal bootstrap stops, existing files/quarantine remain preserved, and the exact reviewed `_activate --from` path is shown. | `Should I prepare a read-only checklist for that reviewed proposal?` |

The recording contains exactly one user-answerable decision question per Management turn. Names are always paired with Management, Operations, or Consultant authority. It exposes no hidden prompt, private claim, live task ID, or persistent-goal operation.

### Memory transcript

| Flow | Agent-rendered behavior | Decision/focus behavior |
| --- | --- | --- |
| Remember | Restates subject/category/meaning, returns a stable claim reference, reports `Saved`, and says what may be influenced without granting authority. | No extra question; focus returns to the composer. |
| Inspect | Reports a privacy-filtered confirmed view with count, source, and stable reference; pending/history data are explicitly excluded. | Reading order is heading, filter status, ordered claims, references, exclusion notice. |
| Personal inference | Reports `Pending confirmation · no effect`, safe meaning, class, source, and stable reference. | `Confirm, correct, reject, or skip this candidate?` |
| Confirm | Previews exact meaning/source/effect, then records `Saved` only after the user's second turn. | Focus moves to the one confirmation question, then returns to the composer. |
| Correct | Shows current and replacement meanings/references and the supersession consequence; the result reports one active claim without duplication. | `Apply this correction?`; non-committing choice receives initial focus. |
| Candidate review | Labels one pending candidate as having no effect and preserves it on skip. | `Confirm, edit-and-confirm, reject, or skip this candidate?` |
| Secret rejection | Reports `Rejected for privacy`, never repeats the supplied value, and states that no claim/history/preview/dashboard/transaction was created. | Offers one safe non-sensitive alternative question. |
| Forget | Previews active removal, candidate clearing, local-history redaction, generated-view refresh, external rollback evidence, and accurate Git/remote/clone/cache/backup retention. | `Confirm forgetting this claim?`; the non-destructive choice receives initial focus. |
| Mutation failure | Reports `Could not save · rolled back`, preserves the last confirmed snapshot and candidate, and shows external recovery references. | One retry question; focus moves to the recovery heading and then the question. |
| Recovery | Reports the affected stable reference, restored-revision result, transaction/report/rollback evidence, and no remaining influence. | Focus returns to the invoking candidate-review position. |

The transcript's reading order always announces heading and literal status before content, consequence, evidence, and the single decision question. It never exposes raw JSON/JSONL, a secret, a forgotten value, or a private claim.

## Representative dashboard recording

The committed source-only projection fixture is [`BATON-002-representative-memory.json`](BATON-002-representative-memory.json). It contains active, awaiting-task, former, and rehired people; Management, Operations, Consultant, and Contractor roles; explicit-user, operational-evidence, self-reflection, and management-assessment sources; reviewed assignment types; repeated-evidence summaries; and safe repository evidence paths.

The fixture was rendered with the candidate `harness_state.py`, served from a disposable directory, and inspected through the in-app browser:

| View | Recorded result |
| --- | --- |
| 320×568 | `clientWidth=scrollWidth=320`; vertical page scrolling available; one memory column; four dossiers; five observable outcomes; ten evidence links; active/awaiting/former/rehired states visible; Company memory status stacks below its description. |
| 768×1024 | `clientWidth=scrollWidth=768`; vertical page scrolling available; two memory columns; four dossiers; five outcomes; ten evidence links; no duplicate organization names. |
| 1440×900 | `clientWidth=scrollWidth=1440`; vertical page scrolling available; two memory columns; four dossiers; five outcomes; ten evidence links; no duplicate organization names and no visible ranking/leaderboard callout. |
| 200% reflow | A 1440×900 desktop surface was retested at its 720×450 effective CSS viewport. `clientWidth=scrollWidth=720`; vertical scrolling available; the memory view reflows to one 660px column; the longest evidence link is 364px inside a 660px panel. The connected browser did not retain a separate page-zoom override, so the effective-viewport method and its exact basis are stated rather than presenting a false native-zoom claim. |

The semantic snapshot exposes one banner, a named tablist, selected tab, main landmark, People/Workload/Company memory regions, ordered personnel/history lists, stable role labels, literal statuses, `Observable outcomes` lists, and `Evidence links` groups. Every displayed outcome, including a repeated-evidence performance summary, has its own source label and deliberate evidence links. Self-reflection renders as `Self Reflection · Unverified`; it is never shown as accepted performance truth. Management and Operations use permanent-seat identity merging, so a differing memory specialty cannot duplicate either person.

## Accessibility and safety evidence

- axe-core 4.11.4, WCAG 2 A/AA, 2.1 A/AA, and 2.2 AA tags: 0 violations and 0 serious/critical violations at 320, 768, and 1440; 26 passes at each width.
- axe marked two checks incomplete rather than failed: `color-contrast` and `aria-prohibited-attr`. Manual measured contrast was 15.39:1 for body text, 16.18:1 for headings, 13.11:1 for muted copy, and 17.52:1 for the focus treatment against the screen background. The semantic snapshot and keyboard run expose each status/name/role through text and no ARIA-dependent meaning was found missing.
- ArrowLeft from Team selects and focuses Mission, updates the canonical URL, and leaves a visible 3px outline plus 6px focus ring. Escape closes the goal dialog, restores focus to the exact invoking goal button, and restores `aria-hidden=true`.
- `prefers-reduced-motion: reduce` matches and computes representative sheet, backdrop, and timeline transition/animation durations to `0.00001s` with one iteration.
- Browser console: zero final warnings/errors.
- Fixture/source assertions reject duplicate permanent seats, candidates, secret values, raw private claims, forgotten values, highest/lowest completion, assignment-share framing, leaderboard framing, and universal scores. Counts remain current-work context, not personnel ranking.

## Reproduction

1. Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_memory tests.test_state_team tests.test_lifecycle`.
2. Render `.baton/state/{project,goals,tickets,ownership,reviews,team}.json` with the projection fixture through `template/.baton/lib/harness_state.py::render_dashboard` into a disposable directory.
3. Serve that directory locally, open `?view=team`, and inspect 320×568, 768×1024, 1440×900, and 720×450 effective-200%-reflow viewports.
4. Run local axe-core 4.11.4 with WCAG 2 A/AA, 2.1 A/AA, and 2.2 AA tags; then verify keyboard tab switching, dialog Escape/focus restoration, measured contrast, reduced motion, and console output.

The immutable remote smoke remains intentionally outside this packet until a human authorizes Release.
