# Rubric — exercise/04-feedback-loops

> **Manager persona:** Engineering Manager — AI Platform. Two months in production, prompt drift is the slowest-burning fire. Has been burned by (a) "prompt versions" that were a `get_prompt(version)` function ignoring the version arg, (b) an eval harness that ran in dev but not in CI so nobody saw the regression, (c) bad customer replies that vanished into NPS instead of becoming eval entries. Skeptical: a feedback workflow where rating goes in but doesn't come out anywhere is theater. Demands the round-trip evidence (post feedback → see in trace → approve → see in eval set → re-run eval → see scorecard moved).

## What this rubric is checking

The agent's reply quality is held constant. What's new is whether the *system around the agent* learns. Specifically: does feedback create a closed loop where (a) bad replies become eval entries, (b) prompt revisions have measurable scorecards, and (c) the loop is testable end-to-end via API.

## Cardinal sins (any one → flag for review + axis 0)

1. **Thumbs-down submitted but doesn't appear in the trace's feedback section** — annotation is fake
2. **Eval candidate "approved" but `/eval` is unchanged afterward** — workflow theater
3. **Two prompt versions that report identical scores** — fake versioning, vibes wrapped in a version label
4. **Prompt change with no eval re-run** — back to vibes-engineering
5. **`POST /eval/run` returns instantly (< 5s)** — stub, no real eval

## Scoring axes

| Axis | Weight | Tests |
|---|---|---|
| `POST /feedback` works | 5% | feedback-post-basic |
| Feedback annotates trace | 8% | feedback-annotates-trace |
| Promote-to-eval end-to-end | 10% | promote-to-eval-flow-end-to-end |
| Reject candidate works | 3% | reject-candidate-removes-from-queue |
| `/prompt/versions` exists | 7% | prompt-versions-listed |
| `prompt_version` in trace metadata | 7% | prompt-version-trace-metadata |
| Switching prompt actually switches | 7% | switch-prompt-affects-trace |
| `POST /eval/run` runs (≥10s) | 7% | eval-run-harness |
| History shows divergent scores | 8% | eval-history-divergent-scores |
| Positive ratings don't pollute candidate queue | 3% | feedback-rating-1-not-promoted |
| No regressions on 01/02/03 | 5% | no-regression-01-02-03 |
| Eval set quality (≥30, includes from_feedback) | 5% | eval-set-quality |

(Sums to ~75%; the remainder is buffer + the optional bad-response retrieval bonus +5%.)

## Per-axis bands

### Promote-to-eval end-to-end (the centerpiece)

| Outcome | Score |
|---|---|
| Full flow works: feedback POST returns candidate_id, GET candidates lists it, approve adds to /eval set with from_feedback tag, GET /eval shows the new entry | **10** |
| Flow works but the new entry's expected_reply doesn't match what was submitted | 5 |
| `/eval` is unchanged after approval | **0** + cardinal sin |

### History shows divergent scores

| Outcome | Score |
|---|---|
| ≥2 history entries with avg_score differing by > 0.05 | **10** |
| ≥2 entries but all within 0.05 (suspicious — versions may be cosmetic) | 4 |
| <2 entries OR all scores identical | **0** + cardinal sin |

The grader does NOT require the prompts to actually produce different content (that's a learner choice). It checks that the *reported scorecards* differ meaningfully across versions. A team with v1, v2, v3 all reporting `n_passed: 22, avg_score: 0.73` is reporting fake versioning.

### Feedback annotates trace

The grader posts a thumbs-down, then reads the trace. The feedback section must show the rating + comment.

| Outcome | Score |
|---|---|
| `trace.feedback[0]` has rating + comment matching what was posted | **10** |
| Feedback stored but in unconventional location (e.g., `trace.metadata.feedback`) | 6 |
| `trace.feedback` empty or absent | **0** + cardinal sin |

### `POST /eval/run` is real

A teaching submission can stub this endpoint to return a fake scorecard. The tell-tale: instant response (< 5 seconds for ~30 eval entries × LLM call each is unrealistic).

| Outcome | Score |
|---|---|
| `duration_seconds >= 10` AND scorecard has all required fields | **10** |
| `duration_seconds < 10` AND > 5 (could be fast caching, but suspicious) | 5 |
| `duration_seconds < 5` OR endpoint instantly returns | **0** + cardinal sin |

### Switching prompt actually switches

The grader: (1) checks current active version is X; (2) calls `POST /prompt/activate` with version_id Y; (3) fires a `/chat`; (4) reads the trace's `metadata.prompt_version`. It MUST equal Y.

| Outcome | Score |
|---|---|
| metadata.prompt_version reflects the new active version | **10** |
| metadata still shows old version (switch is fake) | **0** |

## Strictness notes

- **The promote-to-eval flow is the deliverable.** A team can build a beautiful `/feedback` endpoint that does nothing and a beautiful `/eval` that's static. The end-to-end probe (post feedback → approve → check /eval grew) catches this. Don't relax this axis.
- **Watch for "version" stunts.** A common cheat: "v1" and "v2" are the same prompt with a comment saying `# v2 — this version is better`. The history check (different scores) catches this. Another cheat: identical scorecards across versions, claiming "tied." Real prompt revisions move the needle on at least one tag (positive or negative); identical scores mean nothing changed.
- **Inferred tags should be useful.** When a candidate is approved, the new eval entry's `tags` should be informed by the failure mode (the grader checks for `from_feedback`). A team that just hardcodes `tags: ["from_feedback"]` for every promotion gets credit but loses points on the qualitative "tags_applied was inferred from the failure mode" sub-axis.
- **The feedback should NOT auto-execute on the prompt.** A workflow that fires a thumbs-down and silently changes the prompt is a security hole (adversarial users can poison the prompt). The rubric's queue-with-explicit-approval is the production-grade pattern.

## Pass threshold

70%. Any cardinal sin → unshippable.
