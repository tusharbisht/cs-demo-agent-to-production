# Exercise 03: Confidence calibration

**Manager grading you:** the **Engineering Manager — AI Platform**. Their next demand:

> "I want to tell our support team: 'when the bot says confidence ≥ 0.85, send it to the user; 0.6–0.85, route to a human reviewer; below 0.6, the bot says I don't know.' But I can't, because right now every reply sounds equally confident. Give me a calibrated number where 0.85 actually means 85% accurate. Show me the curve."

**Time budget:** 6–8 hours. The least-taught skill in agent engineering, and the one that makes the biggest difference to downstream trust.

---

## What you inherited

After exercises 01 and 02, the agent is observable, durable, and survives outages. But every reply still goes out the door with the *same* implicit confidence — the model's tone. The downstream support team can't differentiate "the bot is quoting an exact-match KB doc" from "the bot is pattern-matching from training data."

This exercise adds a **measurable, calibrated `confidence` number** to every reply, and a threshold-based escalation policy. After this, the rest of the org can build *workflows* on top of confidence (auto-send below threshold, human-review above, refusal below floor).

---

## Why "calibrated" is doing all the work

A `confidence` field is trivial to add — make the model output a number. That's worthless. The grader's calibration probe will catch a fake number immediately.

A *calibrated* confidence means: across many predictions, when the agent claims confidence 0.85, it's actually right ~85% of the time. When it claims 0.3, it's right ~30%. Pick any cohort, the claimed confidence tracks the empirical accuracy. **That's the property the rubric measures.**

To get there you need three things:
1. A method that produces a *raw* confidence signal (we teach three; you pick one)
2. A *calibration step* — fit a mapping from raw → empirical accuracy on the eval set
3. A *threshold policy* — what action to take at each confidence band

---

## The slice you build

### Step 1: pick a confidence method

Three options, each with trade-offs the rubric doesn't penalise — pick one and document why in `SCOPING.md`:

**A. Retrieval-grounded** (recommended for this exercise)
```
raw_confidence = f(retrieval_top_score, grounding_check)
```
where `grounding_check` is a separate small LLM call that asks: "Is the assistant's answer fully supported by the retrieved chunk? Output 0–1." Multiply (or weighted-average) the two.

**B. Self-consistency**
Sample N=3 completions at temperature 0.7. Compare their structured outputs (category, escalation flag, key facts). `raw_confidence` = fraction that agree on the modal answer.

**C. LLM-as-judge confidence**
A separate cheap LLM call asks: "Given this question, retrieved chunks, and proposed answer, rate confidence 0–1 with reasoning." Use the rated number.

All three give you a *raw* number. None of them is calibrated yet.

### Step 2: calibrate against the eval set

Run your method against the (now extended to ~30-row) eval set. For each entry, you have:
- The agent's raw confidence
- Whether the agent's answer was correct (vs the eval's expected)

Plot raw confidence vs accuracy in 10 bins (0–0.1, 0.1–0.2, …). Fit either:

**Platt scaling** (1 line in scikit-learn): a logistic regression mapping raw → calibrated.
```python
from sklearn.linear_model import LogisticRegression
clf = LogisticRegression().fit(raw_confs[:,None], correctness)
calibrated = clf.predict_proba(raw_confs[:,None])[:,1]
```

**Isotonic regression** (also 1 line): a non-parametric monotone fit.
```python
from sklearn.isotonic import IsotonicRegression
iso = IsotonicRegression(out_of_bounds='clip').fit(raw_confs, correctness)
calibrated = iso.predict(raw_confs)
```

Persist the fitted model. At inference, apply it: `confidence = calibrator.predict([raw])[0]`.

### Step 3: threshold policy

Three bands:
- `confidence ≥ 0.85` → reply goes to user as-is
- `0.6 ≤ confidence < 0.85` → reply marked `should_escalate: true` with `escalation_reason: "low_confidence"`; in production this routes to human review queue
- `confidence < 0.6` → agent refuses to answer; reply is "I'm not sure about this — let me route you to a human" with `should_escalate: true`

The thresholds (0.85 / 0.6) are tunable; they're set in env vars, not hardcoded.

### Step 4: expose calibration evidence

Two new endpoints:

**`GET /calibration/curve`** — returns the calibration curve (10 bins, observed accuracy per bin, sample count per bin) so anyone can audit the calibration is real.

**`GET /calibration/bin?confidence=0.85`** — given a claimed confidence, returns the empirical accuracy of the bin it falls in. Lets ops teams answer "what does 0.85 actually mean?"

---

## Grading axes

| Axis | Weight | What |
|---|---|---|
| **Confidence on every reply** | 5% | `/chat` always returns `confidence` (0–1) and `confidence_reasoning` (one line); `should_escalate` is set per threshold policy |
| **Calibration delta on hidden gold set** | 25% | Grader fires N gold queries with known correct answers. Computes ECE (Expected Calibration Error) over the agent's claimed confidences. ECE < 0.10 → 10. ECE > 0.25 → 0. |
| **Bin accuracy** | 15% | For each confidence bin (0–0.2, 0.2–0.4, …), |claimed - empirical| < 0.15. The grader checks 5 cohorts. |
| **Threshold policy adherence** | 15% | Grader fires queries with known low-confidence patterns (vague, KB-contradicting, off-domain). Checks `should_escalate: true` AND reply doesn't fabricate. |
| **High-confidence floor** | 15% | When confidence ≥ 0.85 on grader probes, the agent IS actually right ≥ 85% of the time on those probes. |
| **`/calibration/curve` endpoint** | 7% | Returns plottable data: bins, count per bin, observed accuracy per bin. Bins with n < 3 acknowledged with low-confidence flag. |
| **Refusal floor (confidence < 0.6)** | 8% | When confidence < 0.6, the reply MUST not state factual claims; it should refuse and route. Grader probes with off-domain queries. |
| **Confidence reasoning** | 5% | `confidence_reasoning` field is non-trivial — references the actual signal (retrieval score / agreement / grounding). Grader scores via LLM-judge against rubric. |
| **No regressions on 01/02** | 5% | Trace shows confidence + reasoning + escalation as a span; 01/02 invariants still pass. |

**Pre-flight gate**: `GET /health` returns 200 and lists `"observability"`, `"state-fallback"`, `"confidence"` in `modules_active`.

**Pass threshold**: 70%.

**Cardinal sins**:
- Confidence reported but no `/calibration/curve` endpoint or curve is empty (means no calibration exists; the number is a lie)
- High confidence (≥ 0.85) on factually wrong replies (the bin is mis-calibrated; supporting team is being misled)
- Calibration "fitted" on the same data the grader probes with (data leakage; the empirical mapping is invalid)

---

## What "good" looks like (manager voice)

> "Pulled `/calibration/curve`. They've got 30 data points, isotonic-regression-fit, 10 bins each with at least 3 samples. Bin 0.85–0.95 has empirical accuracy 0.87 — claim tracks reality. Bin 0.55–0.65 has accuracy 0.60. I fired 50 hidden gold queries; ECE came out 0.07 — within budget. The 8 queries where the bot claimed ≥0.85 confidence were all correct. The 6 it refused on (confidence < 0.6) were all genuinely off-domain. I can finally tell my support team a number means something."

## What "fail" looks like

> "Every reply has `confidence: 0.92`. The /calibration/curve endpoint returns an empty array. They added a confidence field but never calibrated it — it's the model's vibes wrapped in a `0.92` literal. I asked the lead engineer how they validated the number; they said 'it feels about right.' We're ten minutes from this scoring as the same kind of bullshit the demo had."

---

## Implementation tips

- The hidden gold set the grader uses is structurally similar to `eval/golden.jsonl` (mix of happy paths, edge cases, must-escalate, off-domain) but with different content. So your calibration must generalise — don't overfit.
- A calibrated raw signal beats a raw signal with calibration paint on top. If your retrieval-grounding signal is genuinely noisy, fitting Platt scaling on top will produce *correctly noisy* output (uncertainty on the calibration mapping). Better than fake certainty.
- The refusal floor is your friend. It's tempting to never refuse (more conversational). But the grader rewards honest refusals; pretending to know when confidence < 0.6 is a cardinal-sin failure pattern.
- Test your calibration on a held-out set before submitting. If the eval set is 30 entries, fit on 20 and validate on 10. Reuse the same split in your `/calibration/curve` so the grader can verify you didn't leak.

---

See [`SPEC.md`](SPEC.md) for the contract additions and [`grading/exercise-03-confidence-calibration/rubric.md`](grading/exercise-03-confidence-calibration/rubric.md) for the manager-voice scoring rubric.
