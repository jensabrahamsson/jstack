# Heartbeat prompt

Schedule this as the recurring check-in, for example every 30-60 minutes.
Keep the mandate and the plan out of it: they live in the plan and the
log (`PLAN.md`, `LOG.md`, or the files the project maps those roles to),
so the prompt cannot go stale when the plan changes. Session-scoped
schedules expire (typically after about 7 days): heartbeats and critical
checks belong in the OS scheduler or server-side timers, and server-side
stop rules must not depend on the laptop or this session.

```
Heartbeat. Read the current mandate block and the "Now" section of the plan
(<plan file>) and the tail of the log (<log file>); they override anything
older, including this prompt. If this prompt is stale, say so once.
1. Cheap check: production health, the event you are waiting for, and
   background agents and jobs (finished, stuck, or died with uncommitted work).
2. If something finished or failed: handle it under the current mandate
   block, log it, and start the next planned step if it is due.
   A stop rule stops that item only. Never start unplanned heavy work.
3. If the mandate has expired: monitor and finish local work only; no merge,
   push or deploy until it is renewed.
4. If nothing changed: reply in one line. Do not repeat the status or the
   open question.
One heavy job per machine, behind the lock.
```
