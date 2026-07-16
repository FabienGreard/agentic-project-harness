# Records

Keep one flat folder per scope: `.baton/records/PROJECT/`, `.baton/records/<GOAL-ID>/`, or `.baton/records/<TICKET-ID>/`.

`PROJECT` holds project-wide `decision-<slug>.md` and evidence; approved direction remains in `.baton/state/project.json`. Goal and Ticket folders may contain `brief.md`, `decision-<slug>.md`, `report.md`, `review-<stage>-<reviewer>.md`, and evidence. State links every record. Evidence may remain elsewhere in the repository. Load only linked Project records and the controlling Goal and Ticket folders.
