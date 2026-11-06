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

| Task | Traces to | Status | Branch / SHA | Evidence |
|---|---|---|---|---|
| T1 <task> | R1 | done | `feat/x` -> merged `<full sha>` | test stamp `<sha>`; deploy `<sha>` |
| T2 <task> | R2 | in progress | `feat/y` @ `<sha>` | builder report `.handoff/...` |
| T3 <task> | R1, R3 | blocked | - | waiting for Q1 |

### Phase 2: <name>
...

## Risks
- <risk> -> <mitigation / stop rule>

## Plan changes
- <YYYY-MM-DD HH:MM> <change> (approved: "<operator's words>" | minor, logged)
