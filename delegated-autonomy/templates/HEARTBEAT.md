# Heartbeat prompt

Schedule this as the recurring check-in, for example every 30-60 minutes.
Keep the mandate and the plan out of it: they live in `LOG.md` and
`PLAN.md`, so the prompt cannot go stale when the plan changes.

```
Heartbeat. Read the tail of LOG.md and the "Now" section of PLAN.md; they
override anything older, including this prompt.
1. Cheap check: production health, the event you are waiting for, and
   background agents and jobs (finished, stuck, or died with uncommitted work).
2. If something finished or failed: handle it under the current mandate,
   log it, and continue the plan.
3. If the mandate has expired: monitor only; no new reserved-adjacent steps.
4. If nothing changed: reply in one line. Do not repeat the status or the
   open question.
One heavy job at a time.
```
