# Use External Notifications Only for Actionable Decisions

Title:
Use External Notifications Only for Actionable Decisions

Type:
Rule

Purpose:
Reach an approved recipient for a material decision or risk without creating noise, exposing private information, or splitting the authoritative record.

Scope:
Email, chat, issue comments, alerts, and other notifications sent outside the repository's normal control plane.

Definition:
Send an external notification only when the exact recipient and channel are explicitly approved and a material blocker, time-sensitive decision, review-ready boundary, urgent invalidation, or material risk requires attention. The notification directs the recipient back to the authoritative repository or task record; it never becomes a separate approval record.

How to Apply:

1. Update authoritative repository state first.
2. Verify the exact recipient and channel were explicitly approved and are currently available.
3. Confirm the event is material and that the same unchanged condition has not already been notified.
4. Include the controlling record, requested decision or review, consequence of delay, and return path.
5. Record only the notification event, channel type, purpose, and pending trigger; keep recipient details and credentials outside versioned files.

Do:

- Link or direct the recipient to the durable record.
- Keep sensitive information out of broad notifications.
- Send one concise, actionable alert after state is consistent.

Don't:

- Use messages to replace tickets, decisions, or ownership records.
- Guess a recipient, address, account, or channel.
- Send routine status, test messages, or unchanged reminders.
- Treat delivery, an external reply, or silence as approval.
- Commit to external publication without authority.

Example:

- After a release candidate enters a declared human-review gate, an approved channel may receive one concise alert naming the candidate, decision needed, consequence of delay, and authoritative review task.

Validation:
Every notification maps to an approved recipient/channel and a material event, points to consistent authoritative state, is not an unchanged duplicate, contains no private recipient detail or secret, and does not claim approval by delivery alone.

References:

- `docs/workflow.md`
- `docs/active-work.md`

Notes:

- Human-review gates must be explicit in both state and the notification requesting approval.
