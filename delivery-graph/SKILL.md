---
name: delivery-graph
description: Split a goal into small tasks that trace to requirements, record their real dependencies in the plan, run the ready ones in parallel worktrees when that is safe, and integrate and verify the combined result on one revision. Use when delegated work needs several dependent or parallel tasks, when tasks must land together through an integration branch, or when a multi-task run hits a merge conflict, a moved base, a failed combined check or a crash mid-graph. Not needed for one task or a short sequential chain. Works under delegated-autonomy, which owns the mandate, stop rules, AI routing, gates and communication.
license: MIT
---

# Delivery Graph

A goal larger than one task becomes a graph: tasks, the edges that block
them, and one revision where the result is proven to work as a whole.
This skill covers that graph and nothing else. The `delegated-autonomy`
skill owns the mandate, stop rules, AI routing, gates, the shared machine
and communication; nothing here widens them. Section references (§) point
to it. Without it, get the mandate from the operator before the first
delegation.

## When to use it

| Work | Shape | How it lands |
|---|---|---|
| One task, or a chain where each step needs the previous one | No graph. Sequential loop: build, review, merge, verify, next | One merge per task (§3) |
| Several tasks, some independent, each safe on main alone | `Blocked by` column in the plan; run the ready tasks | One merge per task, main verified after each |
| Tasks that only work together, or that main must not see half-done | Full graph | Integration branch, one verified candidate, then land |

Pick the smallest row that fits. Move down a row only when the work
demands it.

Stay sequential when:

- the tasks touch the same files or the same generated artifacts;
- you can't name each task's write scope yet (explore or spike first);
- the test suite dominates the time: tests queue on the machine lock
  anyway (§4);
- quota or your review capacity is the bottleneck;
- the requirements are still moving.

## 1. Break the goal into tasks

- Start from what the project already has: `REQUIREMENTS.md`, a plan, a
  spec, tickets in a tracker or in local files. Reuse their IDs and
  blocking edges. Don't copy ticket bodies into the plan, and don't open
  tickets in a tracker the project doesn't use. Creating issues on a
  shared tracker is outward-facing: check the mandate first.
- Every task traces to requirement IDs and names the acceptance criteria
  it proves. A task that traces to nothing is scope creep (§2).
- Cut vertical slices: each task is small enough for one fresh context
  and verifiable on its own by a named check. A layer with no check of
  its own is not a task.
- Put enabling refactors first, as their own tasks.
- A wide mechanical change that can't land green in slices goes expand,
  migrate in batches, contract. Batches that can't stay green alone share
  an integration branch.
- Give every task a **write scope**: the files or directories it may
  change. A builder that needs to edit outside it stops and reports.

## 2. Record the graph in the plan the project already has

The graph is a task table in the file that owns the plan, as mapped in
delegated-autonomy section 2 ("Use the project's existing documents").
That can be `IMPLEMENTATION_PLAN.md`, `TICKETS.md` or the `PLAN.md`
template; never a new graph file next to an existing plan. If tickets live
in one file and the plan in another, put the edges where the tickets are,
reuse their IDs, and let the plan link to them. Add the columns you need:
`Blocked by`, `Scope`, and, once merged, `Landed` (branch tip and landing
commit). Template:
[`PLAN.md`](../delegated-autonomy/templates/PLAN.md).

- **Blocked by** lists only real edges: a task whose output this task
  needs, or an open question (`Q1`) whose answer changes this task. A
  preferred order is not an edge.
- An open question blocks only the tasks that list it. Everything else
  keeps moving. Put the question in `REQUIREMENTS.md` with a
  recommendation (§6).
- When a tracker already holds the tickets, it stays the source for
  their content and edges. The plan row points to the ticket ID and adds
  only what the tracker lacks: scope, branch, base, SHA and evidence.

| Status | Meaning |
|---|---|
| `blocked` | Waiting for the tasks or questions in `Blocked by` |
| `ready` | Every blocker satisfied; can start |
| `in progress` | A builder owns it; worktree, branch and base SHA recorded |
| `review` | Builder reported; review bound to its tip SHA |
| `integrated` | Merged into the integration branch, or into main |
| `done` | Its acceptance criteria verified on the revision that lands |
| `stopped` | A stop rule fired; the log says which |

The **frontier** is every `ready` task. Recompute it after each status
change. A blocker is satisfied when its work is merged into the revision
the dependent task starts from, not when its branch looks finished.

## 3. Decide what runs in parallel

Start a ready task next to others only when every row holds:

| Check | Parallel when | Otherwise |
|---|---|---|
| Dependencies | Every blocker is merged into its base | Wait |
| Write scope | No overlap with any running task | Serialize, or merge the two tasks |
| Shared artifacts | No lockfile, migration number, generated fixture, snapshot, checksum, changelog or registry that a running task also touches | One task owns the artifact, or the coordinator writes it at integration |
| Machine | Its tests can wait behind the machine-wide heavy-job lock (§4) | Fewer builders. Parallel builders still test one at a time |
| Routing and review | The recorded AI routing and quota allow it, and you can review each branch when it reports | Queue it |

Two or three builders at once is a practical ceiling. More branches than
you can review is a queue, not progress.

## 4. Brief each builder

Use the [builder brief](../delegated-autonomy/templates/BUILDER_BRIEF.md)
and fill its Scope section: the criteria the task proves, the write
scope, and the base. The base is the full SHA that contains every
blocker; with an integration branch, its tip after the blockers merged,
never a blocker's own branch.

Builders don't merge, rebase onto a moved base, push or open pull
requests. The coordinator owns every merge (§3).

## 5. Integrate and verify

Without an integration branch, merge each reviewed task into main one at
a time (§3) and run the checks on main after each merge. That stays the
default.

With an integration branch:

1. Cut `int/<goal>` from main at a recorded SHA. Record it in the
   Integration block of the plan.
2. When a task's review passes on its tip SHA, merge that tip into the
   integration branch with a merge commit. Don't rebase or squash a
   reviewed branch: the review is bound to its SHA.
3. Run the task's targeted checks on the new integration tip, mark the
   task `integrated` and recompute the frontier.
4. When every task is integrated, the tip is the **candidate**. Run the
   full suite on it behind the lock, and have a fresh reviewer read the
   combined diff (`git diff main...<candidate sha>`, which leaves out
   anything merged from main) for how the tasks interact. Bind both
   results to the candidate SHA.
5. Any later commit (a fix, a merge from main) makes a new candidate.
   Rerun the checks. Old evidence doesn't carry over.
6. Mark tasks `done` once the candidate's checks prove their criteria.
   Landing the candidate on main is the mandate's merge action, free only
   if the mandate says so. Land it with a merge commit, not a squash or
   rebase, so each task's recorded landing commit stays in main's history
   and its branch can be deleted safely. A green candidate or a finished
   graph grants no right to merge, push or deploy.

Branches that pass one by one are not evidence that the whole works.
Only checks on the candidate count.

## 6. When things go wrong

| Event | Do this |
|---|---|
| Merge conflict into the integration branch | Resolve a mechanical conflict in the merge commit and say what you chose. Otherwise brief a fix task based on the integration tip. Add the edge or scope rule the graph was missing |
| Candidate fails while every branch passed | Fix it in its own commit on the integration tip (§3), or brief a fix task. To find the cause, check the merge commits in order, one heavy job at a time |
| Main moved | Keep building on the recorded base. Before the candidate run, merge main into the integration branch in its own commit. Review that merge too if main changed files in any task's scope |
| A blocker changed after a dependent task started | Keep the dependent branch. Merge it into the integration branch and run its checks there; don't ask the builder to rebase |
| A task hits a stop rule | Mark it `stopped`. Its dependents stay `blocked` on it; independent tasks continue (§1). Don't merge it. If it is already merged and causes a failure, revert it on the integration branch in its own commit. Landing without it is a plan change (§2) |
| A builder died or was stopped | Inspect its worktree, commit the WIP, and resume with a brief that names that commit (§2). Don't relaunch from scratch |
| Resume after a crash | Rebuild the frontier from the plan file and git, not from memory: which task branches exist, which are merged (the `Landed` record matches, see [`merged-branch-check.md`](../delegated-autonomy/reference/merged-branch-check.md); a branch that only looks unmerged is kept, never force-deleted), which worktrees hold uncommitted work, which agents are alive |

Clean up task worktrees and branches as §3 says. Delete the integration
branch only after main holds it.

## Example: three tasks

Goal: users can download a report as CSV. R1: the CSV opens correctly in
a spreadsheet. R2: a 1M-row report exports without a timeout. Main must
not show a half-done export, so the tasks share an integration branch.

| Task | Traces to | Blocked by | Scope | Status |
|---|---|---|---|---|
| T1 CSV writer with quoting and encoding | R1 | - | `src/export/csv*`, its tests | ready |
| T2 Streaming report query | R2 | - | `src/report/query*`, its tests | ready |
| T3 Export endpoint that streams T2 through T1 | R1, R2 | T1, T2, Q1 | `src/api/export*`, its tests | blocked |

Q1: which permission does the endpoint require? It blocks T3 only.

1. Cut `int/csv-export` from main at `<sha-A>`. T1 and T2 have disjoint
   scopes and share no artifacts, so two builders start from `<sha-A>`.
   Both want a changelog line; the coordinator writes it at integration.
   Their tests queue on the machine lock. Ask the operator Q1 meanwhile.
2. T2 reports at `<sha-T2>`. Review it on that SHA, merge it into the
   integration branch, run T2's checks on the new tip. T1 follows the same
   way. The integration tip is now `<sha-C>`.
3. The operator answers Q1, and both blockers are merged, so T3 is ready.
   Brief it with base `<sha-C>` and Q1's answer.
4. Main moves to `<sha-A2>`. Merge it into the integration branch in its
   own commit; it touched no task scope.
5. T3 merges. The full suite on that candidate fails: T2's query closes
   its cursor before T3 finishes writing. Each branch passed alone. Fix it
   in its own commit on the integration branch, have it reviewed, and run
   the full suite on the new candidate `<sha-E>`: green. A fresh review of
   `main...<sha-E>` passes. Record both against `<sha-E>` and mark T1
   to T3 `done`.
6. Landing `<sha-E>` on main follows the mandate. If merging to main is
   reserved, ask with the evidence and wait. Then clean up the worktrees
   and branches.

A Q1 answer that never comes stops T3 only. T1 and T2 still land if the
operator approves landing without T3.

## Credit

The task graph, frontier, vertical slices, expand-contract batches and
integration branch are adapted from Matt Pocock's `to-tickets` and
`implement-spec` skills (https://github.com/mattpocock/skills, MIT
License, Copyright (c) 2026 Matt Pocock). The ideas are reworked here;
no text is copied.
