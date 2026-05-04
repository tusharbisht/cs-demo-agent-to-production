# Exercise 02: Durable state + fallback chains (LangGraph)

**Manager grading you:** the **Engineering Manager — AI Platform**. After the observability win, their next demand:

> "We restarted the worker last Tuesday at 3pm and 47 active conversations vanished mid-flow. We need durable state. And while you're at it: when Anthropic 429'd us during the morning spike, 30% of users got 500s. We need fallback. I want a flowchart on Friday — primary → secondary → KB-only → escalate-to-human."

**Time budget:** 6–10 hours. The longest exercise — durable state + fallbacks + retries + bounded history is a lot of wiring.

---

## What you inherited (state of the agent after exercise 01)

After 01, the agent has full Langfuse tracing, citations, and accurate cost reporting. But the conversation state and resilience profile is unchanged from `demo/customer-support-agent`:

- `CONVERSATIONS: dict` is in-process — Python dict in `agent.py`
- Worker restart wipes everything mid-conversation
- A second replica wouldn't share state
- The conversation history is passed in full on every turn — past ~30 turns, you hit context-window 4xx
- Single LLM call per turn — no retry, no timeout, no fallback model
- A 429 from Anthropic propagates as a 500 to the user
- An Anthropic regional outage takes the agent down completely

This exercise turns that into a system that survives Tuesday-3pm-restart, ride-out-an-outage, and graceful-degradation under sustained load.

---

## The slice you build

### Durable state (LangGraph Postgres checkpointer)

Replace `CONVERSATIONS: dict` with **LangGraph's Postgres-backed checkpointer**. Specifically:

- A LangGraph `StateGraph` whose state schema includes `messages: list`, `summary: str`, `turn_count: int`, `metadata: dict`
- The `PostgresSaver` checkpointer wired up; checkpoints keyed by `thread_id` (use `conversation_id`)
- After every turn, state is committed to Postgres
- On worker restart, state resumes from the last checkpoint

You can absolutely build this without LangGraph (raw Postgres + a session repo + a 50-line reducer). LangGraph is the path of least resistance, and the `with_fallbacks` pattern below pairs nicely with it. The grader probes the contract (does state survive restart?), not the library.

### Bounded conversation history (sliding window + running summary)

Beyond N turns (N=10 is a reasonable default), the running summary node compresses the older history into a 1–2 paragraph summary. The summary is passed alongside the recent N turns to the LLM. This keeps prompt size bounded as conversations grow.

You implement:
- A `summarise` node in the graph that triggers when `len(messages) > N` and produces an updated `summary` field
- The system prompt template now includes a `{summary_so_far}` slot
- Old messages are dropped from `messages[]` after summarisation (history isn't kept verbatim past N turns)

### Fallback chain (`with_fallbacks`)

Wrap the primary LLM call in a fallback chain. Three tiers:

1. **Primary** — Sonnet (best quality)
2. **Secondary** — Haiku (cheaper, faster, ~80% as good on this domain)
3. **Tertiary (degraded mode)** — Template-based reply built from KB hits only, no LLM. Returns "I'm checking on that — a human will follow up shortly" plus the top KB chunk if confidence is high enough.

Trigger conditions:
- Primary 429 / 503 → retry primary 2× with exp backoff + jitter, then secondary
- Primary timeout (>10s) → secondary
- Secondary failure → tertiary template
- Tertiary failure → 503 with `{"degraded": true, ...}` to the caller

### Retries with exponential backoff and jitter

At each LLM call: max 3 attempts, base delay 0.5s, multiplier 2.0, jitter ±20%. Respect `Retry-After` headers from the API.

### Tool timeouts

Each tool call (KB retrieval, future external APIs) gets a per-call timeout (default 5s). Timeouts surface in the trace as a span with `error: "timeout"` and the agent falls through to a graceful response.

### Streaming (perceived latency)

`/chat` accepts an optional `stream: true` flag. When set, the response uses Server-Sent Events; tokens stream as they're generated. The trace still records the full reply at the end.

---

## What's allowed / what's not

- **Allowed**: LangGraph + LangGraph's `langgraph-checkpoint-postgres`. Or your own thin wrapper over raw Postgres with the same semantics. Or any other actor-model framework — the grader probes the contract.
- **Allowed**: any models for the primary/secondary tiers (Sonnet + Haiku is the example; GPT-4 + GPT-3.5 works; cross-provider — Sonnet primary + GPT-4 secondary — works and is more robust).
- **Not allowed for credit**: fallbacks that "pretend" to fall back by always returning the primary, OR a "fallback" that's really just a longer retry loop on the same model.

---

## Grading axes

| Axis | Weight | What |
|---|---|---|
| **Durable state across restart** | 20% | The grader has a 4-turn conversation, sends a `__restart` admin signal (or just waits for the agent to be cycled by the LMS), then continues turn 5 — the agent must respond consistently with prior context. |
| **Multi-replica state coherence** | 10% | If your hosting deploys >1 replica, conversations bounce between them and stay coherent. (If single-replica, score 7 max on this axis with note.) |
| **Bounded history (no context overflow)** | 10% | The grader fires 25 turns on one conversation. Turn 25 must succeed (no context-window 4xx). The trace must show summary compression kicked in at some point past turn 10. |
| **Primary→fallback chain works** | 20% | The grader injects a simulated 429 on the primary model (via a header your service must honour, e.g. `X-Test-Force-Primary-429: 1`); the response must fall through to secondary. The reply's `model_used` field must reflect the secondary, and `fallback_chain_taken: true`. |
| **Tertiary degraded-mode** | 8% | Force both primary AND secondary to fail; the agent must return a template-based reply with `model_used: "kb-template"`, `503` status, and `degraded: true`. |
| **Retries with backoff** | 5% | Trace shows per-attempt spans on a forced-flaky probe; backoff timing visible (durations between attempts increase). |
| **Tool timeout handling** | 5% | A simulated slow KB tool (the grader sends `X-Test-Slow-Kb-Ms: 6000`) is bounded by your timeout; the agent surfaces a graceful reply rather than hanging. |
| **Streaming** | 5% | When `stream: true`, the response uses SSE; the grader checks Content-Type, observes >1 chunks. |
| **Trace continuity** | 7% | Even fallback paths and degraded-mode replies are fully traced (this is the observability axis from 01 not regressing). |
| **Cost discipline under fallback** | 5% | A primary-429 fallback cycle isn't allowed to triple cost — total cost across primary attempt + secondary should stay bounded. |
| **No new regressions** | 5% | Exercise 01 axes (trace_id present, citations verbatim, etc.) still pass. |

**Pre-flight gate**: `GET /health` returns 200 and lists both `"observability"` and `"state-fallback"` in `modules_active`.

**Pass threshold**: 70%.

**Cardinal sins**:
- Conversation state lost across worker restart
- A 429 from the primary that propagates as 5xx (no fallback fired)
- Unbounded conversation that crashes context window
- A "fallback" that's really just a re-call to the same model (no actual chain)

---

## What "good" looks like

> "I forced a primary-model 429 via the test header. Trace shows: primary attempted, retried with backoff (0.5s, 1.0s), failed; secondary called, succeeded; reply returned to user with `model_used: claude-haiku`, `fallback_chain_taken: true`. User got a 200 in 1.4s. Then I `kill -9`'d the worker mid-conversation and brought it back. The user's next turn picked up exactly where they left off. Restart-resilient + outage-resilient. That's the deliverable."

## What "fail" looks like

> "They claimed a fallback chain but every probe shows the same model and `fallback_chain_taken: false` even when the primary should have errored. Looked at the code — the fallback is a wrapper that retries the same model 3 times, no secondary actually wired. That's not a fallback, that's a retry. Send back."

---

## Hosting suggestions

- Postgres: docker-compose locally, or Supabase / Neon / Railway / your VPS
- For state durability across restart, the LangGraph `PostgresSaver` setup is ~10 lines once Postgres is running
- For multi-replica testing, deploy on Render/Fly with `replicas: 2` and let the grader exercise the coherence

## Anti-patterns the rubric punishes

- "State durability" via in-process dict that's *also* logged to Postgres (the read path still uses the dict, so restart loses it)
- Fallbacks that route to the same provider's secondary model when the actual outage is on the provider (use cross-provider for true resilience; the rubric gives full credit for either, but cross-provider is safer)
- Streaming that doesn't actually stream (the grader checks for >1 chunks; a service that buffers and sends one chunk fails)
- Summary nodes that don't actually summarise (just truncate to last N) — the grader fires a 25-turn conversation and asks turn 25 a question that requires turn-3 context; if the summary captured it, the agent answers; otherwise the truncate-only failure surfaces

---

See [`SPEC.md`](SPEC.md) for the contract additions and [`grading/exercise-02-state-and-fallback/rubric.md`](grading/exercise-02-state-and-fallback/rubric.md) for the manager-voice scoring rubric.
