# Plan: <project or goal>

Approved: <YYYY-MM-DD HH:MM TZ> ("<operator's words>").

## Current mandate (rewritten in place; changes go to LOG.md)
- Window: until <YYYY-MM-DD HH:MM TZ>
- Free: <...>
- Reserved: <...>
- Stop rules and safe state: <...>
- Conditional approvals: <"operator's words"> (conditions: <...>)
- AI routing: build <...>, review <...>, fallback <...>, never <...>; expires <...>

Requirements: [REQUIREMENTS.md](REQUIREMENTS.md)

## Now
- In progress: <task id> (<who: coordinator / builder in worktree X>)
- Next decision for the operator: <question + recommendation>, or none

## Phases

### Phase 1: <name>

| Task | Traces to | Blocked by | Scope | Status | Branch / SHA | Evidence |
|---|---|---|---|---|---|---|
| T1 <task> | R1 | - | `<paths>` | done | `feat/x` -> merged `<full sha>` | test stamp `<sha>`; deploy `<sha>` |
| T2 <task> | R2 | - | `<paths>` | in progress | `feat/y` from `<base sha>` @ `<sha>` | builder report `.handoff/...` |
| T3 <task> | R1, R3 | T2, Q1 | `<paths>` | blocked | - | - |

`Blocked by` lists real edges only: tasks whose output this task needs,
and open questions (Q-ids) whose answer changes it. `Scope` is the write
scope given to the builder. A single task or a short chain can leave both
as `-`.

### Integration (only when tasks must land together)
- Branch: `int/<goal>` cut from main `<full sha>`; tip `<full sha>`
- Merged: T1 `<task tip sha>`, T2 `<task tip sha>`; main merged at `<sha>`
- Candidate `<full sha>`: full suite `<stamp>`, combined review of `<base>...<candidate>` `<report>`
- Landing on main: <free | reserved, asked <time>>

### Phase 2: <name>
...

## Risks
- <risk> -> <mitigation / stop rule>

## Plan changes
- <YYYY-MM-DD HH:MM> <change> (approved: "<operator's words>" | minor, logged)
