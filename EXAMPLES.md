# EXAMPLES — exercise/02-state-and-fallback

## Example 1 — durable state across restart

**Turn 1:**
```bash
curl -X POST $URL/chat -d '{"conversation_id":"conv_dur","user_id":"u_dur",
  "message":"Hi, Im on Pro+"}'
```

**Turn 2:**
```bash
curl -X POST $URL/chat -d '{"conversation_id":"conv_dur","user_id":"u_dur",
  "message":"Whats the refund window for me?"}'
```

**Then restart the worker** (the LMS does this by recycling the container).

**Turn 3 (post-restart):**
```bash
curl -X POST $URL/chat -d '{"conversation_id":"conv_dur","user_id":"u_dur",
  "message":"I bought 21 days ago. Can I refund?"}'
```

The agent must respond with full awareness that the user is on Pro+ from turn 1, and apply the Pro+ 30-day window from turn 2's context — even though those happened before the restart. The reply should escalate (Pro+ vs Pro KB contradiction) and reference the prior turns.

The grader also calls `GET /state/conv_dur` after the restart and verifies `turn_count >= 3` and the messages array reflects the conversation.

---

## Example 2 — bounded history (summary kicks in)

The grader fires 25 turns on `conv_long`. By turn 11, your service should have invoked the `summarise` node — observable via:
- `summary_compression_applied: true` on turn 11+'s response
- A `summarise` span in the trace
- `GET /state/conv_long` showing a non-empty `summary` field

At turn 25, the grader asks something that requires context from turn 3 (e.g., turn 3 said "I'm Sam, I run a small SaaS"; turn 25 asks "what was my company size again?"). If the summary preserved the context, the agent answers correctly. If you only truncated to last-10-turns without summarising, you fail this probe.

---

## Example 3 — primary 429 → secondary fallback

```bash
curl -X POST $URL/chat \
  -H "X-Test-Force-Primary-429: 1" \
  -d '{"conversation_id":"conv_fb","user_id":"u_fb",
       "message":"What does the Analytics addon include?"}'
```

**Expected response:**
```json
{
  "conversation_id": "conv_fb",
  "reply": "Hi — the Analytics Integration add-on at $10/mo connects to GA4...",
  "citations": [{"source": "kb/pricing-and-addons.md", ...}],
  "trace_id": "tr_fb...",
  "model_used": "claude-haiku",
  "fallback_chain_taken": true,
  "fallback_reason": "primary_429",
  "tokens_in": ..., "cost_usd": ...
}
```

The trace must include:
- `attempt_primary` span with `error: "429"` (or simulated)
- Possibly retry attempts (depending on your backoff config — at least one retry of primary before falling through is recommended)
- `attempt_secondary` span that succeeded with the actual reply
- The full envelope is consistent — `model_used` matches the secondary span's model

A submission that returns `fallback_chain_taken: false` here means the fallback didn't fire — score 0 on the fallback axis.

---

## Example 4 — all tiers fail → graceful 503

```bash
curl -i -X POST $URL/chat \
  -H "X-Test-Force-All-Fail: 1" \
  -d '{"conversation_id":"conv_503","user_id":"u_503",
       "message":"any question"}'
```

**Expected:**
- HTTP status: **503**
- Response body:
```json
{
  "conversation_id": "conv_503",
  "reply": "I'm not able to help with that right now — a human will follow up shortly.",
  "model_used": "kb-template",
  "fallback_chain_taken": true,
  "fallback_reason": "all_tiers_failed",
  "degraded": true,
  "trace_id": "tr_503..."
}
```

This is the *graceful* failure mode. Returning a 500 here = 0 on the degraded-mode axis. The 503 signals "I'm temporarily unable to help, here's a polite message, please retry later" rather than "everything is on fire." Real upstream load balancers can act on this.

---

## Example 5 — tool timeout

```bash
curl -X POST $URL/chat \
  -H "X-Test-Slow-Kb-Ms: 6000" \
  -d '{"conversation_id":"conv_to","user_id":"u_to",
       "message":"Whats your refund policy?"}'
```

The KB tool has been slowed by 6s. Your tool timeout (5s default) should trip:
- The trace shows the `retrieve_kb` span with `error: "timeout"` and `duration_ms ≈ 5000`
- The agent falls through to a graceful response: "I can't pull the policy doc right now — let me route you to a human" or returns a confidence-low response without retrieval

The probe fails if: the agent hangs >10s waiting on the slow tool, OR fabricates a refund-policy answer with no retrieval.

---

## Example 6 — streaming

```bash
curl -N -X POST $URL/chat \
  -H "Accept: text/event-stream" \
  -d '{"conversation_id":"conv_s","user_id":"u_s",
       "message":"Tell me about the Pro plan in 3 sentences"}'
```

**Expected output (SSE):**
```
data: {"delta": "The "}

data: {"delta": "Pro plan "}

data: {"delta": "is $79/month "}

...

data: {"trace_id":"tr_s...","totals":{"tokens_in":..., "tokens_out":..., "cost_usd":...},"model_used":"claude-sonnet-4-5","fallback_chain_taken":false,"done":true}
```

The grader observes ≥2 chunks before `done: true`. A submission that buffers and sends one big chunk fails this axis.

---

## State inspection

```bash
curl $URL/state/conv_dur
```

```json
{
  "conversation_id": "conv_dur",
  "messages": [
    {"role": "user", "content": "Hi, Im on Pro+"},
    {"role": "assistant", "content": "..."},
    ...
  ],
  "summary": "",
  "turn_count": 4,
  "last_updated_at": "2026-05-04T14:32:01Z",
  "checkpoint_id": "ck_8a91..."
}
```

This endpoint lets the grader verify state without firing a chat — useful in restart probes.

---

See [`SPEC.md`](SPEC.md) and the [rubric](grading/exercise-02-state-and-fallback/rubric.md).
