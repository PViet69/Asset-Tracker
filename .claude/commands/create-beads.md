---
description: Create br issues/epics from a reference document
argument-hint: <path-to-doc> [extra-context]
---

Create br issues from document `$ARGUMENTS`.

First run `/caveman ultra` for terse comms. Use `/br` skill for all br/bv ops.

Workflow:

1. **Read doc** — Read tool on the path in `$ARGUMENTS` (first arg). If multiple args, treat the rest as extra scoping context. Path missing or unreadable → stop and ask.
2. **Extract work items** — identify epics, issues, acceptance criteria, dependencies, priorities from the doc. Group related items under epics where doc structure implies it.
3. **Propose plan** — show user a numbered list: title, type (epic/feature/bug/task), priority, parent (if any), blockers (if any), 1-line description. No br writes yet.
4. **Confirm** — wait for user approval or edits. Ambiguous scope/title/priority → ask, don't guess.
5. **Create** — via `/br`: create epics first, then children with `--parent`, then wire dependencies with `br dep add`. Use `--json` on all create calls. Resolve actor as `ACTOR="${BR_ACTOR:-assistant}"`.
6. **Verify** — `br dep cycles` returns empty. List created IDs back to user.
7. **Sync** — `br sync --flush-only`

Rules:

- Don't invent acceptance criteria not in doc. Mark gaps as "TBD" and surface to user.
- Preserve doc's wording for titles where reasonable.
- One epic per top-level section unless user says otherwise.
- Do NOT create frontend test issues (e.g., Playwright, component, e2e UI tests). Backend tests OK.
