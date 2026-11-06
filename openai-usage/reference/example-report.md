# OpenAI usage: csv-export (synthetic example)

OpenAI models only. **List-price calculation, not a bill.** Prices: https://developers.openai.com/api/docs/pricing, retrieved 2026-11-06T14:10:06Z (table `openai-api-2026-11-06.json`, sha256 `8b919bf1fc5330afae4876092f81d02f424ccfe6adb6f4bc2a6197aada0d32eb`).

**Total at API list price: at least $1.3635** over 12 calls (2 exact, 8 lower_bound, 2 unknown).
Of which retries (attempt > 1): at least $0.1541 over 3 calls.

## Billing

- 8 calls: subscription (Codex rate_limits.plan_type=plus)
- 4 calls: api (declared in attribution)
- Subscription calls are not billed per token. Their USD figure is a hypothetical: what the same tokens would cost at API list price. OpenAI's Codex pricing page: "API token prices are separate from subscription usage; don't use them to estimate included tasks."
- API calls are billed per token; this figure is an estimate. Reconcile with the organization's billing records.

## By model

| Model | Calls | Input | Cached input | Cache writes | Output | Reasoning (in output) | List price | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gpt-6.1-sol` | 3 | 153,000 | 89,600 | unknown | 2,800 | 1,100 | at least $0.1638 | lower_bound |
| `gpt-6.1-terra` | 4 | 620,000 | 339,600 | unknown | 20,000 | 7,500 | at least $0.4799 | lower_bound |
| `gpt-6-luna` | 1 | 30,000 | 0 | unknown | 2,500 | 2,000 | at least $0.0042 | lower_bound |
| `gpt-5.5` | 3 | >= 164,000 (1 call unknown) | >= 79,872 (1 call unknown) | unknown | >= 8,500 (1 call unknown) | >= 5,200 (1 call unknown) | at least $0.7156 | unknown |
| `gpt-9-preview` | 1 | 5,000 | 0 | unknown | 400 | 0 | unknown | unknown |
| **Total** | 12 | >= 972,000 (1 call unknown) | >= 509,072 (1 call unknown) | unknown | >= 34,200 (1 call unknown) | >= 15,800 (1 call unknown) | at least $1.3635 | unknown |

## By role, task and attempt

| Role / task / attempt | Calls | Input | Cached input | Cache writes | Output | Reasoning (in output) | List price | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| orchestrator / all / 1 (gpt-6.1-sol) | 3 | 153,000 | 89,600 | unknown | 2,800 | 1,100 | at least $0.1638 | lower_bound |
| builder / T1 / 1 (failed) (gpt-6.1-terra) | 2 | 420,000 | 250,000 | unknown | 13,000 | 5,000 | at least $0.3300 | lower_bound |
| builder / T1 / 2 (retry) (gpt-6-luna, gpt-6.1-terra) | 3 | 230,000 | 89,600 | unknown | 9,500 | 4,500 | at least $0.1541 | lower_bound |
| reviewer / T1 / 1 (gpt-5.5, gpt-9-preview) | 4 | >= 169,000 (1 call unknown) | >= 79,872 (1 call unknown) | unknown | >= 8,900 (1 call unknown) | >= 5,200 (1 call unknown) | at least $0.7156 | unknown |

Input includes cached input and cache writes; output includes reasoning. Nothing is counted twice.

## Coverage

- Measured: 12 calls from 5 Codex session files and the ledgers given; 2 duplicate records ignored.
- Runs listed: 7; with usage: 4.
- **Unknown, not zero**: reviewer / T2 run `00000000-0000-4000-8000-00000000000e`: no usage records.
- **Unknown, not zero**: builder / T2 run `00000000-0000-4000-8000-00000000000f`: session file not found.
- **Not measured**: orchestrator / planning: ran before usage logging started.
- 1 call from subagent threads, attributed to the run that spawned them.

Estimates, lower bounds and gaps:

- 8 calls: model is the requested model, not confirmed by a response
- 8 calls: service tier standard is configured, not confirmed by a response
- 8 calls: cache writes not reported; uncached input priced at the ordinary input rate (writes cost 1.25x or 2.5x)
- 1 call: long-context rates (input > 272000 tokens)
- 1 call: usage missing (unknown, not zero)
- 1 call: model gpt-9-preview not in price table

Not included in any amount:

- Per-call tool fees (web search, file search) and hosted container sessions.
- The 10% regional-processing or FedRAMP uplift: the endpoint is not visible in usage.
- Audio, image and realtime tokens: the pinned table holds text-token rates only.
