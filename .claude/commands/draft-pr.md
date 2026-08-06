---
description: Draft a PR description for current branch into a target branch in markdown
argument-hint: <target-branch (default to `origin/main`)>
---

Draft a PR description for merging the current branch into the target branch.

The target branch is provided as `$ARGUMENTS`. If no argument is given, default to `main`.

Steps:

1. **Determine target branch** — use `$ARGUMENTS` if provided, otherwise `main`. Call it `TARGET`.

2. **Gather context** — run these in parallel:
   - `git log TARGET..HEAD --oneline` — list commits on this branch
   - `git diff TARGET...HEAD --stat` — files changed
   - `git diff TARGET...HEAD` — full diff for detail
   - `git log TARGET..HEAD --format="%B" | head -200` — full commit messages

3. **Synthesize** — from commits + diff, identify:
   - What changed (feature, fix, refactor, chore)
   - Why (motivation, problem solved)
   - Breaking changes or migration notes if any
   - Related br issue IDs found in commit messages

4. **Output** — print the PR description as a markdown block the user can copy:

```markdown
## Summary

<!-- 2-4 bullet points: what this PR does and why -->

## Changes

<!-- Key changes grouped by area, not a commit list -->

## Test plan

<!-- Checklist of what to verify before merging -->

## Notes

<!-- Breaking changes, migrations, follow-up issues, anything reviewer should know -->
```

Rules:
- Keep summary bullets tight (1 line each)
- Changes section: group by area, omit trivial chores
- Test plan: concrete steps, not vague "test the feature"
- Only include Notes section if there's something non-obvious
- No co-authored trailer, no template boilerplate left unfilled
- No em dashes (—); use a hyphen or rewrite the sentence
