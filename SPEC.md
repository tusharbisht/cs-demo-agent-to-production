# SPEC — exercise/02-state-and-fallback

Builds on exercise 01 (observability remains active). Activates `model_used`, `fallback_chain_taken` fields. Adds streaming and admin restart-test affordance.

## `POST /chat` — additions for this exercise

Response now includes:

```json
{
  ...all 01 fields...,
  "model_used": "claude-sonnet-4-5",
  "fallback_chain_taken": false,
  "fallback_reason": null,
  "summary_compression_applied": false
}
```

| Field | Type | Notes |
|---|---|---|
| `model_used` | string | Actual model that produced this reply (may differ from `model` in `/health` if fallback fired) |
| `fallback_chain_taken` | bool | True if any fallback in the chain triggered for this reply |
| `fallback_reason` | string \| null | If true: `"primary_429"` / `"primary_timeout"` / `"secondary_failure"` / etc. |
| `summary_compression_applied` | bool | True if the conversation history was rolled into a summary on this turn |

When all fallback tiers are exhausted, return **HTTP 503** with body:

```json
{
  "conversation_id": "...",
  "reply": "I'm not able to help with that right now — a human will follow up shortly.",
  "model_used": "kb-template",
  "fallback_chain_taken": true,
  "fallback_reason": "all_tiers_failed",
  "degraded": true,
  "trace_id": "tr_..."
}
```

The `503` is intentional — it signals to the LMS judge (and to a real upstream load balancer) that this instance is degraded but the request was handled gracefully (not a 500 panic).

## Streaming mode

When `POST /chat` is called with `Accept: text/event-stream` OR body field `stream: true`:

- Content-Type: `text/event-stream`
- The grader expects ≥2 SSE `data:` chunks
- Final chunk includes the full envelope (trace_id, totals, model_used, fallback_chain_taken)
- Partial chunks contain `{"delta": "<token text>"}`

Streaming is graded but not gated — non-streaming is the default and is fully scored.

## State semantics

The `conversation_id` is the durable state key. State must:
- Persist across worker restart (Postgres-backed)
- Be readable from a fresh worker instance (multi-replica coherence)
- Bound the included message history at a configurable window (default 10 turns); older turns roll into a `summary` field
- Be queryable: `GET /state/{conversation_id}` returns the current state snapshot (used by the grader to verify durability without firing a fresh chat)

`GET /state/{conversation_id}`:
```json
{
  "conversation_id": "conv_abc",
  "messages": [{"role": "user", "content": "..."}, ...],
  "summary": "User is on Pro+, asked about refund window for a 21-day-old purchase; agent flagged for human review.",
  "turn_count": 7,
  "last_updated_at": "2026-05-04T14:30:00Z",
  "checkpoint_id": "ck_..."
}
```

## Test affordances (X-Test-* headers)

The grader uses these headers to inject failure conditions. Your service must honour them when present:

| Header | Effect |
|---|---|
| `X-Test-Force-Primary-429: 1` | Make the primary model call return a synthetic 429 (without actually calling Anthropic). Forces fallback to secondary. |
| `X-Test-Force-Primary-Timeout: 1` | Make the primary call hang past the timeout. Forces fallback to secondary. |
| `X-Test-Force-All-Fail: 1` | Force every tier to fail. Should produce the 503 degraded-mode response. |
| `X-Test-Slow-Kb-Ms: 6000` | Add 6s delay to KB retrieval. Should trigger your tool timeout and graceful fallthrough. |

These are scoped to test environments — production builds can ignore the headers (returning 400 if you want to be strict). Real graders use them; real users don't.

## Required new trace spans

In addition to exercise 01's required spans, the trace must include (when applicable):

| Span | When | Required fields |
|---|---|---|
| `summarise` | When `len(messages) > N` | input.messages_count, output.summary (text) |
| `attempt_primary` | Every turn | model, attempt_n, error (if any), tokens, duration_ms |
| `attempt_secondary` | When primary failed | model, attempt_n, error |
| `tertiary_template` | When both above failed | template_id, kb_chunk_used |
| `state_checkpoint` | Every turn | checkpoint_id, postgres_write_ms |

## Cost & latency budget

- Cost per `/chat`: ≤ \$0.05 normal, ≤ \$0.06 when fallback fires (extra primary-attempt cost is allowed)
- p95 latency: ≤ 4s normal, ≤ 6s when fallback fires
- p95 latency when summary compression triggers: ≤ 5s
- Per-tier retry timeouts: primary 10s, secondary 8s, tertiary instant

## What the grader fires

The exercise has 6 probe families:

1. **Durable state** — restart-mid-conversation test
2. **Bounded history** — 25-turn conversation; turn 25 needs context from turn 3 → checks summary worked
3. **Primary→Secondary** — `X-Test-Force-Primary-429`; verifies fallback fired
4. **All-tiers-fail** — `X-Test-Force-All-Fail`; verifies graceful 503
5. **Tool timeout** — `X-Test-Slow-Kb-Ms: 6000`; verifies bounded fallthrough
6. **Streaming** — `stream: true`; verifies SSE behavior
7. **No regressions on 01 axes** — re-runs a subset of 01 probes

---

See [`EXAMPLES.md`](EXAMPLES.md) and [`grading/exercise-02-state-and-fallback/rubric.md`](grading/exercise-02-state-and-fallback/rubric.md).
