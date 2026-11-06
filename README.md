# jstack

**Stop supervising your coding agent. Delegate to it.**

jstack is a set of agent skills for running Claude Code (or any compatible
agent) the way you would run a senior team. You give it a goal that spans
days or weeks, a mandate and clear boundaries. It plans the work,
delegates to sub-agents, verifies the results, ships through gates and
keeps a written record. It interrupts you only for the decisions that
are actually yours to make.

> Most developers use AI as an assistant: autocomplete and a chat on the
> side. A growing group runs an agent on one task at a time and watches
> each step. Few delegate. The gap between those last two groups is not
> tooling. It is the mandate, the memory, the written record and the
> discipline around shared resources. jstack writes that down.

---

## What a day looks like

You write one line, from your phone:

> *Work autonomously until Monday 10:00. You can start the new feature again
> on Sunday at 17:00.*

The agent then does the following:

1. Records the mandate, with exact end time, goals, free actions,
   reserved decisions, stop rules and AI routing, in its plan, log and
   memory. If you left out stop rules or which AI providers may build and
   review, it asks once and proposes a default.
2. Spins up builder agents in isolated git worktrees and has a second
   model review each branch.
3. Runs the test suite locally, one heavy job at a time, so the machine
   doesn't run out of memory.
4. Merges and deploys through dry runs and postflight checks, binding
   every step to an exact commit SHA.
5. Asks you one question when it reaches a real decision, with a
   recommendation and the numbers behind it, and keeps working on
   everything else while it waits.
6. Picks up exactly where it left off after a crash or a context reset,
   because nothing important lives only in the conversation.

You course-correct now and then. That's the job.

---

## Skills

| Skill | Use it when |
|---|---|
| [**delegated-autonomy**](delegated-autonomy/SKILL.md) | You grant an autonomy window, resume after a crash or context reset, or want status on long-running delegated work. |

### The core ideas in `delegated-autonomy`

- **Mandate**: an exact window, goals, free actions, reserved
  decisions, stop rules with a safe state, and AI routing (which
  providers build, which review, the fallbacks). A stop rule stops the
  item, not the window. Conditional approvals hold only while every
  condition holds. An approval covers the context it was given in. A false
  premise behind an order means asking, not executing.
- **Durable context** on disk: project instructions, memory (one fact
  per file, with *why*), a timestamped `LOG.md`, and the plan.
  Context is a budget, so verify memories against the live system before
  acting on them.
- **REQUIREMENTS.md, PLAN.md and LOG.md**: what, how and what happened. The operator owns *what* and *why*
  (numbered requirements with verifiable acceptance criteria). The agent
  owns *how*: a living plan where every task traces to a requirement and
  links to its proof (branch, SHA, test stamp, deploy). "Done" means
  every criterion is verified.
- **Decisions**: every operator decision is recorded right away with
  who, when, the exact words, the evidence and the rollback path.
- **Bind everything to a SHA**: briefs, reviews, test stamps, deploys
  and state transitions all name the exact revision. Undo a change from
  the revision that made it.
- **Coordinator and sub-agents**: one worktree per task, briefs as the
  only context, review by another model, and verification by the
  coordinator.
- **Gates**: local tests, a dry run before every apply, postflight
  evidence, and no shortcuts past a refusal.
- **Heartbeats**: a recurring check-in runs one cheap check, follows the
  log rather than its own possibly stale text, and stays to one line when
  nothing changed.
- **Evidence**: collect what only the current state can show before any
  rollback, and prove a source would have recorded X before concluding
  that X never happened.
- **Test the way production runs**: check that the suite really ran, and
  match production's user, privileges, versions and data shapes. A
  fail-closed check that passes for you can block everything for the
  service user.
- **Shared machine**: other sessions share the checkout and the RAM, so
  one heavy job per machine behind a lock, explicit staging, and no stash.
- **Memory that stays current**: rewrite in place, expire what ended, and
  "dream" between windows: a backed-up consolidation pass that merges,
  rewrites and expires memories and rebuilds the index.
- **Communication**: short status, questions answerable in one line, and
  loud reports of what did *not* happen.

Templates are included: [requirements](delegated-autonomy/templates/REQUIREMENTS.md),
a [plan](delegated-autonomy/templates/PLAN.md), a [builder brief](delegated-autonomy/templates/BUILDER_BRIEF.md),
a [log](delegated-autonomy/templates/LOG.md), a
[heartbeat prompt](delegated-autonomy/templates/HEARTBEAT.md), a
[dream prompt](delegated-autonomy/templates/DREAM.md) and a
[memory file](delegated-autonomy/templates/memory-example.md).

---

## Install

Claude Code discovers skills at `~/.claude/skills/<name>/SKILL.md`, so
clone the repo once and link each skill into place:

```bash
git clone https://github.com/jensabrahamsson/jstack.git ~/jstack
mkdir -p ~/.claude/skills
ln -s ~/jstack/delegated-autonomy ~/.claude/skills/delegated-autonomy
```

`git -C ~/jstack pull` updates every linked skill. To use a skill in one
project only, copy it into that repository instead:

```bash
cp -R jstack/delegated-autonomy your-repo/.claude/skills/
```

Then tell your agent:

> *Work autonomously until Friday 18:00. Plan: 1) ... 2) ... 3) ...
> Real money, production mode changes and anything irreversible need my OK.
> Builds on the small model, reviews on a different vendor.*

---

## Works well with

- [**mattpocock/skills**](https://github.com/mattpocock/skills): use
  `grill-me` / `grill-with-docs` to settle the requirements with the agent
  interactively, then hand the result to jstack as `REQUIREMENTS.md` and
  let it run. Pocock for *what*, jstack for *doing it while you sleep*.

---

## Origin

jstack comes from running a real production system with Claude Code on
multi-week goals: thousands of agent commits a month, autonomous windows
over whole weekends, deploys gated by tests and dry runs, and an operator
who mostly makes decisions. Every rule in it exists because something
broke without it.

## License

[MIT](LICENSE) © 2026 Jens Abrahamsson
