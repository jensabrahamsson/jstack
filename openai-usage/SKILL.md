---
name: openai-usage
description: Measure token usage of OpenAI models across a delegated goal and estimate its cost at OpenAI's API list price, per model, role, task and attempt, with explicit coverage of what is measured, estimated or unknown. Use when the operator asks what a goal cost in OpenAI tokens, when a mandate sets a cost limit on OpenAI runs, or when reporting usage of Codex CLI sessions or OpenAI API calls. OpenAI models only; it does not cover other providers.
license: MIT
---

# OpenAI Usage

After a delegated goal, show what the OpenAI models consumed and what that
would cost at OpenAI's API list price: per actual model, per role, task and
attempt where the attribution is safe, and for the whole goal including
failed attempts, reviews and the orchestrator's own runs. Every number
says whether it was measured, estimated or is unknown.

This skill covers **OpenAI models only**. Runs on other providers appear
in the report only as "not measured".

It has two parts. Keep them apart when you report:

- **Implemented and tested**: `openai_usage.py`, a Python 3.9+ standard-library
  tool, the pinned price table in `prices/`, and the tests in `tests/`.
- **Instructions to the agent**: everything under "What you do" below.
  Nothing enforces them; they are rules you follow.

## What can be observed where

Checked on 2026-11-06 against the OpenAI documentation and Codex CLI
0.165.0 session logs. Field names are exact.

| Source | Per-call usage fields | Model | Service tier | Gaps |
|---|---|---|---|---|
| Responses API response | `usage.input_tokens`, `usage.input_tokens_details.cached_tokens`, `.cache_write_tokens`, `.cache_write_tokens_details.ttl_30m_tokens` / `ttl_12h_tokens`, `usage.output_tokens`, `usage.output_tokens_details.reasoning_tokens` | `model` of the response | `service_tier` of the response (the tier actually used) | `usage` can be null |
| Chat Completions response | `usage.prompt_tokens`, `usage.prompt_tokens_details.cached_tokens`, `.cache_write_tokens`, `usage.completion_tokens`, `usage.completion_tokens_details.reasoning_tokens` | `model` | `service_tier` | 12-hour cache writes don't exist here |
| Agents API session turns | turn `usage` with the Responses fields above, and `subagent_id` (null for the root agent) | as recorded | as recorded | No cache-write count; "best-effort", "can be `null` when unknown, and recorded counts may change" |
| Codex CLI session log `$CODEX_HOME/sessions/**/rollout-*-<thread id>.jsonl` | `token_usage_record` events: `payload.usage.{input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens}` per `response_id`; cumulative `turn_token_usage` and `thread_token_usage` | `turn_context.payload.model`: the model Codex **requested**, not confirmed by a response | `thread_settings_applied.service_tier`: **configured** | `cache_write_input_tokens` was 0 in every one of 8,741 local records although 98% of input was cache reads, so a 0 is not evidence. Older logs have only `token_count` events. Runs with `--ephemeral` write no log |
| `codex exec --json` stdout | `turn.completed.usage` per turn, no model | - | - | Per turn, not per request; not read by the tool |
| Codex cloud tasks, ChatGPT | none found locally | - | - | Not observable with this tool |

How the counts nest (OpenAI Agents API observability guide: "Cached tokens
are included in `input_tokens`, and reasoning tokens are included in
`output_tokens`." and "Reasoning tokens are billed as output tokens."):

```
input  = ordinary input + cached reads + cache writes   (each billed at its own rate)
output = visible output + reasoning                     (one output rate)
```

The local Codex logs agree: `total_tokens == input_tokens + output_tokens` in
all 8,741 records, with cached ≤ input and reasoning ≤ output. The tool never
adds cached to input or reasoning to output.

Billing evidence: a Codex log whose `token_count` events carry
`rate_limits.plan_type` comes from a ChatGPT plan. Those runs are not billed
per token. OpenAI's Codex pricing page says: "API token prices are separate
from subscription usage; don't use them to estimate included tasks." For
them the USD figure is a hypothetical, labelled so. Direct API calls are
billed per token, but the tool's figure is still an estimate; only the
organization's billing records show the charge.

Sources: https://developers.openai.com/api/docs/guides/agents-api/observability,
https://developers.openai.com/api/docs/guides/prompt-caching,
https://developers.openai.com/api/docs/pricing,
https://developers.openai.com/codex/pricing,
https://developers.openai.com/codex/noninteractive (all read 2026-11-06).

## What the tool computes

`<skill>` is this skill's folder, for example `~/.claude/skills/openai-usage`:

```bash
python3 <skill>/openai_usage.py \
  --attribution ops/usage-attribution.json \
  --ledger ops/openai-calls.jsonl \
  [--codex-session FILE ...] [--codex-home ~/.codex] \
  [--format markdown|json|records]
```

- **Codex runs** listed in the attribution file are found by thread id
  under `--codex-home` (default `$CODEX_HOME`, else `~/.codex`), together
  with every subagent thread below them (`parent_thread_id`).
- **Deduplication**: one count per `response_id` (Codex) or `call_id`
  (ledger), across all inputs, so a resumed or forked log, a file given
  twice or a call logged twice counts once. Cumulative counters are never
  summed: Codex per-response records are used; older `token_count` logs and
  ledger snapshots marked `cumulative` count the difference from the
  previous snapshot, skip repeats, and flag a counter that goes down.
- **Pricing** per call from the pinned table: the tier's rates, the
  long-context rates when that call's input exceeds 272,000 tokens, the
  cached-input rate, the 30-minute and 12-hour cache-write rates for models
  that bill writes separately (GPT-5.6 and later), and one output rate that
  covers reasoning. All money is `Decimal`.
- **Status per call**, and the worst one for every sum:

| Status | Meaning | Sum shown as |
|---|---|---|
| `exact` | Model and tier from the response, every needed count and rate present | `$X` |
| `estimate` | Priced fully, but the model or tier is requested, configured or assumed, or a snapshot name was priced as its alias, or the promotional price had ended | `~$X` |
| `lower_bound` | A count or split is missing; it is priced at the cheapest rate it could have had (missing cached split at the cached rate, unreported cache writes at the ordinary input rate, unknown write lifetime at the 30-minute rate, unknown request length at the short-context rate, a missing count or listed rate at 0) | `at least $X` |
| `unknown` | No usage, model not in the table, tier not observed, inconsistent counts, or audio and image tokens | `unknown`; never added as 0 |

- **Attribution** comes only from the attribution file. Calls from threads
  it doesn't list are `unattributed`. A subagent thread is attributed to the
  run that spawned it and counted as such. `attempt` above 1 is a retry,
  summed separately as well.
- **Coverage** lists listed runs with no usage ("unknown, not zero"), runs
  marked not measured, session files without usage, input files that are
  missing or unreadable (by file name), duplicates dropped,
  every assumption and gap with its call count, and the charges no amount
  includes: per-call tool fees, container sessions, the 10% regional or
  FedRAMP uplift, and audio or image tokens.
- **Output**: a Markdown summary, the same as JSON, or `records`: one
  metadata-only line per call that the tool reads back as a ledger
  (`"api": "normalized"`), so a goal can be priced again after the session
  logs are gone or with a newer price table.

The tool reads only ids, model names, tiers, timestamps and token counts. It
never prints or stores prompts, messages, paths, code or tool output; a test
plants secrets in message, instruction and path fields and checks that none
reaches any output. It makes no network calls and needs no API key. It exits 0 when
usage or an input file is missing: measurement never blocks the work.

[Example report](reference/example-report.md), from the synthetic fixtures
in `tests/fixtures/example/`: an orchestrator, a failed builder attempt
with one long-context request, its retry with a subagent, a reviewer on
the API with one call whose usage is null and one model the table doesn't
list, a reviewer whose Codex session had no usage, a builder whose session
file is missing, and planning that was never measured.

## What you do

1. **Before the first delegation**, create the attribution file in the ops
   folder (untracked, next to the log). One entry per run, written when
   the run starts:

   ```json
   {
    "goal": "csv-export",
    "runs": [
     {"id": "<codex thread id>", "source": "codex", "role": "builder", "task": "T1", "attempt": 1, "outcome": "failed"},
     {"id": "<codex thread id>", "source": "codex", "role": "builder", "task": "T1", "attempt": 2},
     {"id": "review-t1", "source": "ledger", "role": "reviewer", "task": "T1", "attempt": 1, "billing": "api"},
     {"id": "planning", "source": "none", "role": "orchestrator", "task": "plan", "note": "not run on an OpenAI model"}
    ]
   }
   ```

   The Codex thread id is the `thread_id` of the `thread.started` event
   (`codex exec --json`) or the UUID at the end of the session file name.
   Every retry gets its own entry with the next attempt number. List the
   orchestrator's own OpenAI runs too. Work that is not an OpenAI call,
   or that you can't measure, gets `"source": "none"` and a note; it then
   shows as not measured instead of silently missing.
2. **When your own code calls the OpenAI API**, append one line per
   response to the ledger. Copy `id`, `model`, `service_tier` and the
   `usage` object from the response, nothing else:

   ```json
   {"run": "review-t1", "call_id": "<response id>", "api": "responses", "model": "<response.model>", "service_tier": "<response.service_tier>", "timestamp": "<UTC>", "usage": {"...": "as returned"}}
   ```

   `api` is `responses`, `chat` or `agents_turn` (use the turn id as
   `call_id`). If you only know the model you asked for, write
   `requested_model` instead of `model`. Batch API calls add
   `"batch": true`. Session-level totals go in as `"cumulative": true`
   with a `stream` and `seq`, never as separate calls. Never copy input,
   instructions, output text, tool arguments or headers.
3. **Don't treat a model name in a brief, a config or a routing rule as the
   model that ran.** Only a response's `model` counts as observed; Codex
   logs give the requested model, and the report says so.
4. **Report after the goal** (and at checkpoints if the operator asks):
   run the tool, put the total, the status counts and the coverage gaps in
   the log, and keep the `--format records` output in the ops folder so
   the numbers can be reproduced. Say in words whether the amount is a
   bill or a hypothetical, and name every run that is unknown.
5. **Cost limits.** The tool measures after the calls happened; it can't
   stop a call, and it sees nothing for runs that leave no usage. If the
   operator sets a hard USD limit on OpenAI usage:
   - Say before the first delegation which runs it can measure and which
     it can't, and that a ChatGPT plan's usage is limited by the plan, not
     by USD, so a list-price figure is not what that limit protects.
   - If any run that counts against the limit is unmeasured, or the total
     is `unknown`, the limit is **not monitored**. Say so plainly, propose
     a limit you can enforce (number of runs or attempts, a cheaper
     model, API-only runs with a ledger), and treat the answer as a
     reserved decision. Don't start runs that the limit would cover while
     you wait.
   - When it is monitored, compare the `at least` total with the limit at
     every task boundary, and stop starting new runs before the next run
     could cross it.
   A soft budget or no limit never blocks work: report and continue.
6. **Updating prices.** Never edit a pinned table. Fetch
   `https://developers.openai.com/api/docs/pricing.md`, write a new
   `prices/openai-api-<date>.json` with the same structure, the retrieval
   time and the source's sha256, and add spot-check tests for it. The tool
   uses the newest table by default; pass `--prices` to reproduce an old
   report with the table it used (its sha256 is in every report).

## Limits

- No cache-write counts from Codex or the Agents API. For models that bill
  writes separately, those totals are lower bounds.
- Codex logs carry the requested model and the configured tier, so Codex
  totals are at best estimates.
- Not priced: tool-call fees, container sessions, regional or FedRAMP
  uplift, audio, image and realtime tokens, fine-tuned models, and models
  not on the pinned table. Each appears as a gap, not as 0.
- Usage reported by the Agents API can change after it is first read;
  re-run the report before quoting a final number.
- Codex cloud tasks, ChatGPT and other OpenAI surfaces without local or
  API usage data can't be measured with this tool.

## Tests

```bash
python3 -m unittest discover -s <skill>/tests
```

Synthetic data only. The tests cover cached and reasoning tokens nested in
input and output, the prompt-caching guide's own cost example, cache
writes with and without a lifetime split, Chat Completions and Agents API
shapes, per-response Codex records, resumed and repeated logs,
`token_count` deltas and resumed `token_count` files, cumulative ledger
streams and counter resets, missing usage and missing input files, splits and tiers, unknown models and snapshot names,
long-context rates, promotional end dates, requested versus observed
models, retries, subagents and unattributed calls, billing labels,
privacy, determinism, re-pricing from `records` output with subagent
attribution intact, and the published example report.
