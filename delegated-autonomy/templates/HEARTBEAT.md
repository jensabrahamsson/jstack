# Heartbeat prompt

Schedule this as the recurring check-in, for example every 30-60 minutes.
Keep the mandate and the plan out of it: they live in `PLAN.md` and
`LOG.md`, so the prompt cannot go stale when the plan changes.

```
Heartbeat. Read the "Current mandate" and "Now" sections of PLAN.md and the
tail of LOG.md; they override anything older, including this prompt.
1. Cheap check: production health, the event you are waiting for, and
   background agents and jobs (finished, stuck, or died with uncommitted work).
2. If something finished or failed: handle it under the current mandate
   block in PLAN.md, log it, and start the next planned step if it is due.
   A stop rule stops that item only. Never start unplanned heavy work.
3. If the mandate has expired: monitor and finish local work only; no merge,
   push or deploy until it is renewed.
4. If nothing changed: reply in one line. Do not repeat the status or the
   open question.
One heavy job per machine, behind the lock.
```
