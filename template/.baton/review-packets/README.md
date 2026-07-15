# Human-review packets

Store explicit human approval/revision/rejection packets here using [the review template](../templates/review-packet.md). Every approved record points to a dedicated regular Markdown packet here—not this README, a template, or a symlink—and records its reviewer and ISO date. Exactly one canonical human decision may exist per ticket/stage, and exactly one Consultant decision per ticket/Consultant/stage; replace that record transactionally when the decision changes while Git and packets retain history. One stage never substitutes for another.
