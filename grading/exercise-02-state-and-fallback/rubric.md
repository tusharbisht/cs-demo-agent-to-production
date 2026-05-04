# Rubric — exercise/02-state-and-fallback

> **Manager persona:** Engineering Manager — AI Platform. After exercise 01 they got their traces. Now they want survivability. Has lived through (a) a worker restart that vanished 47 active conversations and produced an angry customer-success thread, (b) an Anthropic regional outage that took the agent down for 2 hours because no fallback was wired. Score with that voice — tactical, references real incidents, asks for trace evidence on every fallback claim.

## What this rubric is checking

The agent's reply quality is held constant from exercise 01. What's new is *whether the agent survives*: a worker restart, a primary-LLM outage, a slow downstream tool, an unbounded conversation. The grader injects each failure mode via test headers; the agent must handle each gracefully, with the trace as evidence.

## Cardinal sins (any one → flag for review + axis 0)

1. **Conversation state lost across worker restart** — a customer mid-flow gets dropped
2. **A 429 from the primary LLM that propagates as a 5xx to the user** — the user sees the outage
3. **An unbounded conversation that 4xx's at turn 25** — the system can't handle long sessions
4. **A "fallback" that's actually a retry on the same model** — no actual fallback chain wired
5. **All-tiers-fail returning 500 instead of graceful 503** — the system panics rather than degrading

## Scoring axes

| Axis | Weight | Tests |
|---|---|---|
| Durable state across restart | 14% | durable-state-across-restart |
| Bounded history (no overflow) | 8% | bounded-history-25-turns |
| Primary→fallback chain works | 16% | primary-429-falls-through |
| Primary timeout fallback | 11% | primary-timeout-falls-through |
| Graceful 503 on all-tiers-fail | 11% | all-tiers-fail-graceful-503 |
| Tool timeout handling | 8% | tool-timeout-graceful |
| Streaming | 5% | streaming |
| Trace continuity on fallback | 8% | fallback-still-traced |
| State endpoint coherent | 5% | state-endpoint-coherent |
| Cost bounded on fallback | 5% | cost-bounded-on-fallback |
| No regressions on exercise 01 | 5% | no-regression-on-01 |
| Eval set quality | 4% | eval-set-quality |

## Per-axis bands

### Durable state across restart

| Outcome | Score |
|---|---|
| Post-restart turn 3 references context from turns 1+2; `/state/{id}` shows full history | **10** |
| Post-restart turn 3 has new context but state endpoint shows partial recovery | 5 |
| State endpoint returns 404 OR turn 3 has no prior context | **0** + cardinal sin |

### Primary→fallback chain

The grader injects `X-Test-Force-Primary-429: 1`. The fallback MUST fire. Specifically:
- Status 200 (not 5xx)
- `fallback_chain_taken: true`
- `model_used` is the secondary model name
- Trace shows both `attempt_primary` (with error) AND `attempt_secondary` (with success)

| Outcome | Score |
|---|---|
| All four conditions met | **10** |
| `fallback_chain_taken: true` but trace doesn't show attempt_secondary span | 6 |
| Status 200 but `fallback_chain_taken: false` (means same model handled it — fake fallback) | 2 |
| Status 5xx (cardinal sin: 429 propagated) | **0** + cardinal sin |

### Graceful 503

| Outcome | Score |
|---|---|
| Status 503 with degraded:true and a polite reply | **10** |
| Status 503 but missing degraded flag | 6 |
| Status 200 with template reply (acceptable but the explicit-degraded signal is missing) | 4 |
| Status 500 (panic) | **0** + cardinal sin |

### Bounded history

The summary axis is the easiest to fake (truncate to last N turns). The probe is designed to catch this: turn 25 needs information from turn 3. Truncate-only fails; summarise-properly passes.

| Outcome | Score |
|---|---|
| Turn 25 recalls turn-3 context AND `summarise` span exists by turn 11 | **10** |
| `summarise` span exists but turn 25 misses the recall (summary content is poor) | 6 |
| Truncation only (no summary span); turn 25 fails recall | 2 |
| Context-window 4xx anywhere in 25 turns | **0** + cardinal sin |

### Cost bounded on fallback

A primary-429 fallback shouldn't triple your cost. The primary attempt was force-failed (zero useful tokens); the secondary did the work. Total cost ≈ secondary's cost.

| Outcome | Score |
|---|---|
| Cost_usd ≤ $0.06 on the fallback path (vs ~$0.04 normal) | **10** |
| ≤ $0.10 | 6 |
| > $0.15 (fallback path is wasting money — likely retrying primary too many times) | 2 |

## Strictness notes

- **The trace is your evidence on every fallback claim.** A `fallback_chain_taken: true` flag with no `attempt_secondary` span in the trace means the flag is a lie.
- **Real outages are cross-provider.** A primary→secondary fallback that stays inside one provider helps with rate limits but not regional outages. The rubric gives full credit for either, but cross-provider is the production-grade pattern (note this in the manager's critique when scoring).
- **Streaming has subtle failure modes.** Some agents claim to stream but actually buffer the entire reply and send it as one big SSE chunk. The grader counts chunks; ≥2 is required.
- **The 503 vs 500 distinction matters more than it sounds.** Real load balancers (HAProxy / Envoy / nginx) treat 503 differently from 500 — they back off retries on 503, they consider the host "drained but coming back." Returning 503 on degraded mode is the *production-grade* signal that the agent is gracefully unhappy. 500 is the panic signal.

## Pass threshold

70%. Any cardinal sin → unshippable.
