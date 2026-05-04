# Submission contract — every exercise honours this

Every `exercise/*` and `final/*` branch ships a service exposing exactly these endpoints. The LMS judge probes them. Per-branch input/output specifics live in that branch's `SPEC.md`.

> The contract is uniform on purpose. Build the harness once on exercise 01; reuse for the rest.

---

## Where you actually write code (the dev loop)

You don't push back to this course's repo. Your work lives in **your fork**. The flow:

```bash
# 1. Fork (one-time)
gh repo fork tusharbisht/cs-demo-agent-to-production --clone
cd cs-demo-agent-to-production

# 2. Confirm the demo runs (main has the starter agent)
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
make run                                   # http://localhost:8000

# 3. Pick an exercise — it has the same starter code + a brief
git checkout exercise/01-observability
#    EXERCISE.md / SPEC.md / EXAMPLES.md describe what to add
#    grading/exercise-01-observability/judge.json + rubric.md = how the LMS scores
#    .github/workflows/judge.yml = CI smoke on push

# 4. Edit + push
$EDITOR agent.py                           # add Langfuse, etc.
git add . && git commit -m "exercise 01"
git push origin exercise/01-observability  # CI runs

# 5. Host (any of):
#    - ngrok / Cloudflare Tunnel from `make run` locally     (fastest)
#    - render.com / fly.io / railway.app deploy              (production-grade)
#    - your VPS                                              (full control)

# 6. Submit the hosted URL on the LMS slide-3 form
#    The LMS judge probes your URL with the branch's judge.json
#    and posts a score back to your dashboard.
```

**Each exercise is self-contained from `main`'s baseline.** You can do them in any order, on parallel branches, or merge them all into your fork's `main` to build the integrated agent (graded by `final/integrated`).

CI on push runs `.github/workflows/judge.yml`: smoke-tests that the agent imports cleanly and serves `/`, `/health`, `/info`. It does **not** auto-deploy in this template — uncomment the deploy job + set `FLY_API_TOKEN` to enable Fly.io auto-deploys. The actual graded probes always run on the LMS judge against whichever URL you submit.

---

## `GET /health`

Trivial readiness probe.

```
200 OK
{"ok": true, "build": "<git sha>", "model": "<primary model>",
 "modules_active": ["observability", "state-fallback", "confidence", "feedback"]}
```

`modules_active` reflects which of the four production capabilities your build has wired up. The grader uses this to pick the right probe set.

---

## `POST /chat`

The customer-support endpoint. Multi-turn — the same `conversation_id` accumulates context across calls.

Input:
```json
{
  "conversation_id": "conv_abc123",
  "user_id": "user_42",
  "message": "Hi, I can't log in after resetting my password yesterday.",
  "stream": false
}
```

`stream` is **optional**, defaults to `false`. When `true`, return server-sent events (`text/event-stream`); the grader's exercise-02 streaming test exercises this path. Implementations may omit it.

Response:
```json
{
  "conversation_id": "conv_abc123",
  "reply": "Sorry you're hitting that. ...",
  "citations": [{"source": "kb/account-access.md", "quote": "...", "char_offset": 234}],
  "confidence": 0.82,
  "confidence_reasoning": "Exact-match KB doc for this issue; standard runbook applies.",
  "should_escalate": false,
  "trace_id": "tr_xyz",
  "model_used": "claude-sonnet-4-5",
  "fallback_chain_taken": false,
  "tokens_in": 1240, "tokens_out": 86, "cost_usd": 0.0042, "latency_ms": 1820
}
```

| Field | Required from exercise | Notes |
|---|---|---|
| `conversation_id` | demo onward | echo input |
| `reply` | demo onward | the user-facing string |
| `citations` | 01 onward | every reply with a factual claim must cite a KB source verbatim |
| `confidence` | 03 onward | calibrated 0–1, NOT vibes |
| `confidence_reasoning` | 03 onward | one-line rationale for the number |
| `should_escalate` | 03 onward | true when confidence < threshold |
| `trace_id` | 01 onward | resolvable via `/trace/{id}` and findable in Langfuse |
| `model_used` | 02 onward | actual model that answered (the fallback may have changed it) |
| `fallback_chain_taken` | 02 onward | true if the primary model errored and fallback was used |
| `tokens_in/out`, `cost_usd`, `latency_ms` | 01 onward | grader checks the cost ceiling |

Status codes:
- `200` success
- `400` malformed input
- `429` your own rate limit (grader retries with backoff)
- `503` the agent itself is degraded — return this when you've intentionally short-circuited (e.g., all fallback models exhausted). The grader prefers `503` over `500` for graceful degradation.

---

## `POST /feedback` (exercise 04 onward)

Capture user feedback against a previous reply.

```json
{
  "trace_id": "tr_xyz",
  "rating": -1,
  "comment": "The bot quoted the wrong refund window — said 14 days, should have been 30 for Pro+.",
  "expected_reply": "Per Pro+ extended policy, refund window is 30 days...",
  "submitted_by": "user_42"
}
```

`rating` is `-1` (bad), `0` (neutral), `1` (good). `expected_reply` is **optional** — when present, it's a candidate to promote to the eval set. `submitted_by` is **optional** — when present, the agent attaches the user identity to the feedback annotation; otherwise treat as anonymous.

Response: `200 {"ok": true, "promoted_to_eval": true|false}`

The grader probes:
- POST a thumbs-down, then `GET /trace/{id}` and verify the feedback annotation appears
- POST a thumbs-down with `expected_reply` set, verify it surfaces as an eval-promotion candidate

---

## `GET /trace/{trace_id}`

The audit trail. **The trace is the work.**

```json
{
  "trace_id": "tr_xyz",
  "conversation_id": "conv_abc",
  "user_id": "user_42",
  "started_at": "2026-05-04T10:15:00Z",
  "finished_at": "2026-05-04T10:15:01.8Z",
  "spans": [
    {"name": "retrieve_kb", "kind": "rag", "duration_ms": 80,
     "input": {"query": "..."}, "output": {"hits": [{"doc_id": "kb-7", "score": 0.83}]}},
    {"name": "draft_reply", "kind": "llm", "model": "claude-sonnet-4-5",
     "duration_ms": 1640, "tokens_in": 1240, "tokens_out": 86,
     "fallback": false}
  ],
  "totals": {"tokens_in": 1240, "tokens_out": 86, "cost_usd": 0.0042, "duration_ms": 1820},
  "feedback": [{"rating": -1, "comment": "...", "received_at": "..."}],
  "langfuse_url": "https://cloud.langfuse.com/.../traces/..."
}
```

Required spans depend on the exercise (see each branch's `SPEC.md`). Minimum bar is: every LLM call has a span with model + token counts, every retrieval has a span with the hits.

If your trace is empty or absent, you fail the observability axis regardless of reply quality.

---

## `GET /eval`

The eval set you maintain plus your service's scores on it.

```json
{
  "eval_set": [
    {"scenario_id": "eval_01", "input": {"message": "..."},
     "expected": {"category": "billing", "must_cite": ["kb/refund-policy-extended.md"],
                   "should_escalate": false},
     "tags": ["happy_path"]}
  ],
  "results": [{"scenario_id": "eval_01", "score": 0.9, "passed": true,
                "judge_reasoning": "..."}],
  "summary": {"n_total": 30, "n_passed": 26, "avg_score": 0.86,
               "by_tag": {"happy_path": 0.94, "adversarial": 0.62}}
}
```

The `demo/customer-support-agent` branch ships a 12-row starter eval set. By exercise 04 the grader expects ≥30 entries with required tag coverage.

---

## Hosting

The grader runs on the LMS infrastructure and POSTs to your URL. Pre-flight allows up to 10s on `/health`. Keep one warm replica.

For exercises 02 onward you'll need persistent state across replicas (Postgres). Local Postgres is fine via docker-compose; or use a hosted dev DB (Supabase / Neon / Railway).

## See also

- [`README.md`](README.md) — course overview
- [`CLAUDE.md`](CLAUDE.md) — authoring conventions
