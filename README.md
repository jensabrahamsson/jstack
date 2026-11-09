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
| [**delivery-graph**](delivery-graph/SKILL.md) | A delegated goal needs several dependent or parallel tasks, or tasks that must land together. `delegated-autonomy` pulls it in; a single task never needs it. |
| [**openai-usage**](openai-usage/SKILL.md) | You want to know what a delegated goal consumed in OpenAI tokens and what that would cost at OpenAI's API list price, or the mandate sets a cost limit on OpenAI runs. OpenAI models only. |

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
- **REQUIREMENTS.md, PLAN.md and LOG.md**: what, how and what happened.
  These are roles: if your project already has a plan or ticket file,
  jstack maps the role to it instead of adding a second plan. The
  operator owns *what* and *why* (numbered requirements with verifiable
  acceptance criteria). The agent
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
- **Model routing with three roles**: one model plans, a cheaper model
  builds against fixed contracts, a different model reviews, and the
  builder never reviews its own work. Bounded builds and early reviews
  may run on cheaper or other-vendor models; the final review before
  merge or deploy runs on a top-tier model, never one the operator
  banned. Another model's report is an unverified lead until it is
  checked against the code and the data.
- **Local models and other agent CLIs**: OpenCode with local models for
  bounded tasks (formatting, docs, simple refactors with tests, log
  triage, first-pass reviews), third-party CLIs behind command
  allow-lists and read-only wrappers, and the same independent review
  for all of their output.
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
  loud reports of what did *not* happen. A deploy waiting on approval
  opens with "NOT deployed" as its first line.

Templates are included: [requirements](delegated-autonomy/templates/REQUIREMENTS.md),
a [plan](delegated-autonomy/templates/PLAN.md), a [builder brief](delegated-autonomy/templates/BUILDER_BRIEF.md),
a [log](delegated-autonomy/templates/LOG.md), a
[heartbeat prompt](delegated-autonomy/templates/HEARTBEAT.md), a
[dream prompt](delegated-autonomy/templates/DREAM.md) and a
[memory file](delegated-autonomy/templates/memory-example.md).

### The core ideas in `delivery-graph`

- **Proportionate**: one task or a short chain runs as a sequential
  loop. A graph and an integration branch appear only when the work
  needs them.
- **The graph lives in the existing plan**: `Blocked by`, `Scope` and
  `Landed` columns on its task table, pointing at existing tickets instead
  of copying them. An open question blocks only the tasks that list it.
- **Parallel only when safe**: no shared files or generated artifacts,
  tests still one at a time behind the machine lock, and no more branches
  than the coordinator can review.
- **Briefs with a base and a scope**: the base SHA contains every
  blocker, the write scope is bounded, and builders never merge or rebase.
- **One verified candidate**: reviewed task tips merge into an
  integration branch, and only the full suite and a combined review on
  the candidate SHA count. Green branches one by one prove nothing about
  the whole, and a green candidate grants no right to merge or deploy.
  Tasks are `verified` on the candidate and `done` only once landed; the
  landing merge carries the candidate's evidence only if its tree is
  identical, and checks that depend on the SHA, history, time or
  environment run again. `done` follows the mandate's delivery boundary:
  local main, pushed or deployed.
- **Recovery**: conflicts, a moved main, a failing candidate, a stopped
  task and a dead builder each have one rule. A stop on one task never
  stops independent tasks.
- **Impacted tests on branches, the full suite on the candidate**:
  branch gates run the tests a change can affect (selected from
  per-test coverage), the full suite proves the combined candidate and
  stamps releases, and a nightly job reruns it and rebuilds the map.
- **Narrow lanes for behaviour change**: new behaviour ships beside the
  old rule with its own flags, approvals and stop rules, and scattered
  exceptions later refactor into data plus a resolver.

### The core ideas in `openai-usage`

OpenAI models only. A small, tested, standard-library tool plus rules for
the agent; the [skill](openai-usage/SKILL.md) keeps the two apart.

- **Real data sources only**: the usage objects of the Responses, Chat
  Completions and Agents APIs, and Codex CLI session logs. Each has
  different gaps, and the skill lists them field by field. No common
  source is invented.
- **No double counting**: cached input is part of input and reasoning is
  part of output. One count per response id across resumed, forked and
  repeated logs; cumulative counters become differences.
- **Observed, not configured**: only a response's `model` and
  `service_tier` count as observed. Codex logs give the requested model and
  the configured tier, and the report says so.
- **Reproducible prices**: a pinned copy of OpenAI's price list with its
  source URL, retrieval time and the source page's hash; every report names
  the table's hash. Each call gets its tier, long-context, cached-input and
  cache-write rates.
- **Unknown is not zero**: each call is `exact`, `estimate`, `lower_bound`
  or `unknown`. Sums say "at least" when anything is missing, and the
  coverage section names every run, session and category that is missing.
- **Not a bill**: subscription runs get a hypothetical list-price figure,
  API runs an estimate to reconcile with billing records. A hard cost
  limit that covers unmeasured runs is reported as not monitored.
- **Metadata only**: ids, models, tiers, timestamps and counts. Never
  prompts, code or tool output.

See the [example report](openai-usage/reference/example-report.md).

---

## Install

Claude Code discovers skills at `~/.claude/skills/<name>/SKILL.md`, so
clone the repo once and link each skill into place:

```bash
git clone https://github.com/jensabrahamsson/jstack.git ~/jstack
mkdir -p ~/.claude/skills
ln -s ~/jstack/delegated-autonomy ~/.claude/skills/delegated-autonomy
ln -s ~/jstack/delivery-graph ~/.claude/skills/delivery-graph
ln -s ~/jstack/openai-usage ~/.claude/skills/openai-usage
```

`git -C ~/jstack pull` updates every linked skill. To use a skill in one
project only, copy it into that repository instead:

```bash
mkdir -p your-repo/.claude/skills
cp -R ~/jstack/delegated-autonomy ~/jstack/delivery-graph ~/jstack/openai-usage your-repo/.claude/skills/
```

Then tell your agent:

> *Work autonomously until Friday 18:00. Plan: 1) ... 2) ... 3) ...
> Real money, production mode changes and anything irreversible need my OK.
> Builds on the small model, reviews on a different vendor.*

`openai-usage` needs Python 3.9 or later and nothing else. Its tests:
`python3 -m unittest discover -s ~/jstack/openai-usage/tests`.

---

## Works well with

- [**mattpocock/skills**](https://github.com/mattpocock/skills): use
  `grill-me` / `grill-with-docs` to settle the requirements with the agent
  interactively, then hand the result to jstack as `REQUIREMENTS.md` and
  let it run. Pocock for *what*, jstack for *doing it while you sleep*.
  `delivery-graph` adapts the task graph, frontier, vertical slices and
  integration branch from his
  [`to-tickets`](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-tickets/SKILL.md)
  and
  [`implement-spec`](https://github.com/mattpocock/skills/blob/main/skills/engineering/implement-spec/SKILL.md)
  skills (MIT License, Copyright (c) 2026 Matt Pocock). If his tickets
  already exist, `delivery-graph` uses their IDs and edges as they are.

---

## Origin

jstack comes from running a real production system with Claude Code on
multi-week goals: thousands of agent commits a month, autonomous windows
over whole weekends, deploys gated by tests and dry runs, and an operator
who mostly makes decisions. Every rule in it exists because something
broke without it.

## License

[MIT](LICENSE) © 2026 Jens Abrahamsson. Every skill carries
`license: MIT` in its frontmatter. Ideas adapted from
[mattpocock/skills](https://github.com/mattpocock/skills) are credited
above and in the skill that uses them; that repository is also MIT.
