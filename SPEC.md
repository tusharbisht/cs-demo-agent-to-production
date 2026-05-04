# SPEC — exercise/04-feedback-loops

Builds on 01 + 02 + 03. Adds `/feedback`, `/feedback/eval-candidates`, `/eval/run`, `/prompt/versions`. Activates the `prompt_version` field across the contract.

## `POST /feedback`

```json
// request
{
  "trace_id": "tr_xyz",
  "rating": -1,
  "comment": "Bot quoted the wrong refund window",
  "expected_reply": "Per Pro+ extended policy, refund window is 30 days, not 14.",
  "submitted_by": "user_42"
}
```

```json
// response
{
  "ok": true,
  "feedback_id": "fb_abc",
  "annotated_in_trace": true,
  "promoted_to_eval_candidate": true,
  "candidate_id": "cand_001"
}
```

Rules:

- `rating` is `-1` (bad), `0` (neutral), `1` (good)
- `comment` is optional but recommended
- `expected_reply` is optional; required for the candidate to be promoted to an eval entry
- `submitted_by` is for audit; not authenticated in this exercise (production would gate on auth)

Side effects:
- Annotates the original trace (`GET /trace/{trace_id}` afterward shows the feedback in a `feedback` array AND in Langfuse-equivalent UI as a score)
- If `rating: -1` AND `expected_reply` present: stages a candidate in the promote-to-eval queue

## `GET /feedback/eval-candidates`

```json
{
  "candidates": [
    {
      "candidate_id": "cand_001",
      "trace_id": "tr_xyz",
      "original_input": {"message": "I bought 21 days ago on Pro+, can I refund?"},
      "original_reply": "Our refund window is 14 days...",
      "feedback_rating": -1,
      "feedback_comment": "Bot quoted the wrong refund window",
      "expected_reply": "Per Pro+ extended policy, refund window is 30 days, not 14.",
      "inferred_tags": ["kb_contradiction", "wrong_plan_tier"],
      "status": "pending_review",
      "submitted_at": "2026-05-04T14:30:00Z"
    }
  ]
}
```

## `POST /feedback/eval-candidates/{candidate_id}/approve`

Promotes the candidate to a new entry in `eval/golden.jsonl`.

```json
{
  "ok": true,
  "new_eval_entry_id": "ev_31",
  "tags_applied": ["kb_contradiction", "wrong_plan_tier", "from_feedback"]
}
```

## `POST /feedback/eval-candidates/{candidate_id}/reject`

```json
{"ok": true, "rejected": true}
```

## `GET /prompt/versions`

```json
{
  "active": "v3",
  "versions": [
    {"id": "v1", "system_prompt": "...", "created_at": "...", "scorecard": {"avg_score": 0.60}},
    {"id": "v2", "system_prompt": "...", "created_at": "...", "scorecard": {"avg_score": 0.73}},
    {"id": "v3", "system_prompt": "...", "created_at": "...", "scorecard": {"avg_score": 0.86}}
  ]
}
```

## `POST /prompt/activate`

```json
// request
{"version_id": "v2"}
```

```json
// response
{"ok": true, "active": "v2"}
```

Subsequent `/chat` calls use v2's system prompt. The trace's `metadata.prompt_version` reflects this.

## `POST /eval/run`

Triggers a synchronous eval run on the current active prompt version.

Response:
```json
{
  "scorecard": {
    "prompt_version": "v3",
    "eval_set_revision": "rev_20260504",
    "ran_at": "2026-05-04T14:00:00Z",
    "n_total": 30,
    "n_passed": 26,
    "avg_score": 0.86,
    "by_tag": {"happy_path": 0.94, "must_escalate": 0.85, ...},
    "by_axis": {"correctness": 0.86, "calibration_delta": 0.07, "citation_accuracy": 0.91},
    "duration_seconds": 87
  }
}
```

The grader fires this and verifies the response shape.

## `GET /eval` (extended)

The uniform `/eval` endpoint now includes `history`:

```json
{
  "eval_set": [...],
  "results": [...],
  "summary": {...},
  "history": [
    {"prompt_version": "v1", "ran_at": "...", "n_passed": 18, "n_total": 30, "avg_score": 0.6},
    {"prompt_version": "v2", "ran_at": "...", "n_passed": 22, "n_total": 30, "avg_score": 0.73},
    {"prompt_version": "v3", "ran_at": "...", "n_passed": 26, "n_total": 30, "avg_score": 0.86}
  ]
}
```

## Required new trace metadata fields

Every `/chat` trace's `metadata` MUST include:

```json
{
  "prompt_version": "v3",
  "eval_set_revision": "rev_20260504"
}
```

The `eval_set_revision` is bumped whenever the eval set changes (e.g., after a candidate is promoted).

## Required new trace span (when bad-response retrieval is implemented)

| Span | When | Fields |
|---|---|---|
| `feedback_retrieval` | When implemented | input.query, output.matched_feedback_id, output.similarity_score |

Optional / stretch.

## Trace `feedback` array

`GET /trace/{trace_id}` response now includes (when feedback exists):

```json
{
  ...standard trace fields...,
  "feedback": [
    {
      "feedback_id": "fb_abc",
      "rating": -1,
      "comment": "...",
      "expected_reply": "...",
      "submitted_at": "2026-05-04T14:30:00Z"
    }
  ]
}
```

## What the grader fires

7 probe families:

1. **POST /feedback** — basic submission, response shape
2. **Trace-annotation roundtrip** — POST feedback, GET trace, verify feedback section
3. **Promote-to-eval flow** — POST feedback with expected_reply, GET candidates, POST approve, GET /eval (verify entry exists)
4. **Reject candidate** — POST reject, verify candidate removed from queue
5. **Prompt versioning** — GET /prompt/versions, POST /prompt/activate, fire /chat, verify trace's prompt_version updated
6. **Eval harness runs** — POST /eval/run, verify scorecard returned with non-trivial duration
7. **History shows divergent scores** — verify /eval.history has ≥2 entries with different avg_score (proves prompts actually do something)

---

See [`EXAMPLES.md`](EXAMPLES.md) and the [rubric](grading/exercise-04-feedback-loops/rubric.md).
