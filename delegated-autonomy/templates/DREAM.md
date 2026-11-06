# Dream: consolidate memory

Run between autonomy windows, when the index passes about 100 lines, or
when the operator asks. It is a smart compaction of the memory folder,
not of the conversation. Ask for an OK first: it rewrites what every
future session loads.

```
Dream. Consolidate the memory folder <path>.
0. Back up the folder (copy to <path>.bak-<timestamp>). Change nothing
   outside it. Never read or copy secrets into memory.
1. Inventory: list every file with size, type and description; find files
   missing from the index and index lines with no file.
2. Classify each file:
   - KEEP: current and correct.
   - REWRITE: still valid but grown into a log, or with "Update:" lines.
     Rewrite to the current rule or state first, with Why / How to apply.
     Move the history to LOG.md (or an archive file), not into memory.
   - MERGE: several files about one subject. Keep one file named after the
     subject; carry over every still-valid rule and its Why.
   - EXPIRE: a window, routing rule, deadline or plan that has ended. Delete
     it, or reduce it to one line if a later rule refers to it.
   - DROP: wrong, or recorded in the repo anyway (code, docs, git history).
3. When rules conflict, the newest operator words win. Check LOG.md or the
   repo before you drop anything you are unsure of; if still unsure, KEEP
   and list it as a question.
4. Rename files whose name carries a date or state that changed; fix every
   [[link]] to a renamed or merged file.
5. Rebuild the index: one line per file, grouped by type, current rules
   first, under about 100 lines.
6. Report: counts before and after, every MERGE, EXPIRE and DROP with a
   one-line reason, open questions, and the backup path.
```

Rules: never drop a standing operator rule (safety, money, access,
language, never-do items) because it is old. Old is not expired; only an
end date or a newer decision expires a rule.
