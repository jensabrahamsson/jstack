# Plan: <project or goal>

<!-- Use this template only if the project has no plan file yet. If it has
one (IMPLEMENTATION_PLAN.md, TICKETS.md, ...), extend that file instead and
record the mapping in the current mandate block. -->

Approved: <YYYY-MM-DD HH:MM TZ> ("<operator's words>").

## Current mandate (rewritten in place; changes go to LOG.md)
- Window: until <YYYY-MM-DD HH:MM TZ>
- Free: <...>
- Delivery boundary ("done" means): <merged locally | pushed | deployed>
- Reserved: <...>
- Stop rules and safe state: <...>
- Conditional approvals: <"operator's words"> (conditions: <...>)
- Documents: plan and graph <file>, tickets <file>, requirements <file>, log <file>
- AI routing: build <...>, review <...>, fallback <...>, never <...>; expires <...>
- Cost limit: <none | soft | hard> <amount> on <which runs>; measured by <openai-usage, attribution file path>; not measurable: <runs>, so <monitored | not monitored>

Requirements: [REQUIREMENTS.md](REQUIREMENTS.md)

## Now
- In progress: <task id> (<who: coordinator / builder in worktree X>)
- Next decision for the operator: <question + recommendation>, or none

## Phases

### Phase 1: <name>

| Task | Traces to | Blocked by | Scope | Status | Branch / SHA | Landed | Evidence |
|---|---|---|---|---|---|---|---|
| T1 <task> | R1 | - | `<paths>` | done | `feat/x` | `<tip sha>` -> `<landing sha>` | test stamp `<sha>`; deploy `<sha>` |
| T4 <task> | R2 | - | `<paths>` | verified | `feat/z` @ `<sha>` | - | suite + review on candidate `<sha>`; waiting to land |
| T2 <task> | R2 | - | `<paths>` | in progress | `feat/y` from `<base sha>` @ `<sha>` | - | builder report `.handoff/...` |
| T3 <task> | R1, R3 | T2, Q1 | `<paths>` | blocked | - | - | - |

`Blocked by` lists real edges only: tasks whose output this task needs,
and open questions (Q-ids) whose answer changes it. `Scope` is the write
scope given to the builder. A single task or a short chain can leave both
as `-`.

Estimate in agent-hours, not human time: a port or rewrite quoted in weeks
can turn out to be hours. Re-check inherited cost assumptions before
planning around them.

### Integration (only when tasks must land together)
- Branch: `int/<goal>` cut from main `<full sha>`; tip `<full sha>`
- Merged: T1 `<task tip sha>`, T2 `<task tip sha>`; main merged at `<sha>`
- Candidate `<full sha>`: full suite `<stamp>`, combined review of `main...<candidate>` `<report>`
- Landing on main: <free | reserved, asked <time>>

### Phase 2: <name>
...

## Risks
- <risk> -> <mitigation / stop rule>

## Plan changes
- <YYYY-MM-DD HH:MM> <change> (approved: "<operator's words>" | minor, logged)
