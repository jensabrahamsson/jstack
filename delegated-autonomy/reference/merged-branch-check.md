# When is a task branch safe to delete?

Deleting a branch or worktree that still holds unmerged work loses it. Git
offers three signals. Each was tested against real merge shapes with
`merged-branch-cases.sh`, which prints the rows below (git 2.38 or later,
for `merge-tree --write-tree`):

| Case | `merge-base --is-ancestor` | `git cherry` `+` lines | `merge-tree` equals main |
|---|---|---|---|
| Merge commit | yes | 0 | yes |
| Fast-forward | yes | 0 | yes |
| Branch rebased, then fast-forward | yes | 0 | yes |
| Rebase merge, clean (new commits) | no | 0 | yes |
| Rebase merge with a conflict | no | 1 | no |
| Squash merge, clean | no | 2 | yes |
| Squash merge with a conflict | no | 2 | no |
| Squash merge, then main changes the same lines | no | 2 | no |
| Squash merge, then a new commit on the branch | no | 3 | no |
| Merged, then a new commit on the branch | no | 1 | no |
| Merged, then reverted on main | yes | 0 | yes |
| Never merged | no | 2 | no |
| Never merged, main made the same edit | no | 1 | no |

What this shows:

- **In these 13 cases, every signal failed only in the safe direction:**
  it said "not merged" for some merged branches and never "merged" for a
  branch with unique work. That is observed behaviour for these shapes,
  not a proof for every possible history (octopus merges, filtered or
  rewritten history, submodules and partial clones are untested). Treat
  the signals as heuristics; the landing record is the evidence.
- **None of them proves a squash or rebase merge that needed conflict
  resolution, or one main changed afterwards.** Those branches look
  unmerged forever, so a rule based on these signals alone either leaks
  branches or tempts someone to force-delete.
- **"Merged" is not "still in main".** A merge that was later reverted
  reads as merged. Deleting is still safe (the commits stay reachable
  from main), but the task is not done.

## The rule

1. **Record the landing.** When the coordinator merges a task, write the
   task's branch tip SHA and the landing commit on main into the plan's
   task row. That record, not a heuristic, is the primary evidence.
2. **Delete only when** the branch tip still equals the recorded tip (no
   commits since), the landing commit is an ancestor of `main`, and the
   worktree has no uncommitted changes.
3. **Without a record,** the git signals are a fallback heuristic, not
   proof. Delete only when `git merge-base --is-ancestor
   <branch> main` holds, or `git cherry main <branch>` prints no `+`
   lines, or `git merge-tree --write-tree main <branch>` equals
   `git rev-parse 'main^{tree}'`, and the worktree has no uncommitted
   changes. Otherwise keep the branch and list it for the operator; never
   force-delete it.
