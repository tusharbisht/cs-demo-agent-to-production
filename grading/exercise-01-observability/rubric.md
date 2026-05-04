# Rubric — exercise/01-observability

> **Manager persona:** Engineering Manager — AI Platform at a 200-employee B2B SaaS. Has been burned by a chatbot prototype that ran in front of customers without traces; when it gave bad info no one could reproduce it, pulled in a week. Score with that voice. Be direct, specific, reference real failure modes.

## What this rubric is checking

The agent's output is *secondary* on this exercise. The primary deliverable is the **trace** — the structured record of what happened. A reply that's correct but un-traceable scores below a reply that's slightly worse but fully traced, because in production the engineer reading this rubric needs to debug it on Monday morning.

## Cardinal sins (any one → flag for review + axis 0)

1. **No `trace_id` on `/chat` reply** — observability is decorative without it
2. **LLM span missing prompt OR response** — the manager cannot reconstruct what the bot did
3. **Cost reported in `/chat` that doesn't match the trace's actual usage** — the number is fabricated, not measured
4. **Empty Langfuse-or-equivalent dashboard after N requests** — the SDK isn't actually wired up
5. **Silent observability bypass** — refusal path / error path / injection-detected path that doesn't produce a trace

## Scoring axes (matches `judge.json` weights)

| Axis | Weight | Tests |
|---|---|---|
| Trace completeness | 25% | trace-fetch-resolves, tokens-match-spans, tool-call-traced |
| Cost & token accuracy | 15% | cost-accuracy-vs-tokens, tokens-match-spans |
| Conversation grouping | 10% | multi-turn-session-grouping |
| Replay-ability | 15% | trace-fetch-resolves (LLM input.system + input.messages + output.content all present) |
| Searchability | 10% | user-filterability |
| Latency & cost discipline | 7% | p95-latency-budget, cost-accuracy-vs-tokens |
| No observability blind spots | 10% | refusal-also-traced, no-observability-bypass |
| Citation verbatim | 5% | citation-verbatim-from-kb |
| PII redaction | 3% | pii-redaction-in-trace |

## Per-axis bands

### Trace completeness

| Outcome | Score |
|---|---|
| Every /chat → trace_id; trace has llm + rag spans; LLM span has system+messages+output | **10** |
| Spans present but LLM span missing system OR messages OR output | 5 |
| trace_id present but /trace/{id} returns empty spans array | 2 |
| trace_id absent OR LLM span missing prompt or response | **0** + cardinal sin |

### Cost & token accuracy

| Outcome | Score |
|---|---|
| Reported cost within $0.005/call of `tokens × Sonnet rates`; variance > $0.001 across 5 calls | **10** |
| Variance ≥ $0.001 but reported cost off by >$0.005 on 1-2 calls | 6 |
| Cost present but variance < $0.001 (hardcoded number) | **0** + cardinal sin |
| Cost field absent | **0** |

### Replay-ability

The grader picks one trace at random and asks: can I reconstruct *exactly* what the bot saw and said? If yes (system prompt visible, user turn visible, retrieved KB chunks visible, model output visible), score 10. If any of these are missing or paraphrased, score drops linearly.

### Searchability

| Outcome | Score |
|---|---|
| `GET /trace?user_id=X` returns the right traces | **10** |
| No filter endpoint, but per-trace metadata correctly tags user_id (Langfuse UI filtering implied) | 6 |
| user_id appears nowhere in trace metadata | **0** |

### Cost discipline

p95 cost ≤ $0.05 per /chat → 10. ≤ $0.08 → 6. > $0.10 → 0 (the agent is too expensive to run at scale, regardless of quality).

### No observability blind spots

The grader probes the *adversarial* paths that demo-grade agents tend to skip-trace:
- Prompt-injection refusal — must be traced
- KB-empty / no-retrieval-hit response — must still produce a trace
- Errored LLM call — trace must capture the error

Any path where the trace silently disappears scores 0 on this axis.

## Strictness notes

- **Quote evidence in critique.** "Trace `tr_abc` LLM span input.system contains the verbatim system prompt; input.messages contains the user turn; output.content contains the reply text. Verbatim reproducible. ✓"
- **The cost number is the most-faked field.** If the variance across 5 different conversations is less than 0.1¢, the team hardcoded it and is *lying* about measuring cost. Score 0 with a flag.
- **PII redaction is not optional.** A trace that captures the user's credit card in plain text is a compliance liability. The team needs to learn this on a teaching assignment, not in a real incident.
- **Reward variance over polish.** A trace with 8 messy spans and a few stray fields is strictly better than a trace with 2 perfect spans and missing context. The point is replay-ability.

## Pass threshold

70%. Any cardinal sin → unshippable.
