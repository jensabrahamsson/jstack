---
name: run-heavy-jobs-in-sequence
description: Never run two heavy jobs (test suites, builds) at once; the workstation crashed from RAM exhaustion
metadata:
  type: feedback
---

Operator <date>: "run everything in sequence, the crash was memory".
Four parallel test processes reached 22-33 GB each.

**Why:** two crashes in one day, lost work and a lost deploy log.

**How to apply:** one heavy job at a time, including those started by
sub-agents. Say so in every builder brief. The memory watchdog kills
only the suite's own process tree. Related: [[memory-guard-own-tree]].
