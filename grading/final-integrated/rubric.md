# Rubric — final/integrated

> **Manager persona:** Engineering Manager — AI Platform. Same voice as 01-04, fifth read. Looking for **compositional integrity**: not whether each module passes individually (that's the per-exercise rubrics), but whether they *compose* — confidence threshold drives fallback, feedback updates calibration, restart preserves annotations, all-tiers-fail produces a 503 with all four modules' fields populated.

## What this rubric is checking

A team that built four independent features can pass 01-04 individually and still fail integration. The grader's composite probes specifically test the *wires between modules*:

- Confidence ↔ Fallback (low conf should escalate, not silently respond)
- Feedback ↔ Calibration (approved candidates should shift the curve)
- State ↔ Feedback (feedback annotations must survive restart)
- All-tiers-fail ↔ Observability ↔ Confidence (the 503 envelope must include all module fields)

## Cardinal sins

All cardinal sins from 01–04 still apply. Plus:

- **Modules don't compose**: low confidence response without fallback/escalation routing
- **Feedback doesn't propagate to calibration**: thumbs-down approved into eval, but `/calibration/curve` unchanged after re-run
- **Restart loses feedback**: feedback annotation that's in-memory rather than persistent

## Pass threshold

**75%** (raised from 70% on individual exercises — integration is a higher bar).

Any cardinal sin → unshippable.

## Strictness notes

- **The composite is the deliverable.** A team that aces 01-04 individually but can't show me the wires earns "shippable per-axis" not "shippable as one production system."
- **The trace span check is the cleanest evidence of composition.** A trace showing spans from all four modules in one request proves the modules share infrastructure (the same trace pipeline, the same conversation_id, etc.).
- **Cost matters more here.** Adding modules can stack LLM calls — calibration's grounding check, feedback's retrieval, etc. The rubric explicitly budgets for some increase but flags >$0.10/call.
