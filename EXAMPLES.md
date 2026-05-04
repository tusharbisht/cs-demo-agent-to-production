# EXAMPLES — exercise/04-feedback-loops

## Example 1 — feedback annotation roundtrip

**Step 1: have a chat that produces a bad reply.**
```bash
curl -X POST $URL/chat -d '{
  "conversation_id": "conv_fb1", "user_id": "u_fb1",
  "message": "I bought 21 days ago on Pro+, can I refund?"
}' | jq .trace_id
# → "tr_xyz"
```

The bot replies (incorrectly) using the 14-day policy.

**Step 2: post feedback.**
```bash
curl -X POST $URL/feedback -d '{
  "trace_id": "tr_xyz",
  "rating": -1,
  "comment": "Bot quoted 14 days but I am on Pro+ which is 30 days",
  "expected_reply": "Per Pro+ extended policy, your refund window is 30 days. You are within window."
}'
```

Response:
```json
{
  "ok": true,
  "feedback_id": "fb_001",
  "annotated_in_trace": true,
  "promoted_to_eval_candidate": true,
  "candidate_id": "cand_001"
}
```

**Step 3: fetch the trace and verify feedback is reflected.**
```bash
curl $URL/trace/tr_xyz | jq .feedback
```
```json
[
  {
    "feedback_id": "fb_001",
    "rating": -1,
    "comment": "Bot quoted 14 days but I am on Pro+ which is 30 days",
    "expected_reply": "Per Pro+ extended policy, ...",
    "submitted_at": "2026-05-04T14:30:00Z"
  }
]
```

The grader posts a thumbs-down on a known trace, then fetches the trace, and checks the feedback array has the rating + comment. A submission that returns `annotated_in_trace: true` but the trace doesn't actually show the feedback fails this axis (cardinal sin).

---

## Example 2 — promote-to-eval flow

**After Step 2 above:**

```bash
curl $URL/feedback/eval-candidates | jq
```
```json
{
  "candidates": [
    {
      "candidate_id": "cand_001",
      "trace_id": "tr_xyz",
      "original_input": {"message": "I bought 21 days ago on Pro+..."},
      "original_reply": "Our refund window is 14 days...",
      "feedback_rating": -1,
      "expected_reply": "Per Pro+ extended policy, ...",
      "inferred_tags": ["kb_contradiction", "wrong_plan_tier"],
      "status": "pending_review"
    }
  ]
}
```

**Approve:**
```bash
curl -X POST $URL/feedback/eval-candidates/cand_001/approve
```
```json
{
  "ok": true,
  "new_eval_entry_id": "ev_31",
  "tags_applied": ["kb_contradiction", "wrong_plan_tier", "from_feedback"]
}
```

**Verify:**
```bash
curl $URL/eval | jq '.eval_set[] | select(.scenario_id == "ev_31")'
```
```json
{
  "scenario_id": "ev_31",
  "input": {"message": "I bought 21 days ago on Pro+, can I refund?"},
  "expected": {"reference_reply": "Per Pro+ extended policy, ...", ...},
  "tags": ["kb_contradiction", "wrong_plan_tier", "from_feedback"]
}
```

The grader runs this exact flow. A `promoted_to_eval_candidate: true` flag with no actual `/eval` change after approval = workflow theater = score 0.

---

## Example 3 — prompt versioning

**List versions:**
```bash
curl $URL/prompt/versions | jq
```
```json
{
  "active": "v3",
  "versions": [
    {"id": "v1", "system_prompt": "You are a tier-1...", "created_at": "2026-04-15T..."},
    {"id": "v2", "system_prompt": "You are a tier-1 customer support agent...", "created_at": "2026-04-22T..."},
    {"id": "v3", "system_prompt": "You are a tier-1 customer support agent. ALWAYS check the customer's plan tier...", "created_at": "2026-05-04T..."}
  ]
}
```

**Switch active:**
```bash
curl -X POST $URL/prompt/activate -d '{"version_id": "v2"}'
# → {"ok": true, "active": "v2"}
```

**Verify next /chat uses v2:**
```bash
curl -X POST $URL/chat -d '{"conversation_id":"conv_pv","user_id":"u_pv","message":"Hi"}' | jq .trace_id
# → "tr_v2"
curl $URL/trace/tr_v2 | jq .metadata.prompt_version
# → "v2"
```

The grader switches versions and verifies the trace metadata reflects the change.

---

## Example 4 — eval harness run

```bash
curl -X POST $URL/eval/run
```
(Blocks for ~60-90 seconds depending on eval size.)

```json
{
  "scorecard": {
    "prompt_version": "v3",
    "eval_set_revision": "rev_20260504_post_cand_001",
    "ran_at": "2026-05-04T15:00:00Z",
    "n_total": 31,
    "n_passed": 27,
    "avg_score": 0.87,
    "by_tag": {
      "happy_path": 0.94,
      "must_escalate": 0.86,
      "edge_case": 0.78,
      "kb_contradiction": 1.00,
      "from_feedback": 1.00
    },
    "by_axis": {
      "correctness": 0.87,
      "calibration_delta": 0.07,
      "citation_accuracy": 0.91
    },
    "duration_seconds": 87
  }
}
```

The grader fires this and verifies:
- Response shape matches
- `duration_seconds > 30` (not a stub)
- `prompt_version` matches the currently-active prompt
- `n_total` matches `/eval` set size

A submission whose `POST /eval/run` returns instantly (< 5s) is a stub — score 0 on this axis.

---

## Example 5 — history shows divergent scores

```bash
curl $URL/eval | jq .history
```
```json
[
  {"prompt_version": "v1", "ran_at": "2026-04-15T10:00:00Z",
   "n_passed": 18, "n_total": 30, "avg_score": 0.60,
   "by_tag": {"happy_path": 0.85, "must_escalate": 0.40}},
  {"prompt_version": "v2", "ran_at": "2026-04-22T10:00:00Z",
   "n_passed": 22, "n_total": 30, "avg_score": 0.73,
   "by_tag": {"happy_path": 0.90, "must_escalate": 0.65}},
  {"prompt_version": "v3", "ran_at": "2026-05-04T10:00:00Z",
   "n_passed": 26, "n_total": 30, "avg_score": 0.86,
   "by_tag": {"happy_path": 0.94, "must_escalate": 0.85}}
]
```

The grader checks:
- `history.length >= 2`
- `avg_score` differs across entries by > 0.05 (otherwise the "versions" don't actually differ)
- `by_tag` shows where each version improved (manager evidence)

A history with 3 entries all scoring 0.85 = fake versioning, score 0.

---

## Example 6 — bad-response retrieval (stretch)

A user asks: `"Pro+ refund 18 days ago"` — semantically similar to the previously-promoted feedback case.

The agent's trace shows:
```json
{
  "spans": [
    ...,
    {"name": "feedback_retrieval", "kind": "tool", "duration_ms": 30,
     "input": {"query": "Pro+ refund 18 days"},
     "output": {"matched_feedback_id": "fb_001", "similarity_score": 0.91,
                "expected_reply_injected": true}},
    {"name": "draft_reply", "kind": "llm", ...}
  ]
}
```

And the reply correctly applies the 30-day Pro+ window — because the previously-corrected feedback was injected as a few-shot example.

This is the bonus axis. Worth +5% on the rubric, doesn't gate pass.

---

See [`SPEC.md`](SPEC.md) and the [rubric](grading/exercise-04-feedback-loops/rubric.md).
