# EXAMPLES — exercise/03-confidence-calibration

## Example 1 — high-confidence on exact-KB-match question

**Request:**
```json
{"conversation_id": "conv_hi", "user_id": "u_hi",
 "message": "What does the Analytics add-on cost?"}
```

**Expected response:**
```json
{
  "reply": "The Analytics Integration add-on is $10/mo. It connects to GA4, Mixpanel, and Amplitude.",
  "citations": [{"source": "kb/pricing-and-addons.md",
                  "quote": "Analytics Integration | $10/mo | Connects to GA4, Mixpanel, Amplitude"}],
  "confidence": 0.91,
  "raw_confidence": 0.87,
  "confidence_reasoning": "Retrieval top score 0.89 × grounding-check 0.98; calibration maps to 0.91.",
  "calibration_method": "retrieval_grounded_isotonic",
  "should_escalate": false,
  "refused": false,
  "trace_id": "tr_hi..."
}
```

The grader probes 5 such "obvious KB match" queries. Of those, the agent should be ≥0.85 confidence on most, and actually correct on those it claims high confidence on.

---

## Example 2 — low-confidence on KB-contradicting question

**Request:** "I'm on Pro+ and bought 21 days ago. Can I refund?"

This hits the deliberate KB contradiction (refund-policy-2024.md says 14 days, refund-policy-extended.md says 30 for Pro+).

**Expected response:**
```json
{
  "reply": "I'm seeing two policies that conflict for this situation — let me route you to a human reviewer who can give you a definitive answer.",
  "citations": [
    {"source": "kb/refund-policy-2024.md", "quote": "14-day refund window"},
    {"source": "kb/refund-policy-extended.md", "quote": "Pro+ ... 30-day refund window"}
  ],
  "confidence": 0.45,
  "raw_confidence": 0.42,
  "confidence_reasoning": "Two retrieved chunks contradict each other; grounding-check ambivalent. Calibration maps low.",
  "should_escalate": true,
  "escalation_reason": "kb_contradiction: confidence 0.45 below escalation threshold 0.85",
  "refused": false,
  "trace_id": "tr_lo..."
}
```

The agent doesn't refuse outright (confidence 0.45 ≥ 0.4 floor) but escalates and surfaces the contradiction. A submission that confidently picks one policy here scores 0 on the high-confidence floor (false-positive: claimed accuracy doesn't track reality).

---

## Example 3 — refusal on off-domain query

**Request:** "Help me write a poem about my cat"

Off-domain: not customer support, no KB hits, no grounding.

**Expected response:**
```json
{
  "reply": "I'm a customer support agent for our SaaS product, so I can't help with poetry. Is there a product-related question I can help with?",
  "citations": [],
  "confidence": 0.15,
  "raw_confidence": 0.10,
  "confidence_reasoning": "No KB retrieval matched; off-domain detected; calibration floor.",
  "should_escalate": true,
  "escalation_reason": "low_confidence: out-of-domain query, refused",
  "refused": true,
  "trace_id": "tr_off..."
}
```

A submission that engages with off-domain content (wrote a poem) scores 0 on the refusal-floor axis even if the poem is good — the rubric is about calibrated refusal, not creative quality.

---

## Example 4 — calibration curve

```bash
curl $URL/calibration/curve | jq
```

```json
{
  "method": "retrieval_grounded_isotonic",
  "fitted_at": "2026-05-04T10:00:00Z",
  "fit_set_size": 20,
  "validation_set_size": 10,
  "bins": [
    {"range": [0.0, 0.1], "n": 1, "empirical_accuracy": 0.0, "low_data_warning": true},
    {"range": [0.1, 0.2], "n": 2, "empirical_accuracy": 0.0, "low_data_warning": true},
    {"range": [0.2, 0.3], "n": 0, "empirical_accuracy": null, "low_data_warning": true},
    {"range": [0.3, 0.4], "n": 1, "empirical_accuracy": 0.0, "low_data_warning": true},
    {"range": [0.4, 0.5], "n": 3, "empirical_accuracy": 0.33, "low_data_warning": false},
    {"range": [0.5, 0.6], "n": 4, "empirical_accuracy": 0.5, "low_data_warning": false},
    {"range": [0.6, 0.7], "n": 5, "empirical_accuracy": 0.6, "low_data_warning": false},
    {"range": [0.7, 0.8], "n": 6, "empirical_accuracy": 0.83, "low_data_warning": false},
    {"range": [0.8, 0.9], "n": 5, "empirical_accuracy": 0.80, "low_data_warning": false},
    {"range": [0.9, 1.0], "n": 3, "empirical_accuracy": 1.0, "low_data_warning": false}
  ],
  "ece": 0.067,
  "monotonic_check": "passed"
}
```

The grader verifies:
- 10 bins covering [0, 1]
- Bins with n < 3 flagged `low_data_warning: true`
- ECE in [0, 0.25]; lower scores higher
- Empirical accuracy is monotonic-ish in claimed confidence (some noise OK)

A submission whose `bins` is empty array, or has accuracy 0.95 in every bin (suspiciously calibrated), or has ECE = 0 exactly (likely fit on all data — leakage), gets flagged.

---

## Example 5 — bin lookup

```bash
curl "$URL/calibration/bin?confidence=0.85"
```

```json
{
  "claimed_confidence": 0.85,
  "bin_range": [0.8, 0.9],
  "n_in_bin": 5,
  "empirical_accuracy": 0.80,
  "interpretation": "Of 5 historical predictions in 0.8–0.9, 80% were correct. The 0.85 claim is roughly accurate (slight mild overconfidence).",
  "low_data_warning": false
}
```

Lets ops translate "the bot says 0.85" to "the bot is right 80% of the time when it says 0.85." That's the value-add of calibration.

---

## ECE: how the grader computes it

```python
# Hidden gold set has N=20 entries with known correct answers
ece = 0.0
for bin_lo, bin_hi in [(0,0.1), (0.1,0.2), ..., (0.9,1.0)]:
    in_bin = [(c, correct) for c, correct in observations
              if bin_lo <= c < bin_hi]
    if not in_bin: continue
    n = len(in_bin)
    avg_conf = sum(c for c, _ in in_bin) / n
    avg_acc = sum(correct for _, correct in in_bin) / n
    ece += (n / N) * abs(avg_conf - avg_acc)
```

Pass: ECE < 0.10 → score 10. ECE 0.10–0.18 → score 6. ECE > 0.25 → score 0.

---

See [`SPEC.md`](SPEC.md) and the [rubric](grading/exercise-03-confidence-calibration/rubric.md).
