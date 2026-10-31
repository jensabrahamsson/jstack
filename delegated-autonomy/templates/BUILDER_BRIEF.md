# Builder brief: <task>

You are a builder. Work only in `<worktree path>` on branch `<branch>`
(cut from `<base sha>`). Commit there. Do not push, merge, deploy, touch
production or `git stash`.

## Goal
<What and why, in two to five sentences. Quote the operator's decision
with its date.>

## Already known / ruled out
- <facts you established, so the builder does not redo them>

## Read first
- <files, docs, prior reports>

## Constraints
- <hard rules: protected paths, language, data safety, no secrets in output>
- Run one test process at a time. Never run the full suite (the
  coordinator does that).

## Tests
```
<exact targeted test commands>
```

## Deliverable
Write `.handoff/BUILD_REPORT.md` with these sections: commits, files
changed, decisions and why, test commands and pass counts, open risks,
anything that blocks the next step. Return a five-line summary.
