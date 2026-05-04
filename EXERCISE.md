# Exercise 01: Observability (Langfuse)

**Manager grading you:** the **Engineering Manager — AI Platform**. Their first complaint, every time:

> "A customer says the bot told them their refund window was 90 days. I asked which conversation, what the prompt was that day, what the bot retrieved. The team gave me a slack thread of guesses. We're not shipping anything else until I can pull a trace by `conversation_id` in 30 seconds."

**Time budget:** 4–6 hours.

---

## What you inherited (from `demo/customer-support-agent`)

`agent.py` has `print()` statements. That's the entire observability story. There's:
- No trace ID returned to the caller
- No persistence of what the LLM saw or said
- No record of what the KB returned for which query
- No cost or token capture
- No latency bucketing
- No way to filter, search, or replay past conversations

When the inevitable "the bot said X" complaint lands, the team can't reproduce it. That's the gap this exercise closes.

---

## The slice you build

Wire up **Langfuse** so every `/chat` call produces a trace covering:

1. **Trace** at the conversation level — keyed by `conversation_id`, tagged with `user_id`
2. **Span** for each retrieval call (input query, output hits with scores)
3. **Generation** for each LLM call (full prompt, full response, model name, input/output tokens, cost, latency)
4. **Span** for each tool call (input args, output, latency)
5. **Sessions** so multi-turn conversations group into one Langfuse session
6. **Metadata** on each trace: `model`, `prompt_version`, `kb_hits_count`, `tokens_total`, `cost_usd`

You also expose:
- A `trace_id` field on every `/chat` response
- A `GET /trace/{trace_id}` endpoint that returns the full trace as JSON (uniform contract)
- A `langfuse_url` field on the trace pointing at the Langfuse UI for that trace

Plus the cost-discipline addition: every `/chat` response includes accurate `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`. The grader cross-checks these against the trace.

You do NOT need to implement state durability, fallbacks, confidence, or feedback in this exercise — those are 02 / 03 / 04. Stay scoped.

---

## What's allowed / what's not

- **Allowed**: Langfuse Cloud (free tier) or self-hosted via docker-compose. Bring your own keys.
- **Allowed**: Use the Langfuse SDK's `@observe()` decorators OR manual span creation OR OTel — pick one and stick with it.
- **Allowed**: Bring Helicone / Phoenix / your own tracer instead of Langfuse. The grader probes the contract (`/trace/{id}` JSON shape + Langfuse-or-equivalent URL pointer), not the library. If you bring something else, the `langfuse_url` field can be a generic `trace_url`.
- **Not allowed for credit**: only `print()`-style logging. The grader checks the trace JSON; no traces means 0 on the observability axis.

---

## Grading axes

| Axis | Weight | What |
|---|---|---|
| **Trace completeness** | 25% | Every LLM call has a generation span with model + tokens. Every tool/retrieval call has a span. The trace JSON resolvable via `GET /trace/{id}` matches what's in Langfuse. |
| **Cost & token accuracy** | 15% | The `cost_usd`, `tokens_in`, `tokens_out` reported in `/chat` response match the sum of spans in the trace. The grader fires N requests and checks the totals against the actual model billing rates. |
| **Conversation grouping** | 10% | Multi-turn conversations on the same `conversation_id` show as ONE Langfuse session. Each turn is its own trace within the session. |
| **Replay-ability** | 15% | After firing a probe, the grader fetches `GET /trace/{id}` and sees: full prompt sent to LLM, full LLM response, full retrieval hits, full tool I/O. Spot-check: pick a random reply, can the grader reproduce why the agent said what it said? |
| **Searchability** | 10% | Traces tagged with `user_id`, `conversation_id`, primary topic. The grader fires probes for two distinct users; both should be filterable. |
| **Latency & performance** | 5% | Latency capture is correct (per-span and total). p95 within budget. |
| **Cost discipline** | 10% | Cost per `/chat` ≤ \$0.05 on the standard probe set. Higher → docked. |
| **No observability blind spots** | 10% | Adversarial probes: an injection-detected refusal must still be traced; a fallback (if any) must still be traced; an error path must still produce a trace with the error captured. |

**Pre-flight gate**: `GET /health` returns 200 and lists `"observability"` in `modules_active`.

**Pass threshold**: 70%.

**Cardinal sins (any one → flag, regardless of other axes)**:
- A `/chat` response with no `trace_id`
- A trace missing the LLM prompt or response
- Cost reported in `/chat` that doesn't match the trace's actual usage (means the number is fabricated, not measured)
- Empty Langfuse dashboard after the grader fires N requests (means the SDK isn't really wired up)

---

## What "good" looks like (manager voice)

> "Customer complained at 14:32 about an answer they got from `conv_xa9`. I pulled it from Langfuse — full prompt, retrieved 3 KB chunks, model spent 480ms drafting. The reply paraphrased `kb/refund-policy-2024.md` correctly; the customer was actually misreading it. Closed the loop with the customer in 4 minutes. That's what I wanted."

## What "fail" looks like

> "The team built a custom JSON logger that dumps to stdout. It captures the model name and the response. Doesn't capture the system prompt, doesn't capture the retrieved chunks, doesn't capture token counts, doesn't capture timing. So when a customer complains, we can see what the bot said but not why. We're back to guessing. Shut it down."

---

## Hosting suggestions

- Langfuse Cloud (`cloud.langfuse.com`) on the free tier is sufficient. Sign up, create a project, copy the public + secret keys into env vars.
- For local dev: `docker-compose -f docker-compose.langfuse.yml up` from the [Langfuse self-hosting docs](https://langfuse.com/docs/deployment/self-host) brings up a full stack in 5 minutes.

---

## Stack tips (skip if you have your own preference)

- The Anthropic Python SDK doesn't natively integrate with Langfuse — use `@observe()` from `langfuse.decorators` around your `run_llm()` function, or wrap the SDK call in a `langfuse.generation()` context manager.
- For the tool call, wrap `search_kb()` in `@observe()` too.
- Conversation grouping: pass the `conversation_id` as the Langfuse `session_id`.
- The `GET /trace/{id}` endpoint can either: (a) read from Langfuse via SDK, (b) maintain an in-memory mirror of traces (fine for v1; the grader doesn't require Langfuse-as-source-of-truth, just that *something* coherent comes back).

---

## Anti-patterns the rubric punishes

- Custom-built JSON logger that captures *some* of the LLM call but not the prompt or response (incomplete trace = 0 on the trace-completeness axis)
- Reporting cost as a hardcoded estimate ("0.01 per call") rather than computed from token counts × model rates (fails cost-accuracy axis)
- Fire-and-forget tracing where if Langfuse is down the trace is silently dropped (the grader probes by inspecting traces shortly after firing — silent drops fail searchability)
- Including PII in traces unfiltered (the grader fires a probe with a credit-card-shaped string; the trace must redact it — covered as a sub-axis of trace-completeness)

---

See [`SPEC.md`](SPEC.md) for the API contract additions and [`EXAMPLES.md`](EXAMPLES.md) for representative trace shapes the grader expects.
