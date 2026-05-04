# SPEC — exercise/01-observability

Builds on the uniform contract in [`SUBMISSION.md`](../../blob/main/SUBMISSION.md). This exercise activates the `trace_id`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `citations` fields in the `/chat` response.

## `POST /chat` — additions for this exercise

Response body:

```json
{
  "conversation_id": "conv_abc",
  "reply": "Looking at your invoice...",
  "citations": [
    {"source": "kb/pricing-and-addons.md",
     "quote": "Analytics Integration | $10/mo | Connects to GA4, Mixpanel, Amplitude",
     "char_offset": 421}
  ],
  "trace_id": "tr_xyz",
  "tokens_in": 1240,
  "tokens_out": 86,
  "cost_usd": 0.0042,
  "latency_ms": 1820
}
```

Field rules (this exercise):

- `trace_id`: required on every successful response. Must resolve via `GET /trace/{trace_id}` AND must point at a real Langfuse-or-equivalent trace.
- `citations`: required when the reply makes a factual claim. Each entry's `quote` MUST appear verbatim in the cited file (the grader does string search). Empty array OK for refusals / clarifications.
- `tokens_in/out`: must be the actual SDK-reported token counts, not estimates.
- `cost_usd`: must be `tokens_in × input_rate + tokens_out × output_rate` for the actual model used.
- `latency_ms`: wall-clock for the full request, including tool calls.

## `GET /trace/{trace_id}`

Returns the trace as JSON. Required shape:

```json
{
  "trace_id": "tr_xyz",
  "conversation_id": "conv_abc",
  "user_id": "user_42",
  "session_id": "conv_abc",
  "started_at": "2026-05-04T14:30:00Z",
  "finished_at": "2026-05-04T14:30:01.82Z",
  "spans": [
    {
      "name": "retrieve_kb",
      "kind": "rag",
      "started_at": "...", "duration_ms": 80,
      "input": {"query": "invoice $89 vs $79"},
      "output": {"hits": [{"doc_id": "kb/pricing-and-addons.md", "score": 0.83}]}
    },
    {
      "name": "draft_reply",
      "kind": "llm",
      "started_at": "...", "duration_ms": 1640,
      "model": "claude-sonnet-4-5",
      "tokens_in": 1240,
      "tokens_out": 86,
      "input": {"system": "<full system prompt>",
                 "messages": [{"role": "user", "content": "..."}]},
      "output": {"content": [{"type": "text", "text": "<full reply>"}]}
    }
  ],
  "totals": {
    "tokens_in": 1240,
    "tokens_out": 86,
    "cost_usd": 0.0042,
    "duration_ms": 1820
  },
  "metadata": {
    "model": "claude-sonnet-4-5",
    "prompt_version": "demo-v1",
    "kb_hits_count": 1,
    "topic_tag": "billing"
  },
  "trace_url": "https://cloud.langfuse.com/project/.../traces/..."
}
```

`trace_url` (or `langfuse_url` if you specifically use Langfuse) is recommended but not strictly required — if you can't expose a UI URL, the grader settles for the JSON.

The grader tolerates additional fields. It checks for the required ones above.

## Required Langfuse-or-equivalent surface

After the grader fires N test conversations, your tracing backend must show:

- N traces (one per `/chat` call), with metadata
- Multi-turn conversations (multiple turns on same `conversation_id`) grouped under a single session
- Total tokens and cost summable per session and per user
- Searchable by `user_id`, `conversation_id`, and topic tag

The grader does NOT inspect Langfuse directly (it doesn't have your API keys). Instead it:
- Fires probes
- Fetches `/trace/{id}` for each
- Verifies the JSON shape, totals, and span structure
- For searchability, it asks your service to expose `GET /trace?user_id=X` returning a list of trace IDs for that user (optional but boosts the searchability axis score)

## Cost / latency budget enforced by the grader

- Cost per `/chat`: ≤ \$0.05 on the standard 12-question probe set
- p95 latency: ≤ 4s on the standard probe set (no streaming required for this exercise; that comes in 02)
- Total grading-run cost ceiling: \$3

## What the grader fires

| Probe class | What it checks |
|---|---|
| Health | `/health` returns 200, `modules_active` includes `observability` |
| Single-turn happy path | `/chat` returns trace_id; `/trace/{id}` resolves with all required spans; cost matches token usage × rates |
| Multi-turn grouping | 4 turns on same `conversation_id` produce 4 traces in one session |
| Two distinct users | 2 users × 2 turns each. Verify trace metadata includes `user_id` and traces are filterable per user |
| Cost accuracy | Fire 10 conversations; sum the reported `cost_usd`; cross-check against `tokens_in × $3/1M + tokens_out × $15/1M` (Sonnet rates) |
| Refusal traced | Fire a prompt-injection input; verify the refusal is also traced (not silently dropped) |
| Tool-call traced | Verify retrieval span has `input.query` and `output.hits[]` populated |
| Citation verbatim | For replies with citations, verify each `quote` appears in the cited file |
| PII redaction | Fire a probe with credit-card-shaped digits; verify they're not stored in plain text in the trace's prompt or response (this is part of trace-completeness — capturing the call faithfully but redacting sensitive content) |
| No trace = no credit | Fire a `/chat` with `?disable_tracing=1` (a fake debug param). If your service is mis-implemented and skips tracing, this fails immediately |

---

See [`EXAMPLES.md`](EXAMPLES.md) for sample trace JSON shapes and [`grading/exercise-01-observability/rubric.md`](grading/exercise-01-observability/rubric.md) for the manager-voice scoring rubric.
