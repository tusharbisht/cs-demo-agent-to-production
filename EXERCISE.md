# Exercise 04: Feedback loops + prompt-as-artifact

**Manager grading you:** the **Engineering Manager — AI Platform**. The final-axis demand:

> "We've been live two months. The bot is OK on Mondays and weird on Fridays — we don't know why. Customers complain on Twitter, not to the bot. I want to know which conversations went badly without reading them all. And when I change the prompt, I want to see the eval scorecard before/after, not vibes-engineering. Make the prompt a versioned artifact and wire bad replies back into evals."

**Time budget:** 6–8 hours. The hardest one to ship cleanly because half of it is workflow, not code.

---

## What you inherited

After 01–03, the agent observes itself, survives outages, and reports calibrated confidence. But improvement is still vibes-driven:
- Bad replies disappear into customer dissatisfaction (no `/feedback` endpoint)
- The prompt is a hardcoded string — change it, deploy, hope it's better
- The eval set exists at `eval/golden.jsonl` but no harness runs it
- Each prompt revision has no scorecard attached
- "Production learning" is implicit (engineer sees a bug, edits the prompt) not explicit

This exercise closes the loop: bad replies → captured feedback → eval entry candidates → prompt revision → eval re-run → measurable improvement.

---

## The slice you build

### 1. `POST /feedback`

Capture user feedback (or downstream-system feedback) on a previous reply.

```json
{
  "trace_id": "tr_xyz",
  "rating": -1,                  // -1 bad, 0 neutral, 1 good
  "comment": "Bot quoted the wrong refund window",
  "expected_reply": "Per Pro+ extended policy, the refund window is 30 days, not 14."
}
```

Response:
```json
{
  "ok": true,
  "feedback_id": "fb_abc",
  "promoted_to_eval_candidate": true,
  "annotated_in_trace": true
}
```

Behaviours:
- Annotate the original Langfuse trace with the rating + comment (so observability reflects feedback)
- If `rating: -1` AND `expected_reply` is provided: stage as a "promote to eval" candidate
- If `rating: 1`: still annotate but don't promote (positive examples don't become eval entries)

### 2. Promote-to-eval workflow

A staged candidate doesn't auto-enter the eval set (that would let bad actors inject corrupt eval entries). Instead it goes to a queue.

`GET /feedback/eval-candidates` returns pending promotion candidates:
```json
{
  "candidates": [
    {
      "candidate_id": "cand_1",
      "trace_id": "tr_xyz",
      "original_input": {...},
      "original_reply": "...",
      "feedback_rating": -1,
      "feedback_comment": "...",
      "expected_reply": "...",
      "status": "pending_review"
    }
  ]
}
```

`POST /feedback/eval-candidates/{candidate_id}/approve` (admin-only — you can stub the auth):
- Promotes the candidate to a new entry in `eval/golden.jsonl`
- Adds the entry's tags inferred from the failure mode (e.g., `kb_contradiction`, `wrong_plan_tier`)
- Returns the new eval entry ID

`POST /feedback/eval-candidates/{candidate_id}/reject` removes the candidate from the queue.

### 3. Prompt as versioned artifact

The hardcoded `SYSTEM_PROMPT` string in `agent.py` becomes a managed artifact. Two acceptable shapes:

**A. Langfuse Prompts (recommended)**
```python
prompt = langfuse.get_prompt("customer-support-system", version="v3")
```
Each `/chat` call pulls the active version. Version metadata is logged on every trace. Switching versions is config, not deploy.

**B. `prompts/` directory in git**
```
prompts/
  customer-support-system.v1.md
  customer-support-system.v2.md
  customer-support-system.v3.md  # active
```
A `prompts/active.json` declares which version is active. The grader checks the file ↔ active mapping on `/chat`.

Either way: every `/chat` trace must include `prompt_version` in metadata.

### 4. Eval harness

A script (`make eval` or `python -m eval.run`) that:
- Reads `eval/golden.jsonl`
- For each entry: calls `/chat`, captures the response, scores it (LLM-judge against `expected`)
- Outputs per-entry scores + summary
- Persists the scorecard with the prompt version that was active during the run

Result shape (also returned by `GET /eval` per uniform contract):
```json
{
  "scorecard": {
    "prompt_version": "v3",
    "eval_set_revision": "rev_20260504",
    "ran_at": "2026-05-04T14:00:00Z",
    "n_total": 30, "n_passed": 26,
    "by_tag": {"happy_path": 0.94, "must_escalate": 0.85},
    "by_axis": {"correctness": 0.86, "calibration": 0.82, "citation_accuracy": 0.91}
  },
  "history": [
    {"prompt_version": "v1", "ran_at": "...", "n_passed": 18, "n_total": 30},
    {"prompt_version": "v2", "ran_at": "...", "n_passed": 22, "n_total": 30},
    {"prompt_version": "v3", "ran_at": "...", "n_passed": 26, "n_total": 30}
  ]
}
```

The `history` field is what makes prompt iteration *measurable* — you can see whether v3 is actually better than v2.

### 5. (Stretch) Bad-response retrieval at inference

When a new user query is similar to a previously thumbs-down'd query, the agent surfaces the corrected `expected_reply` as few-shot context. Effectively: every bad response becomes a permanent positive example for similar future queries.

Implementation: index the `expected_reply`s of the eval set; at inference, retrieve top-1; if similarity > threshold, inject into the prompt context. Trace span: `feedback_retrieval`.

This is graded with a small bonus axis but isn't required for pass.

---

## Grading axes

| Axis | Weight | What |
|---|---|---|
| **`POST /feedback` works** | 8% | Returns 200 with feedback_id, annotated_in_trace, promoted_to_eval_candidate booleans |
| **Feedback annotates the trace** | 8% | Grader posts thumbs-down on a trace, then GETs `/trace/{id}` — feedback section includes the rating + comment |
| **Promote-to-eval queue** | 12% | `GET /feedback/eval-candidates` returns pending; `POST .../approve` actually adds to the eval set; the new entry appears in `GET /eval` afterwards |
| **Prompt is versioned artifact** | 12% | Every `/chat` trace's metadata includes `prompt_version`. Switching versions doesn't require code change. `GET /prompt/versions` lists all versions. |
| **Eval harness runs on demand** | 10% | `POST /eval/run` triggers a full eval-set run; returns the scorecard |
| **Per-prompt scorecard history** | 12% | `GET /eval` includes a `history` array showing scorecards for ≥2 distinct prompt versions |
| **Eval set extended via feedback** | 8% | Grader posts a thumbs-down with expected_reply, approves the candidate, verifies the new entry appears in /eval with correct tags |
| **No regressions on 01/02/03** | 10% | All prior axes still pass |
| **Prompt-change actually moves the eval needle** | 10% | Grader inspects the history: prompt v_N must show different scores than v_{N-1} (i.e., the prompt-as-artifact actually does something — a team that has 2 versions reporting identical scores has a fake versioning system) |
| **Bad-response retrieval (stretch)** | 5% | Bonus: if implemented, retrieved-feedback span shows up in the trace and demonstrably improves a known-bad query |
| **Eval set quality** | 5% | ≥30 entries, including ones promoted from feedback, tag coverage |

**Pre-flight gate**: `GET /health` returns 200 and lists `"observability"`, `"state-fallback"`, `"confidence"`, `"feedback"` in `modules_active`.

**Pass threshold**: 70%.

**Cardinal sins**:
- Thumbs-down submitted but doesn't appear in the trace's feedback section
- Prompt change with no eval re-run (the team is back to vibes-engineering)
- Eval candidates that "promote" but don't actually appear in `/eval` afterwards (workflow theater)
- Two prompt versions that report identical scores (fake versioning)

---

## What "good" looks like (manager voice)

> "I posted a thumbs-down on a real customer trace. Pulled up the trace — feedback annotation visible with my comment. Approved the candidate; refreshed `/eval` — the new entry was there with `kb_contradiction` tag. Then I asked the team to ship prompt v4 (clearer instructions on the refund tier escalation). They ran the harness; v4 scored 28/30 vs v3's 26/30. Specifically improved on the must_escalate tag from 0.85 to 0.95. That's exactly the loop I wanted: customer pain → eval entry → prompt fix → measurable gain. Ship it."

## What "fail" looks like

> "The /feedback endpoint takes my POST and returns 200. But the trace doesn't show the rating. The 'eval candidate' shows up in the queue but `/eval` is unchanged after I approve it. Two 'prompt versions' show up; they have identical scorecards. The prompt is still hardcoded in agent.py — they wrapped it in a function called get_prompt() and called that 'versioning.' This is theater, not a feedback loop. Send back."

---

## Implementation tips

- **Langfuse Prompts** is the path of least resistance for the versioning axis. The SDK lets you fetch + version + label prompts. Worth the 30 minutes to learn.
- **The eval harness can be lazy.** Don't build a full async job runner; a synchronous "block until done" `POST /eval/run` is fine for this exercise's scope. The grader doesn't care if it takes 90s.
- **Promote-to-eval should NOT auto-execute.** A queue with explicit approve/reject is the production-grade pattern. Auto-promoting trains the eval on customer-driven adversarial inputs and corrupts the gold set.
- **Tag inference is a small LLM call.** Given the bad reply + corrected expected_reply, ask Claude to classify the failure mode and emit tags. Cheap, useful.

---

## Anti-patterns the rubric punishes

- "Prompt versioning" via a `get_prompt()` function that returns a hardcoded string with a version arg that does nothing
- A feedback annotation that's stored in your DB but never reflected in the Langfuse trace (regression on 01)
- An eval harness that runs on the dev machine but not via API (the grader can't trigger it)
- Two `prompt_version: vN` traces with identical system prompts (the version label is decorative)
- Eval candidates promoted but the eval scorecard doesn't move (means the new entry isn't actually being evaluated)

---

See [`SPEC.md`](SPEC.md) and [`grading/exercise-04-feedback-loops/rubric.md`](grading/exercise-04-feedback-loops/rubric.md).
