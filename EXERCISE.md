# Tour — From demo to production

> Read this before exercise 01. ~30 minutes. No code.

## What this course is really teaching

The previous two courses in this series ([`system-design-hands-on`](https://github.com/tusharbisht/system-design-hands-on), [`forward-deployed-engineering`](https://github.com/tusharbisht/forward-deployed-engineering)) rehearsed *building* — picking a problem, writing the agent, shipping the URL.

**This course rehearses the opposite.** You don't build from scratch. You inherit a working demo and you harden it. That's most actual AI engineering work in real orgs.

The split between the two skills matters more than people think:

| Building from zero | Hardening a demo |
|---|---|
| The codebase is yours; the constraints are the spec | The codebase is someone else's; the constraints are reality |
| You can choose the architecture | You inherit it; can refactor only with justification |
| The demo bar is "does the happy path work?" | The bar is "does the unhappy path not break us?" |
| Eval-first is a discipline you adopt | Eval-first is a discipline you retrofit |
| Cost is a Phase 2 concern | Cost matters today; the bill is real |
| Observability comes when you need it | You needed it yesterday; you're hand-debugging in prod |

Most senior engineers find the second column harder, because it's about *seeing what isn't there* — the missing trace, the unmeasured cost, the absent fallback, the unspoken confidence — and naming it.

## The four axes

A production-grade agent needs at minimum four capabilities the demo doesn't have. Each exercise teaches one.

### 1. Observability

> **Without it**: a customer says "the bot told me wrong info." You ask which bot, when, with what prompt. The team shrugs. There's no record.

You wire up Langfuse so every LLM call, tool call, retrieval, and full conversation is captured as a trace. The trace links by `conversation_id` and `user_id`, includes prompt + response + tokens + cost + latency, and is searchable. Cost-per-conversation becomes a number, not a guess.

**Why it goes first**: every other axis depends on you being able to *measure* improvement. Calibration is meaningless without traces of real predictions. Feedback loops need a `trace_id` to attach to. State-and-fallback debugging is hand-wavy without spans.

### 2. State management & fallback chains

> **Without it**: the worker restarts and 47 active conversations evaporate. The Anthropic API returns 429 and the user gets a 500. The conversation hits turn 30 and the context window overflows silently.

You replace the in-process dict with a **LangGraph Postgres checkpointer** — durable state, resumable across restarts, shared across replicas. You add a primary→fallback model chain so a 429 from Sonnet falls through to Haiku, then to a KB-only template. You bound the conversation history with a sliding-window-plus-summary strategy. You add retries with exponential backoff and tool timeouts. You stream the response so perceived latency drops.

**Why LangGraph**: the fallback-chain abstraction (`with_fallbacks`) is genuinely good in this library, and the Postgres checkpointer is one config-line away. You could absolutely build durable state with raw Postgres + a 50-line session repo — and after this exercise you'll be able to swap in your own implementation in an afternoon. The exercise teaches the *pattern*, not the library.

### 3. Confidence calibration

> **Without it**: the agent says "your refund window is 14 days" with the same confident tone whether it's quoting an exact-match KB doc (right) or pattern-matching from training data (wrong). The downstream support team can't tell what to escalate.

You add a `confidence` field to every response. Not vibes. A *measurable* number — computed from retrieval similarity × answer-grounding-check, or self-consistency, or LLM-as-judge confidence (you pick). Then you **calibrate** it: run the chosen method against the eval set, build a calibration table mapping raw → empirical accuracy (Platt scaling / isotonic regression — taught in 30 minutes), apply the inverse at inference. Set a threshold-based escalation policy.

**The grader's calibration probe**: 50 gold queries fired; for each cohort of claimed confidence (e.g., 0.8–0.9), the agent's actual accuracy on that cohort must be within ±0.15 of the claim. That's the testable property.

### 4. Feedback loops

> **Without it**: bad replies disappear into customer dissatisfaction. Improvements require code deploys. The prompt is a hardcoded string. After 6 months you have no idea if the agent is better or worse than launch.

You add `POST /feedback` capturing thumbs ratings + comments + (optional) corrected expected response. Feedback flows into Langfuse as score annotations on traces. Bad responses become candidate eval entries via a "promote-to-eval" workflow. The prompt becomes a versioned artifact (Langfuse Prompts or a `prompts/` git directory) — every revision has its eval scorecard attached. An eval harness runs on demand and on every prompt change.

**The bigger story**: the agent stops being code-that-runs and becomes a system-that-learns. Every customer interaction is potential training data. Every bad response is a future eval case.

## How they compose

The four are not independent improvements. The wiring between them is what makes the system production-grade:

```
                ┌─────────────────────────────────────┐
                │    Observability (Langfuse)         │
                │   traces every LLM/tool/retrieval   │
                └────┬───────────────────────┬────────┘
                     │ traces                │ traces
                     ▼                       ▼
   ┌─────────────────────────┐   ┌─────────────────────────┐
   │  State + Fallback       │   │  Feedback (rating →     │
   │  (LangGraph)            │   │   eval entry)           │
   │  trace_id ↔ conversation│   │  trace_id ↔ feedback    │
   └────────┬────────────────┘   └─────────┬───────────────┘
            │ trace_id                     │ corrected outputs
            └───────────────┬──────────────┘
                            ▼
                ┌──────────────────────────────────────┐
                │    Confidence Calibration            │
                │  claimed conf vs actual on eval set  │
                │  (from feedback);                    │
                │  thresholded routing into            │
                │  fallback chain                      │
                └──────────────────────────────────────┘
```

- Observability traces give Confidence the data to calibrate against
- Confidence's threshold drives Fallback's escalate-to-human path
- Feedback flows into the eval set Confidence calibrates with
- All four use the same `trace_id` / `conversation_id` IDs

A demo agent has none of these wires. A production agent has all four. The course is the rehearsal of wiring them.

## What the manager checks (consistent across all 4 exercises)

A simulated **Engineering Manager — AI Platform** grades each exercise. Their bar:

> "Can I (a) pull any customer's conversation in 30 seconds and see exactly what happened, (b) restart a worker without losing in-flight conversations, (c) ride out an Anthropic outage without going down, (d) tell my support team what fraction of bot replies they should trust without reading, and (e) prove the prompt is better than last week's?"

Their cardinal sins (any one → flag for review):

- **Observability**: a trace missing the LLM prompt+response, or `trace_id` absent from a `/chat` reply
- **State+Fallback**: conversation state lost across worker restart; a 429 propagating as a 5xx
- **Confidence**: a `confidence` number not backed by an empirical mapping
- **Feedback**: thumbs-down that doesn't appear in the trace; prompt change with no eval re-run

These appear in every exercise's `rubric.md`. They don't get easier as you progress.

## Honest framing on libraries

This course names specific libraries:
- **Langfuse** for observability
- **LangChain / LangGraph** for state and fallback chains

Use them. They're the path of least resistance for this assignment, and you'll see them in production codebases.

But the *patterns* are the actual lesson. Once you've built the observability axis with Langfuse, you'll be able to swap to Helicone, Phoenix, Honeycomb, or a homemade tracer in an afternoon. Once you've built durable state with the LangGraph Postgres checkpointer, you'll be able to build your own session repo on top of raw Postgres in a weekend. The libraries are the scaffolding for learning the patterns.

The grader doesn't care which library you use. It probes the contract: are traces visible? Does state survive restart? Does the fallback fire on a simulated 429? Is confidence calibrated against an eval set? Does feedback flow into a measurable improvement?

## Suggested order

```
foundations  →  demo (read + run)  →  01 observability  →  02 state-and-fallback
            →  03 confidence  →  04 feedback  →  final/integrated
```

You can skip ahead if you have prior experience on a specific axis, but the modules build on each other. Confidence's calibration probe needs traces (01) and an eval set (04 or your own). Feedback wires into observability (01). State's fallback chain pairs with confidence's threshold (03). The final branch only makes sense after all four.

## Before you start exercise 01

1. Clone the repo. Check out `demo/customer-support-agent`. Run it. Talk to it. Find five things wrong with it before reading the rest of the docs. Write them down — those are your hypotheses for what the exercises fix.
2. Skim `SUBMISSION.md` on `main`. Internalise the four-endpoint contract.
3. Sign up for Langfuse Cloud (free tier) or stand up self-hosted Langfuse via docker-compose.
4. Decide your hosting target. The grader runs on the LMS infrastructure and POSTs to your URL — pick somewhere reachable from the public internet.

Then go to [`exercise/01-observability`](../../tree/exercise/01-observability).
