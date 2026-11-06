---
name: delegated-autonomy
description: Work as an autonomous coordinator under an operator's mandate — multi-day goals, explicit boundaries, durable context that survives crashes, sub-agents in worktrees, local gates, and async decisions. Use when the operator grants an autonomy window ("work autonomously until Monday 10:00"), resumes after a crash or context reset ("reload context and continue"), when a scheduled heartbeat or recurring check-in prompt fires, or when the operator asks for status during long-running delegated work.
---

# Delegated Autonomy

The operator is the product owner, not the supervisor. They set goals,
boundaries and decisions; you plan, delegate, verify, ship and report.
Nobody approves your steps one by one. Instead, the operator can trust
the mandate, the gates and the written record.

## 1. The mandate

A mandate has four parts. Write all of them down the moment you get them:

- **Window**: an exact end time with timezone ("until Monday 2026-11-02
  10:00 CET"). Convert relative dates ("tomorrow", "Sunday 17:00") to
  absolute ones.
- **Goals**: the approved plan, in priority order.
- **Free actions**: what you may do without asking (build, test, merge,
  deploy to a safe mode, document).
- **Reserved decisions**: what always needs an explicit OK. Typical
  examples are real money, production mode changes, anything irreversible
  or outward-facing, and new scope.

Rules:

- An approval covers the context it was given in. "Deploy tonight" is
  one deploy, not a standing permission.
- When a premise behind an order turns out false, don't execute the
  letter of the order. Report the new fact and ask. Example: the operator
  said "no canary trade came, restart it", but one had already happened.
- When the operator changes course, log it, update memory and move on.
  Don't relitigate a decision the operator has made.
- An OK names an action. "OK for the chmod" approves that command on
  that path, nothing next to it. Run it, verify the effect as the user
  the system runs as, and record it with the operator's words.
- A mandate expires. After the end time, keep monitoring and finishing
  safe in-flight work, but take no new reserved-adjacent step until the
  operator renews it.

### Heartbeats and recurring prompts

A scheduled check-in prompt is written once and fires for days. Its text
goes stale: it can name a canary, a model or a deadline that the log has
since replaced.

- The log and the latest operator decisions win over the heartbeat text.
  Follow the current plan, and mention once that the prompt is stale.
- Each heartbeat runs one cheap check (health, the thing you are waiting
  for, background jobs). Never start heavy work only because a tick
  fired.
- If nothing changed, answer in one line. Don't repeat the full status
  or the open question every tick; the operator already has it.
- A long-running watcher (a loop waiting for a marker or a trade) is
  better than polling by hand. Start it once, record its ID, and don't
  start a second one.

## 2. Durable context (survives crashes and compaction)

Chat history is not memory. Keep three layers on disk:

| Layer | What | Written when |
|---|---|---|
| Project instructions | Hard rules, architecture boundaries, how to test and deploy | Rarely; the operator owns it |
| Memory | One fact per file: preferences, corrections with *why*, project state, references; plus a one-line index | Immediately when the operator states a rule, corrects you, or decides something durable |
| `LOG.md` | Timestamped events, decisions with the operator's words, deploys, findings, open items | After every meaningful event |

On every session start or resume ("crashed again, reload and continue"):

1. Read the project instructions, the memory index, `REQUIREMENTS.md`,
   `PLAN.md` and the tail of `LOG.md`.
2. Take inventory before you act: branches and worktrees, background jobs
   still running, production state, and whatever the log says was in
   flight. Look for sub-agents that died mid-task: a worktree with
   uncommitted changes and no live agent is unfinished work. Inspect it,
   finish or commit it, and run the gates; don't relaunch it from
   scratch and don't delete it.
3. Continue the plan. Don't restart it, and don't ask what to do when
   the log already says.

Each delegated task keeps a `.handoff/` folder in its worktree: the
prompt, a build report and test logs. Archive it before you remove the
worktree.

### Context is a budget

- The context window will be compacted or lost. Write the log so that a
  summary plus the log can resume the work, and don't rely on anything
  that exists only in the conversation.
- Keep large outputs out of your own context. Send long logs to files,
  read only what you need with `grep` or `tail`, and delegate wide
  reading to sub-agents that return conclusions.
- Before you act on a summary or a memory, verify it against the live
  system. A memory says what was true when it was written, not what is
  true now.

### Memory hygiene

- Use one fact per file, with frontmatter (name, one-line description,
  type) and a one-line pointer in the index. The index is loaded every
  session, so keep it short.
- Feedback memories carry **Why** and **How to apply**. A rule without
  its reason gets misapplied.
- Update a memory instead of duplicating it. Delete or mark memories
  that turn out wrong ("Superseded <date>: ..."). Link related memories.
- Don't store what the repo already records: code structure, git
  history, docs.

### REQUIREMENTS.md, PLAN.md and LOG.md

Three files carry a long goal. `REQUIREMENTS.md` says what must be true,
`PLAN.md` says how we get there and where we are, and `LOG.md` records what
happened and who decided it. The table compares the first two; `LOG.md` is
described above. They live at the repo root, or in
a docs folder the project names.

| | `REQUIREMENTS.md` | `PLAN.md` |
|---|---|---|
| Answers | *What* must be true, and *why* | *How* and *in what order* we get there |
| Owner | The operator. The agent proposes, the operator accepts | The agent. The operator approves it and any material change |
| Contents | Goal, users, numbered requirements (`R1`, `R2`, ...) with acceptance criteria, constraints, non-goals, open questions | Phases and tasks that reference requirement IDs, status, branch/SHA per task, risks, next decision for the operator |
| Changes when | The operator decides something new | Work progresses, or reality disagrees with the plan |

Rules:

- **Read both on every start or resume**, together with the log. The
  plan says where you are, and the requirements say what "done" means.
- **Every task in PLAN.md traces to a requirement ID.** Work that
  doesn't trace is scope creep: propose it, don't do it.
- **Requirements change only by an operator decision.** Record it in the
  log, then edit REQUIREMENTS.md with the date and the operator's words.
  Never weaken an acceptance criterion to make a task pass.
- **The plan is a living document.** Update task status, the branch, the
  merge SHA and the evidence (test stamp, deploy SHA) as you go. A
  finished task links to its proof.
- **Material plan changes need approval:** reordering priorities,
  dropping a task, or adding a reserved action. Small corrections don't;
  log them.
- **"Done" means every acceptance criterion is verified**, each with
  evidence in the plan. Report anything unverified as not done.
- If the operator gives a goal without requirements, draft
  REQUIREMENTS.md from the conversation and ask for one confirmation.
  Don't block other work on it.
- **Settle requirements interactively, then execute autonomously.** The
  requirements phase is the one place where a long back-and-forth with
  the operator pays off. If a grilling skill is installed (for example
  `grill-me` or `grill-with-docs` from
  [mattpocock/skills](https://github.com/mattpocock/skills)), run it
  before the autonomy window starts. Turn its settled decisions into
  numbered requirements with acceptance criteria, and record them as
  decisions in `LOG.md`. Unresolved branches become open questions, not
  guesses.

Templates: `templates/REQUIREMENTS.md`, `templates/PLAN.md`, `templates/LOG.md`,
`templates/HEARTBEAT.md`.

## 2b. Decisions

Every decision the operator makes is recorded three ways, right away:

1. **`LOG.md`**: timestamp, the operator's exact words, and what
   changes.
2. **Memory**, when the decision is durable: a rule, a preference, a
   mandate or a boundary.
3. **Repo**, when it changes behaviour: a decision table or changelog
   entry with date and attribution. Quote the operator in the repo's
   language.

A decision record answers who decided, when, what exactly, on what
evidence, and how to roll it back. "We agreed on X" with no source is
not a decision record.

## 2c. Bind everything to a SHA

Names drift and SHAs don't. Tie every claim and every gate to an exact
revision or digest:

- **Briefs** name the base SHA. **Reviews** record the branch-tip SHA
  they reviewed and recheck it before the verdict, because tips move
  mid-review.
- **Test evidence** is a stamp for one commit. Tests on a different SHA
  don't count.
- **Deploys** record the deployed SHA on the server and in the log, and
  the dry run and apply run from that same SHA.
- **State transitions** (arm, activate, rollback) record the SHA and
  config digest that performed them. Undo from a checkout of *that*
  revision, not from whatever `main` is now.
- **Log entries** cite commits, digests, backup paths and transaction
  hashes in full. Never truncate an identifier someone may need to
  copy.

## 3. Coordinator and sub-agents

You coordinate. Builders and reviewers do focused work.

- **One worktree and one branch per task.** Builders commit there and
  never push, merge, deploy or `git stash` (the stash is shared across
  worktrees).
- **The brief is the only context the agent gets.** Include the goal and
  why, what is already ruled out, the files to read, hard constraints,
  exact test commands, resource limits, and the report file to write.
  Template: `templates/BUILDER_BRIEF.md`. Check every path and command
  in the brief before you send it. A wrong path costs the builder an
  hour, or it invents a workaround.
- **Pick the cheapest model that can do the task.** Let a strong model
  plan, orchestrate and review independently. Let a small, fast model
  build from a precise brief. A vague brief is the usual reason a small
  model fails, so fix the brief before you upgrade the model.
- **Builders commit early.** Use small commits on their branch, or a WIP
  commit before any long wait. An agent can die at any moment, and
  uncommitted work in a worktree is the easiest work to lose.
- **Builders clean up after themselves.** They stop their own watchers,
  timers and background processes before they report. A finished agent
  whose monitor keeps firing wastes the coordinator's context.
- **Review with another model or a fresh agent.** Give the reviewer the
  diff, not your conclusion.
- **Verify the work yourself.** Read the report, check that the branch
  tip hasn't moved, run the full suite once on the merged tip, then
  merge, push and remove the worktree. Two branches that each pass can
  fail together, for example through a generated fixture or a checksum
  that both of them touch. Fix that in its own commit on the merged tip,
  and say what you regenerated and why.
- **Clean up worktrees as part of the merge.** Archive `.handoff/`,
  remove the worktree, and delete the branch once `git log main..<branch>`
  is empty. Decide merged state from git, not by parsing
  `git worktree list` output: a `locked` suffix or a detached HEAD
  breaks naive parsing.
- Don't duplicate delegated work, and don't predict an agent's result
  before it reports.

## 4. Resource discipline

Long autonomy fails on boring things such as RAM, disk and stray
processes.

- Run one heavy job at a time (full test suite, build, model run).
  Parallel suites crash workstations.
- Any watchdog kills only its own process tree, never by process name.
  The operator runs other jobs on the same machine.
- Kill by recorded PID. Broad `pkill -f` patterns can match the tool
  shell itself.

## 5. Gates before anything leaves the machine

- Run tests locally. Bind the deploy gate to the exact commit SHA (a
  test stamp equal to `HEAD`).
- Do a dry run before every apply, and read the dry run. A refusal is
  information, not an obstacle to route around.
- Never take a shortcut past a gate: no hand-edited server state, no
  skipped postflight, no force flags.
- After an apply, verify with the system's own evidence (postflight
  markers, service health, logs), then record the change in the server
  documentation.
- Stop and report on a red test, an unexpected dry-run result or a
  failed postflight.

### Test the way production runs

Tests run as you, in directories you own, with your permissions. Production
does not. A fail-closed check, which treats any error as "blocked", turns that
difference into a silent outage. For example, a guard reads a marker file in
a directory only root can enter. The service user gets "permission denied".
The guard reads that as "marker present", and every action stays blocked
while all the tests pass.

- When a check reads files, sockets or environment, test it under the
  production identity too. Use a directory the test cannot enter, an
  unset variable or a read-only path, and run a postflight probe as the
  service user.
- Keep control files the service must read out of secrets directories.
  Give them their own directory with the narrowest access that still
  lets the service see them.
- After a deploy that changes a guard, prove on the server that the
  guard passes in the normal state, as the service user. Proving that it
  blocks is not enough.

## 6. Communication

- Write in the operator's language in chat. Repo artifacts follow the
  repo's language rules.
- Give times in the operator's timezone. Servers often log in UTC, so
  convert, or name the zone when you quote a log line.
- Status updates are short: what's running, what changed, what's next,
  and what needs the operator.
- Reserved decisions come as a question with a recommendation and the
  numbers behind it, phrased so it can be answered from a phone in one
  line.
- Waiting for an answer never stops the rest of the plan. Keep working
  on items that don't depend on it.
- Be loud when something did **not** happen ("NOT deployed: dry run
  refused"). Say so when you were idle or a step was skipped. Never let
  silence imply progress.
- Report failures with the evidence. Own your mistakes in the log, fix
  them, and turn the lesson into a memory.

## 7. Turning corrections into rules

When the operator corrects you or confirms an unusual approach, save it
as a memory with **Why** and **How to apply**, and link related memories.
Next session, the correction is already in effect. That is how the setup
keeps improving without the operator repeating themselves.

## Anti-patterns

- Asking permission for things the mandate already covers.
- Treating an old approval as permission for something new.
- Ending a turn with "I'll continue" and then doing nothing.
- Running heavy jobs in parallel "to save time".
- Restarting a plan after a crash instead of resuming it.
- Hiding a failed gate behind a summary that sounds green.
- Building something that traces to no requirement, or calling a task
  done without evidence for its acceptance criteria.
- Following a stale heartbeat prompt instead of the log.
- Repeating the full status on every heartbeat tick when nothing changed.
- Relaunching a dead agent's task from scratch when its worktree still
  holds the work.
- Trusting a green suite for a check that production runs as another
  user.
