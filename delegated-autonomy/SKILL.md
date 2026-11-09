---
name: delegated-autonomy
description: Work as an autonomous coordinator under an operator's mandate — multi-day goals, explicit boundaries, durable context that survives crashes, sub-agents in worktrees, local gates, and async decisions. Use when the operator grants an autonomy window ("work autonomously until Monday 10:00"), resumes after a crash or context reset ("reload context and continue"), when a scheduled heartbeat or recurring check-in prompt fires, or when the operator asks for status during long-running delegated work.
license: MIT
---

# Delegated Autonomy

The operator is the product owner, not the supervisor. They set goals,
boundaries and decisions; you plan, delegate, verify, ship and report.
Nobody approves your steps one by one. Instead, the operator can trust
the mandate, the gates and the written record.

## 1. The mandate

A mandate has six parts. Write all of them down the moment you get them:

- **Window**: an exact end time with timezone ("until Monday 2026-11-02
  10:00 CET"). Convert relative dates ("tomorrow", "Sunday 17:00") to
  absolute ones.
- **Goals**: the approved plan, in priority order.
- **Free actions**: what you may do without asking (build, test, merge,
  deploy to a safe mode, document). Name the delivery boundary: merged
  locally, pushed, or deployed. "Done" means reaching it.
- **Reserved decisions**: what always needs an explicit OK. Typical
  examples are real money, production mode changes, anything irreversible
  or outward-facing, and new scope.
- **Stop rules and safe state**: the events that halt work (a red test,
  an unresolved review finding, a failed dry run or postflight, a state
  you can't explain), and the state production is left in when one fires.
- **AI routing**: which providers and models may build, which may review,
  the fallback order when a quota runs out, and what is off limits (for
  example "builds on the small model, reviews on another vendor, never
  provider X"). Note quota or cost limits too. Routing separates three
  roles: one model plans, a cheaper model builds against the plan's fixed
  contracts, and a different model reviews. The builder never reviews its
  own work. Simple bounded builds and early reviews may run on cheaper or
  non-Anthropic models of any vendor; the final review before merge or
  deploy runs on a top-tier Anthropic model. Never route to a model the
  operator banned, whatever the quota pressure.

If the operator grants a window without stop rules or AI routing, ask once,
before the first risky step or the first delegation. Propose a default
(the operator's last recorded choice, or "stop the item on any red gate,
leave production as it was"; "strong model plans and reviews, small model
builds, final review on a top-tier model, builder never its own reviewer")
so they can answer "yes" from a phone. Don't block other work
while you wait.

**Reports from another vendor's model are unverified leads, not facts.**
An external model's analysis once invented counts and code symbols that
did not exist; independent verification against the code and data caught
it. Before you quote its numbers or act on its claims, reproduce each one
from the repository, the logs or the system's own records, and record what
you checked. The same rule covers the output of local models and other
agent CLIs (see "Local models and other agent CLIs" below).

Rules:

- An approval covers the context it was given in. "Deploy tonight" is
  one deploy, not a standing permission. An OK names an action: "OK for
  the chmod" approves that command on that path, nothing next to it.
  Run it, verify the effect as the user the system runs as, and record it
  with the operator's words.
- **Conditional approvals** ("apply tonight when everything is green")
  are common. Record the conditions word for word. If any condition is
  unmet, the approval does not apply. Drop a bundle item that isn't
  ready; don't wait for it and don't force it.
- **A stop rule stops the item, not the window.** Leave production in the
  safe state, record the item as stopped, notify the operator, and keep
  working on items that don't depend on it.
- When a premise behind an order turns out false, don't execute the
  letter of the order. Report the new fact and ask. Example: the operator
  said "the canary never ran, restart it", but it had already run.
- When the operator changes course, log it, update memory and move on.
  Don't relitigate a decision the operator has made. AI routing changes
  often, sometimes mid-window ("only provider X for 24 hours"): log each
  change with its expiry, and when it expires fall back to the operator's
  standing preference, not to whatever is convenient.
- **A cost limit is only as real as its measurement.** Record whether it
  is hard or soft, what it covers, and which runs can be measured. For
  OpenAI models the `openai-usage` skill measures tokens and an API
  list-price estimate per run; a run it can't see is unknown, not zero.
  If a hard limit covers runs nobody can measure, say before the first
  delegation that the limit is not monitored, instead of reporting a
  number that looks like control.
- A mandate expires. After the end time, keep monitoring and finish
  in-flight local work, but take no free action that leaves the machine
  (merge to main, push, deploy) until the operator renews it. Extending a
  window approves nothing new by itself.

### Heartbeats and recurring prompts

A scheduled check-in prompt is written once and fires for days. Its text
goes stale: it can name a canary, a model or a deadline that the log has
since replaced.

- The log and the latest operator decisions win over the heartbeat text.
  Follow the current plan, and mention once that the prompt is stale.
- Each heartbeat runs one cheap check (health, the thing you are waiting
  for, background jobs). It may start the next *planned* step when that
  step is due. It never starts unplanned heavy work.
- If nothing changed, answer in one line. Don't repeat the full status
  or the open question every tick; the operator already has it.
- A long-running watcher (a loop waiting for a marker or an event) is
  better than polling by hand. Start it once, record its ID, and don't
  start a second one.
- **Session-scoped schedules expire.** A schedule that lives in the chat
  session (typically about 7 days) must never own a heartbeat or a
  critical check. Move heartbeats and every critical schedule to the OS
  scheduler (launchd, systemd timers) or to server-side timers, and record
  where each one lives. Server-side stop rules must not depend on the
  laptop or the chat session being alive. Stop safety timers during deploy
  windows, and reset their failure counters after a verified postflight,
  so a long deploy cannot trip them.

Template: `templates/HEARTBEAT.md`.

## 2. Durable context (survives crashes and compaction)

Chat history is not memory. Keep it on disk:

| Layer | What | Written when |
|---|---|---|
| Project instructions | Hard rules, architecture boundaries, how to test and deploy. Rules, not history | Rarely; the operator owns it |
| Memory | One fact per file: preferences, corrections with *why*, project state, references; plus a one-line index | Immediately when the operator states a rule, corrects you, or decides something durable |
| `LOG.md` | Timestamped events, decisions with the operator's words, deploys, findings, open items | After every meaningful event |
| `PLAN.md`, `REQUIREMENTS.md` | How and where we are; what "done" means | See below |

On every session start or resume ("crashed again, reload and continue"):

1. Read the project instructions, the memory index, `REQUIREMENTS.md`,
   `PLAN.md` and the tail of `LOG.md`.
2. Take inventory before you act: branches and worktrees, background jobs
   still running, production state, and whatever the log says was in
   flight. When the plan carries a delivery graph, run
   `jstack status` and `jstack ready` (delivery-graph skill) before the
   next step: they compare saved status with git and worktrees and flag
   a task that is already in flight, so a restart does not start the
   same task or delivery twice. Look for sub-agents that died mid-task: a worktree with
   uncommitted changes and no live agent is unfinished work. Inspect it,
   finish or commit it, and run the gates; don't relaunch it from
   scratch and don't delete it.
3. Continue the plan. Don't restart it, and don't ask what to do when
   the log already says.

Each delegated task keeps a `.handoff/` folder in its worktree: the
prompt, a build report and test logs. Keep it out of git (ignore it), so
briefs and operator quotes never enter code history. Archive it before
you remove the worktree.

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
  type) and a one-line pointer in the index. Example:
  `templates/memory-example.md`.
- When the operator corrects you or confirms an unusual approach, save it
  at once. Feedback memories carry **Why** and **How to apply**; a rule
  without its reason gets misapplied. Link related memories.
- A memory holds the **current** rule or state. When it changes, rewrite
  it in place with the current version first, and move the history to
  `LOG.md`. Never append "Update:" lines. A memory longer than one screen
  has become a log.
- Don't put a date that can change in a file name
  (`autonomy-until-<date>`). Name the subject (`autonomy-window`) and keep
  the date in the body.
- When a mandate or routing rule expires, delete its memory or reduce it
  to one superseded line. Delete memories that turn out wrong.
- Don't store what the repo already records: code structure, git
  history, docs.
- At every window start, check the index against the files: every file
  listed once, no listed file missing, no expired entries. The index
  loads every session; keep it under about 100 lines.

### Dreaming: consolidate memory between windows

Memory decays even with good hygiene: duplicates, grown files, expired
windows, stale names. Between windows, or when the index passes about 100
lines, run a consolidation pass, a smart compaction of the memory folder.
Ask the operator first; it rewrites what every future session loads.

- Back up the folder first and change nothing outside it.
- Classify every file as keep, rewrite to current state, merge, expire or
  drop. History goes to the log, never into another memory.
- The newest operator words win a conflict. Old is not expired: a
  standing rule on safety, money, access or language stays until a newer
  decision ends it. When unsure, keep it and ask.
- Fix renamed files and links, rebuild the index, and report every merge,
  expiry and drop with its reason and the backup path.

Template: `templates/DREAM.md`.

### REQUIREMENTS.md, PLAN.md and LOG.md

`REQUIREMENTS.md` says what must be true, `PLAN.md` says how we get there
and where we are, and `LOG.md` records what happened and who decided it.
These are roles, not file names.

**Use the project's existing documents.** If the project already has an
implementation plan, a ticket list, a spec or a decision log, map each
role to that file and write the mapping once, in the current mandate
block and the project instructions ("plan and graph:
`IMPLEMENTATION_PLAN.md`; tickets: `TICKETS.md`; log: `ops/LOG.md`").
Extend the owner file with the columns you need instead of creating a
parallel plan. Two files that both claim to be the plan will drift apart.

Only create the templates when a role has no home. Keep new ones out of
the code history: in an untracked or ignored ops folder, or on a
dedicated branch. At the repo root, every event becomes a commit, every
builder branch carries a stale copy, and worktrees conflict over them.

| | `REQUIREMENTS.md` | `PLAN.md` |
|---|---|---|
| Answers | *What* must be true, and *why* | *How* and *in what order* we get there |
| Owner | The operator. The agent proposes, the operator accepts | The agent. The operator approves it and any material change |
| Contents | Goal, users, numbered requirements (`R1`, `R2`, ...) with acceptance criteria, constraints, non-goals, open questions | A **current mandate** block (window, free, reserved, stop rules, AI routing), phases and tasks that reference requirement IDs, blockers, status, branch/SHA per task, risks, next decision for the operator |
| Changes when | The operator decides something new | Work progresses, or reality disagrees with the plan |

Rules:

- **Read both on every start or resume**, together with the log. The
  plan says where you are, and the requirements say what "done" means.
- **The current mandate block is rewritten in place** whenever the
  mandate or routing changes. The change itself goes to `LOG.md`. Nobody
  should have to grep history to learn what is allowed now.
- **Every task in PLAN.md traces to a requirement ID.** Work that
  doesn't trace is scope creep: propose it, don't do it. Production
  incidents, regressions and gate failures are always in scope; log
  them as such.
- **Requirements change only by an operator decision.** Record it in the
  log, then edit REQUIREMENTS.md with the date and the operator's words.
  Never weaken an acceptance criterion to make a task pass.
- **The plan is a living document.** Update task status, the branch, the
  merge SHA and the evidence (test stamp, deploy SHA) as you go. A
  finished task links to its proof.
- **Estimate in agent-hours, not human time.** Human-time estimates are
  systematically wrong for agent work: a port or rewrite quoted in weeks
  can turn out to be hours. Quote agent-hours per task, and re-check any
  inherited assumption about what a port or rewrite costs before you plan
  around it.
- **Material plan changes need approval:** reordering priorities,
  dropping a task, or adding a reserved action. Small corrections don't;
  log them.
- **"Done" means every acceptance criterion is verified**, each with
  evidence in the plan. Report anything unverified as not done.
- If the operator gives a goal without requirements, draft
  REQUIREMENTS.md from the conversation and ask for one confirmation.
  Don't block other work on it.
- **Settle requirements interactively, then execute autonomously.** If a
  grilling skill is installed, run it before the window starts and turn
  its settled decisions into numbered requirements; open branches become
  open questions, not guesses.

Templates: `templates/REQUIREMENTS.md`, `templates/PLAN.md`, `templates/LOG.md`.

## 2b. Decisions

Every decision the operator makes is recorded right away:

1. **`LOG.md`**: timestamp, the operator's exact words, and what
   changes.
2. **Memory**, when the decision is durable: a rule, a preference, a
   mandate or a boundary.
3. **Repo**, when it changes behaviour: a decision table or changelog
   entry with date and attribution. Never in the project instructions
   file: it holds rules, not history.

Exact words stay in memory and in an uncommitted log, outside the code
history. If the log role maps to a committed file, or the words go into
any other committed file, quote the operator in the repo's language and
mark a translation "(translated)"; a repo with language checks will
otherwise fail on the quote.

If memory and `LOG.md` disagree, the newer operator words in `LOG.md` win.
Fix the memory at once.

A decision record answers who decided, when, what exactly, on what
evidence, and how to roll it back. "We agreed on X" with no source is
not a decision record.

Keep the project's strategy or decision document living: every claim is
labelled **Verified**, **Measured**, **Proposed** or **Open**; dated
decisions quote the operator in the repo's language (marked
"(translated)" when the operator wrote in another language); a change log
lists every study and decision that moved a claim between labels. Update
it after every study and every decision, not at the end of the window.

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
- **Log entries** cite commits, digests, backup paths and run IDs in
  full. Never truncate an identifier someone may need to copy.

## 3. Coordinator and sub-agents

You coordinate. Builders and reviewers do focused work.

- **One worktree and one branch per task.** Builders commit there and
  never push, merge or deploy.
- **Split only what needs splitting.** One task or a short chain runs as a
  sequential loop: build, review, merge, verify, next. When a goal needs
  several dependent or parallel tasks, or tasks that must land together,
  plan and integrate them with the `delivery-graph` skill. When that
  skill's `jstack` CLI is in use, starts, integration and delivery go
  through `jstack transition`; do not hand-edit task status in the plan.
- **Assume other sessions share the machine and the repository.** Do
  multi-step work in your own worktree, not the main checkout. Run
  `git branch --show-current` right before every commit, stage explicit
  paths (never `git add -A`), and never reset, switch or rewrite a branch
  you didn't create.
- **Builders and reviewers never run `git stash`, `git reset`,
  `git checkout -- .` or `git clean`.** The stash is shared across
  worktrees, and the others touch state that someone else may own.
- **The brief is the only context the agent gets.** Include the goal and
  why, what is already ruled out, the files to read, hard constraints,
  exact test commands, resource limits, and the report file to write.
  Template: `templates/BUILDER_BRIEF.md`. Check every path and command
  in the brief before you send it. A wrong path costs the builder an
  hour, or it invents a workaround. Every brief carries stop-and-ask
  rules: if the change would alter a decision path (cost or spend,
  safety, user-visible behaviour, data deletion), the builder stops after the mapping and
  reports instead of applying it. If the brief hands the builder a
  report written by another vendor's model, mark it as an unverified
  lead and require independent verification before use.
- **Follow the recorded AI routing.** Within it, pick the cheapest model
  that can do the task: a strong model plans, orchestrates and reviews
  independently; a small, fast model builds from a precise brief. A vague
  brief is the usual reason a small model fails, so fix the brief before
  you upgrade the model.
- **Record who ran what when usage is measured.** As you start each run
  (builder, reviewer, retry, your own), add its id, role, task and attempt
  to the usage attribution file (`openai-usage`). Attribution written
  afterwards is a guess.
- **Builders commit early.** Ask long-running builders for a WIP commit
  early, and another before any long wait, so the work survives
  interruptions. An agent can die at any moment, and uncommitted work in
  a worktree is the easiest work to lose. Squash or tidy the WIP commits
  later, at review or integration time.
- **Builders clean up after themselves.** They stop their own watchers,
  timers and background processes before they report. A finished agent
  whose monitor keeps firing wastes the coordinator's context.
- **Review with another model or a fresh agent.** Give the reviewer the
  diff, not your conclusion.
- **Verify the work yourself.** Read the report, check that the branch
  tip hasn't moved, merge it locally, and run the full suite once on that
  merge result. Only a green merge result is pushed (when the mandate
  allows it); then remove the worktree. Two branches that each pass can
  fail together, for example through a generated fixture or a checksum
  that both of them touch. Fix that in its own commit on the merged tip,
  and say what you regenerated and why.
- **Clean up worktrees as part of the merge.** Archive `.handoff/`,
  remove the merged worktree and its branch right after the merge, so
  stale worktrees never pile up. Record
  the branch tip and the landing commit in the plan when you merge, and
  delete only when the tip is unchanged and the landing commit is in
  `main`. Never treat a branch with zero own commits as merged: it may be
  a fresh builder worktree that just started. Git's own signals (`--is-ancestor`, `git cherry`, `merge-tree`)
  are heuristics: tested on 13 merge shapes, they miss squash and rebase
  merges that needed conflict resolution; see
  `reference/merged-branch-check.md`. Never force-delete a branch that
  only looks unmerged. Parse only `git worktree list --porcelain`, never
  the human-readable output.
- Don't duplicate delegated work, and don't predict an agent's result
  before it reports.

## 4. Resource discipline

Long autonomy fails on boring things such as RAM, disk and stray
processes.

- Run one heavy job at a time **per machine**, not per agent: full test
  suites, builds, model runs. Take a machine-wide lock for each one (for
  example `flock <shared path>/heavy.lock <command>` on Linux; macOS has
  no `flock`, so use an atomic `mkdir <shared path>/heavy.lock` that the
  holder removes on exit) and put the lock
  command in every brief. Parallel suites crash workstations: memory
  pressure on a shared machine is the usual cause.
- **Branch gates run impacted tests, not the full suite.** Select the
  tests to run from per-test coverage contexts recorded for the
  repository, and run only the tests the change can affect. The full
  suite is for release stamps only, plus a nightly scheduled job (launchd
  or systemd) that also rebuilds the coverage map the selection reads.
- Any watchdog kills only its own process tree, never by process name.
  The operator runs other jobs on the same machine.
- Kill by recorded PID. Broad `pkill -f` patterns can match the tool
  shell itself.
- **Secrets for analysis jobs travel by file, never by chat.** Copy the
  secret to a file with mode `0600` without printing it, test that it
  works, and delete it afterwards. An agent that received secret-use
  approval only second-hand (through you, not from the operator) may
  rightly refuse: get the operator's approval in the operator's own
  words before you pass the secret on.

## 5. Gates before anything leaves the machine

- Run tests locally. Bind the deploy gate to the exact commit SHA (a
  test stamp equal to `HEAD`). A merge commit made only to land an
  already-tested revision may carry that revision's stamp if its tree is
  identical (`git rev-parse <sha>^{tree}`); record both SHAs and run the
  smoke checks on the new one. A different tree means untested. Same
  tree is same tracked files, not same run: rerun checks that depend on
  the SHA, history, time or environment.
- Do a dry run before every apply, and read the dry run. A refusal is
  information, not an obstacle to route around.
- Never take a shortcut past a gate: no hand-edited server state, no
  skipped postflight, no force flags.
- After an apply, verify with the system's own evidence (postflight
  markers, service health, logs), then record the change in the server
  documentation.
- A red test, an unexpected dry-run result or a failed postflight is a
  stop rule: stop that item and report it (section 1).
- **Measure before you remove.** Map everything a component's output
  feeds, then replay recorded history with and without it before you
  delete it. A tool that looks dead can still feed a decision path; only
  a replay that shows zero effect makes the removal safe.
- **Map before you flip a flag.** A flag named for one thing may gate
  another: map every check the flag controls first, and give the other
  check its own flag before you change the shared one.

### Evidence before you change state

- Before any rollback, restart, teardown or cleanup, collect the
  evidence that only the current state can produce: verifier reports,
  live state, logs that rotate on restart. Copy it into the backup
  unchanged. Then change state.
- **Run the terminal verifier before a canary rollback.** A canary's
  evidence is lost the moment it is torn down, so verify first and roll
  back second.
- A rollback is a change. Dry-run it, verify it, and run the next planned
  gate's dry run right away, so drift shows up now and not in the next
  deploy window.
- Know what an apply resets: running experiments, armed states,
  measurement windows, caches. If it resets something the operator is
  waiting on, treat it as a reserved decision, or wait and bundle it with
  the next allowed apply.

### Absence of evidence

- Zero matches is a finding only if you have shown the source would have
  matched. Before you conclude "no X happened", find one known X in the
  same source with the same query.
- Check where the system actually records the event (a database table,
  per-process log files, rotated files) before you check its absence.

### Test the way production runs

Tests run as you, in directories you own, with your permissions and your
versions. Production does not. A fail-closed check, which treats any error
as "blocked", turns that difference into a silent outage. For example, a
guard reads a marker file in a directory only root can enter. The service
user gets "permission denied". The guard reads that as "marker present",
and every action stays blocked while all the tests pass.

- Check that the suite ran before you trust that it passed. Compare the
  passed, skipped and errored counts with the last known good run.
  Thousands of setup errors mean the harness broke, not that the change
  did.
- Match production in identity and privileges: test as the runtime user
  and database role, not as yourself or a superuser. When a check reads
  files, sockets or environment, also test with a directory it cannot
  enter, an unset variable and a read-only path.
- Match production in versions and data shapes. Build every test
  environment from pinned requirements, and know the interpreter version
  production runs. Fakes return exactly what the real interface returns,
  no richer.
- Run any test that spawns processes or uses short timeouts under CPU
  load before you call it stable.
- Keep control files the service must read out of secrets directories.
  Give them their own directory with the narrowest access that still
  lets the service see them.
- After a deploy that changes a guard, prove on the server, as the
  service user, that the guard passes in the normal state. Proving that it
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
- **Deploy-approval pauses are loud by construction.** An autonomy window
  names its scope, end time and stop rules up front; when a deploy waits
  on the operator, the report opens with "**NOT deployed**" as its first
  line and, where a push notification channel exists, sends one. The
  operator must never have to open a log to learn that nothing shipped.
- Report failures with the evidence. Own your mistakes in the log, fix
  them, and turn the lesson into a memory.

## Local models and other agent CLIs

A builder or reviewer does not have to run on the same CLI or the same
vendor as the coordinator. Local models through OpenCode (Ollama, LM
Studio) and third-party agent CLIs (for example Codex, or Muse and
agy/Gemini, whose headless modes, sandboxes and quotas differ and change
over time; check each one's current documentation) are useful inside the routing recorded in the mandate, under
the same rules as any other builder.

**OpenCode with local models** fits bounded tasks: formatting, docs,
simple refactors with tests, log triage, and first-pass reviews. Its
limits set the boundary: typically small context windows and less
reliable tool use on long multi-step work (varies by model), and no access to secrets or production. Give it
narrow briefs with exact files and test commands, and put its output
through the same independent review as any builder's.

**Other agent CLIs in headless mode** need permission handling, not
trust:

- Never pass a skip-all-permissions flag on a machine with production
  access. Run them behind a command allow-list, and give them narrow
  read-only wrapper scripts (a read-only database session, read-only
  file stores, log grep) instead of raw credentials or write access.
- Know each CLI's sandbox limits before you brief it. Some cannot commit
  inside linked worktrees: then the builder leaves its changes
  uncommitted and the coordinator inspects and commits them. Record the
  limit in the plan so the next brief already accounts for it.
- Record each CLI's quota alongside the AI routing, and queue work when
  it runs out instead of rerouting to a model the operator banned.
- Keep every report they produce as an unverified lead until you have
  checked it against the code and the data (section 1).

## Anti-patterns

- Asking permission for things the mandate already covers.
- Ending a turn with "I'll continue" and then doing nothing.
- Hiding a failed gate behind a summary that sounds green.
- Stopping the whole window because one item hit a stop rule.
- Rolling back before collecting the evidence the current state holds.
- Concluding "it didn't happen" from a source that never records it.
- Quoting another model's report as fact without independent verification.
