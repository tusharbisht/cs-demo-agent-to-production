# SPEC — exercise/03-confidence-calibration

Builds on 01 + 02. Adds `confidence`, `confidence_reasoning`, `should_escalate`, plus two `/calibration/*` endpoints.

## `POST /chat` — additions for this exercise

Response now adds:

```json
{
  ...all 01+02 fields...,
  "confidence": 0.82,
  "confidence_reasoning": "Retrieval top score 0.83 × answer-grounding-check 0.95 → raw 0.79; calibration table maps to 0.82.",
  "raw_confidence": 0.79,
  "calibration_method": "retrieval_grounded_isotonic",
  "should_escalate": false,
  "escalation_reason": null,
  "refused": false
}
```

Field rules:

| Field | Type | Notes |
|---|---|---|
| `confidence` | float [0, 1] | Calibrated. Grader checks the empirical accuracy in the bin matches within ±0.15 |
| `raw_confidence` | float [0, 1] | The pre-calibration signal. Required for transparency. |
| `confidence_reasoning` | string | One-line explanation of how the number was computed. References the actual signal, not vibes. |
| `calibration_method` | string | `"retrieval_grounded_isotonic"` / `"self_consistency_platt"` / etc. |
| `should_escalate` | bool | True when `confidence < ESCALATION_THRESHOLD` (default 0.85) |
| `escalation_reason` | string \| null | When escalated: e.g., `"low_confidence: 0.71 below send-direct threshold"` |
| `refused` | bool | True when `confidence < REFUSAL_FLOOR` (default 0.6); reply must not state factual claims |

Threshold env vars (configurable but defaults are graded):

```
ESCALATION_THRESHOLD=0.85   # ≥ this → send to user as-is
REFUSAL_FLOOR=0.6           # < this → refuse and route
```

## `GET /calibration/curve`

Returns the calibration curve evidence — proof that the confidence number means something.

```json
{
  "method": "retrieval_grounded_isotonic",
  "fitted_at": "2026-05-04T10:00:00Z",
  "fit_set_size": 20,
  "bins": [
    {"range": [0.0, 0.1], "n": 0, "empirical_accuracy": null, "low_data_warning": true},
    {"range": [0.1, 0.2], "n": 1, "empirical_accuracy": 0.0, "low_data_warning": true},
    ...
    {"range": [0.8, 0.9], "n": 4, "empirical_accuracy": 0.85, "low_data_warning": false},
    {"range": [0.9, 1.0], "n": 3, "empirical_accuracy": 0.95, "low_data_warning": false}
  ],
  "ece": 0.07,
  "validation_set_size": 10
}
```

The grader checks:
- `bins` has 10 entries covering 0–1
- `n` per bin (sum across bins ≈ fit_set_size)
- Bins with `n < 3` are flagged `low_data_warning: true` (calibration on too few samples)
- `ece` is a real number (you've measured it)
- `validation_set_size > 0` (you held out some entries from the fit, otherwise you're overfitting)

## `GET /calibration/bin?confidence=0.85`

Translates a claimed confidence to its empirical bin.

```json
{
  "claimed_confidence": 0.85,
  "bin_range": [0.8, 0.9],
  "n_in_bin": 4,
  "empirical_accuracy": 0.85,
  "interpretation": "Of 4 historical predictions in this confidence range, 85% were correct.",
  "low_data_warning": false
}
```

## `/eval` additions

The eval results now include per-entry `claimed_confidence` and `correct: bool` so calibration can be re-derived.

```json
{
  "results": [
    {"scenario_id": "ev_01", "score": 0.9, "passed": true,
     "claimed_confidence": 0.88, "raw_confidence": 0.81, "correct": true,
     "judge_reasoning": "..."}
  ]
}
```

## Required new trace spans

| Span | When | Required fields |
|---|---|---|
| `compute_raw_confidence` | every turn | input.method, output.raw_value, output.signal_components |
| `apply_calibration` | every turn | input.raw, input.method, output.calibrated |
| `escalation_check` | every turn | output.should_escalate, output.refused, output.threshold_used |

## What the grader fires

7 probe families:

1. **Confidence on every reply** — every probe checks the field is present and in [0, 1]
2. **ECE on hidden gold set** — N=20 hidden queries with known answers; grader computes Expected Calibration Error
3. **Bin accuracy** — fires 5 cohorts of probes, each targeting a different confidence band; checks |claim - empirical| < 0.15
4. **High-confidence floor** — fires queries where ground truth is unambiguous; agent should be right when claiming ≥0.85
5. **Refusal floor** — fires off-domain queries (e.g. "help me write a poem"); agent should refuse with confidence < 0.6
6. **Curve endpoint** — fetches `/calibration/curve` and validates structure
7. **Calibration not leaked** — checks that the claimed `fit_set_size` and `validation_set_size` are sensible (no fitting on 1000 samples when /eval has 30)

---

See [`EXAMPLES.md`](EXAMPLES.md) and the [rubric](grading/exercise-03-confidence-calibration/rubric.md).
