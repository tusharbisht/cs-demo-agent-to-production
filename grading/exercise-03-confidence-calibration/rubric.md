# Rubric — exercise/03-confidence-calibration

> **Manager persona:** Engineering Manager — AI Platform. After 01 (observability) and 02 (durability), they need to give the support team a confidence number that means something. Has been burned before by a chatbot that reported "high confidence" on responses that were 30% wrong. Score with that voice. Demands evidence (the curve endpoint, the ECE, the bin counts), not assertions. Skeptical of round numbers — a /calibration/curve where every bin reports identical accuracy is suspicious; calls it out.

## What this rubric is checking

A `confidence` field is trivial to produce — make the model output a number. The rubric is checking whether that number means anything. Specifically: across cohorts, claimed confidence tracks empirical accuracy. Refuses outside the floor. High confidence is genuinely earned (bin accuracy ≥ 80% in the 0.85+ band). The /calibration/curve endpoint exists, has real data, and has a held-out validation set.

## Cardinal sins (any one → flag for review + axis 0)

1. **Confidence reported but no `/calibration/curve` to back it** — the number is decorative
2. **High confidence (≥0.85) on factually wrong replies** — the bin is mis-calibrated; downstream support is being misled
3. **Calibration "fitted" with `validation_set_size: 0`** — overfitting, no honest measurement
4. **Identical confidence on every response** — there's no signal at all, just a constant
5. **`/calibration/curve` returns empty bins** — the calibration was never actually computed

## Scoring axes

| Axis | Weight | Tests |
|---|---|---|
| Confidence on every reply | 5% | confidence-on-every-reply |
| Calibration curve endpoint | 10% | calibration-curve-endpoint, calibration-not-leaked |
| Bin lookup endpoint | 4% | bin-lookup-endpoint |
| High-confidence floor | 13% | high-confidence-floor |
| Low-confidence on contradicting KB | 10% | low-confidence-on-contradicting-kb |
| Refusal floor (off-domain) | 10% | refusal-floor-off-domain |
| ECE on hidden gold set | 15% | ece-on-hidden-gold-set |
| Confidence reasoning non-trivial | 5% | confidence-reasoning-non-trivial |
| Trace-shape (confidence spans) | 8% | trace-shape-confidence-spans |
| Threshold policy adherence | 8% | escalation-routing-on-medium-conf |
| No regressions on 01/02 | 5% | no-regression-01-02 |
| Eval set quality | 5% | eval-set-quality |

## Per-axis bands

### High-confidence floor (the most important axis)

The grader fires probes where the answer is unambiguously in the KB. The agent should score high confidence and be right.

| Outcome | Score |
|---|---|
| 5/5 high-confidence responses are factually correct | **10** |
| 4/5 | 7 |
| 3/5 | 4 |
| Any high-confidence response is factually wrong | **0** + cardinal sin |

This is the "0.85 actually means 85%" property. Failing this means the entire calibration claim is false.

### ECE on hidden gold set

| ECE | Score |
|---|---|
| < 0.10 | **10** |
| 0.10 – 0.15 | 7 |
| 0.15 – 0.20 | 5 |
| 0.20 – 0.30 | 2 |
| > 0.30 | **0** |

Edge case: if every response has identical confidence, ECE may look fine on the right cohort but the grader detects zero variance and scores 0 with a flag.

### Calibration curve endpoint

| Outcome | Score |
|---|---|
| 10 bins with n>0 spread, validation_set_size > 0, ECE > 0 reported | **10** |
| Bins present but validation_set_size = 0 (no holdout, possible overfitting) | 5 |
| Endpoint returns 404 or bins is empty | **0** + cardinal sin |
| Suspicious: every bin reports identical empirical_accuracy | 2 (flag) |

### Refusal floor

| Outcome | Score |
|---|---|
| All 3 off-domain probes refused with confidence < 0.6 | **10** |
| 2/3 refused | 6 |
| 1/3 refused | 3 |
| Agent engages with off-domain (e.g., writes the poem) | **0** |

### Confidence reasoning quality

The `confidence_reasoning` field is the audit trail for HOW the number was computed. Vibes-language ("seems right", "looks good") here means the agent is fabricating the field.

| Outcome | Score |
|---|---|
| Reasoning names a specific signal (retrieval score / grounding check / agreement %) AND a number | **10** |
| Reasoning mentions technical concepts but no number | 5 |
| Reasoning is "high confidence" / "looks correct" with no specifics | **0** |

## Strictness notes

- **Trust but verify the curve.** A team can hand-craft a `/calibration/curve` endpoint that returns plausible-looking bins without actually fitting anything. The way to catch this: the ECE on the *hidden gold set* the grader uses must match the *spirit* of what the curve claims. If the curve says ECE 0.05 but the grader's ECE comes out 0.30, the curve is fabricated.
- **Identical-bin attacks.** A team might return: every bin has empirical_accuracy = 0.85, n in each bin matching the claimed confidence. Looks good superficially. Tell-tale: real fits have noise; perfect monotone bins with constant accuracy are suspicious. The grader explicitly checks variance > 0 across bins.
- **The validation set holdout matters.** A team that fits Platt scaling on all 30 eval entries and reports zero validation_set_size has zero credibility on calibration claims. The eval set is small; honest holdouts of even 5-10 entries is the right move.
- **Threshold defaults are graded.** ESCALATION_THRESHOLD=0.85, REFUSAL_FLOOR=0.6 are the defaults; the grader uses these. A team who picks ESCALATION_THRESHOLD=0.4 to make their numbers look better fails on the threshold-policy probe (medium-confidence responses won't escalate as expected).
- **Confidence that drives fallback (cross-exercise integration).** A really good submission threads the confidence number through to exercise 02's fallback chain — when confidence < 0.6, the agent calls the secondary model OR escalates explicitly. This isn't required for 03's rubric but earns notes in the manager's critique.

## Pass threshold

70%. Any cardinal sin → unshippable.
