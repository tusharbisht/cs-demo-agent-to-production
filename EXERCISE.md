# Final: integrated production-grade agent

**Manager grading you:** the **Engineering Manager — AI Platform**. The capstone:

> "I want one URL where I can see all four working together — observability, durability, calibration, feedback. I'll fire the same probes that broke the demo and watch them produce a clean trace, fall through to a fallback when I rate-limit them, refuse calibratedly when off-domain, and turn my thumbs-down into a measurable eval improvement. If all four work together at this URL, we ship."

**Time budget:** 2–4 hours of integration work (assuming 01–04 are landed).

---

## What this branch is

Not a new exercise. The **integration** branch — the four prior exercises wired together as one production-grade agent. Same uniform contract, all four `modules_active` flags set, all four axes graded together.

If you've finished 01–04 cleanly, the final branch is mostly:
- Verifying the modules compose without conflict (e.g., the fallback chain in 02 properly threads through to confidence in 03)
- Ensuring the trace shape captures all four exercises' required spans
- Running an integration smoke that exercises end-to-end behaviour

---

## The composite checks the grader runs

These are *crossover* probes that the per-exercise judges don't fire:

### 1. Confidence drives fallback (03 ↔ 02 wiring)

When `confidence < 0.6` on the primary model, the agent should escalate via the fallback path (not just refuse silently). The trace should show `attempt_primary` → `confidence_check_below_floor` → `escalate_to_human` (or `attempt_secondary` if you wire it that way).

### 2. Feedback updates calibration (04 ↔ 03 wiring)

When a thumbs-down candidate is approved into the eval set AND the eval is re-run, the calibration curve should shift. The grader fires:
- Pre-approval: `/calibration/curve` snapshot
- Post-approval + re-run: another snapshot
- Bins in the relevant range should show different `n` and possibly different `empirical_accuracy`

This proves feedback actually feeds back.

### 3. Restart preserves feedback annotations (02 ↔ 04 wiring)

After posting feedback, restart the worker. The feedback annotation must still be visible on the original trace (it's persisted, not in-process).

### 4. All-tiers-fail preserves observability AND escalates (01 ↔ 02 ↔ 03)

When `X-Test-Force-All-Fail: 1` is set:
- HTTP 503 (02)
- Trace still complete with the failure spans (01)
- `confidence: <low>`, `should_escalate: true`, `refused: true` (03)
- The 503 reply itself is annotated with feedback enabled (04 still active)

### 5. Cost ceiling across all features active

With ALL modules wired, the cost per `/chat` is still bounded. The grader fires 10 standard conversations and checks total cost ≤ $0.50.

---

## Grading axes

Composite of:

- **All four exercise rubrics** (re-run subsets) — 60% (15% each)
- **Confidence ↔ fallback wiring** — 8%
- **Feedback ↔ calibration wiring** — 10%
- **Restart preserves feedback** — 7%
- **All-tiers-fail full envelope** — 8%
- **Composite cost ceiling** — 7%

**Pre-flight gate**: `GET /health` lists all four modules in `modules_active`.

**Pass threshold**: 75% (raised because integration is a higher bar than per-axis).

**Cardinal sins** (combined from all four):
- Any prior exercise's cardinal sins still apply
- Plus: confidence and fallback chain that don't compose (low confidence doesn't trigger any escalation/fallback path)
- Plus: feedback that doesn't reach the calibration curve

---

## What "good" looks like

> "Same URL, all four. I fired a calibrated-confidence probe — got 0.91 confidence on the addon question, reply was correct. Fired a primary-429 — fell through to Haiku in 1.3s, trace showed both attempts with all four modules' fields populated. Posted a thumbs-down on a wrong-tier-policy reply, approved into eval, re-ran the harness; calibration curve shifted in the relevant bin. Restarted the worker; feedback annotation survived. Cost across 10 conversations: $0.31. Ship it."

## What "fail" looks like

> "01 alone passes. 02 alone passes. But when I check `should_escalate` (a 03 field) on a fallback-path response (a 02 path), the field is `null` — the modules don't compose. The team built four parallel features, not one integrated agent."

---

See [`grading/final-integrated/rubric.md`](grading/final-integrated/rubric.md) for the composite scoring rubric.
