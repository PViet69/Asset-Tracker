---
description: Implement a br issue or epic by ID
argument-hint: <br-id>
---

Implement br issue/epic `$ARGUMENTS`. If no ID provided, stop and ask user for one.

First run `/caveman ultra` for terse comms. Use `/br` skill for all br/bv ops and `/cavecrew` skill for code investigation, edits, review.

Workflow:

1. **Fetch** — via `/br`: load `$ARGUMENTS` (title, description, acceptance criteria, status, type, dependencies).
2. **Classify** — if epic, via `/br`: list only `ready` children of `$ARGUMENTS` (no open blockers), show to user, ask which to implement (or run sequentially if all ready). Else proceed with the single issue.
3. **Check deps** — via `/br`: verify blockers are `closed`. If not, surface and stop.
4. **Investigate** — via `/cavecrew` (investigator): locate relevant files/symbols, map call sites.
5. **Plan** — short implementation plan in conversation. No separate doc unless asked.
6. **Status → in_progress** — via `/br`.
7. **Implement** — via `/cavecrew:builder` for edits. Ensure each one only edits 3 files max
8. **Verify** — tests / typecheck / lint on changed files.
9. **Review** — via `/cavecrew` (reviewer) on the diff.
10. **Close** — via `/br`: close target issue. Separate tool call from git commit (per repo feedback).
11. **Check branch** — verify current branch starts with `feat/` and name reflects the task/epic (e.g. `feat/gg-ai-data-viz-1234-short-description`). If not, ask user to switch or create appropriate branch before committing.
12. **Commit** — stage related files + `.beads/`. Message references br ID. No co-authored trailer.

Ambiguous requirements → ask user before guessing.
