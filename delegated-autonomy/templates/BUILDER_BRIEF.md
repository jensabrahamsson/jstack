# Builder brief: <task>

You are a builder. Work only in `<worktree path>` on branch `<branch>`
(cut from `<base sha>`). Commit there. Do not push, merge, deploy, touch
production or `git stash`.

## Goal
<What and why, in two to five sentences. Quote the operator's decision
with its date.>

## Scope
- Traces to: <R-ids>. Proves: <acceptance criteria this task must meet>.
- Base `<base sha>` already contains: <blocking tasks, or "nothing">.
- Write scope: <files or directories>. If the task needs a change outside
  it, stop and report; don't make the change.

## Already known / ruled out
- <facts you established, so the builder does not redo them>

## Read first
- <files, docs, prior reports>

## Constraints
- <hard rules: protected paths, language, data safety, no secrets in output>
- Run every test process through the machine-wide lock:
  `<lock command> <test command>`. Never run the full suite (the
  coordinator does that).
- Never run `git stash`, `git reset`, `git checkout -- .` or `git clean`.
- Commit early on your branch. Before a long wait, make a WIP commit so the
  work survives if you are stopped.
- If the code runs as another user or role in production, test the
  permission-denied case too. Fakes return exactly what the real
  interface returns.
- Stop every watcher, timer and background process you started before you
  report.

## Tests
```
<exact targeted test commands>
```

## Deliverable
Write `.handoff/BUILD_REPORT.md` with these sections: base SHA and tip
SHA, commits, files changed (and any outside the write scope), decisions
and why, test commands and pass counts, open risks, anything that blocks
the next step. Return a five-line summary.
