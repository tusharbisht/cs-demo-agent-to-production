# Customer Support Agent — Demo to Production

A hands-on course that takes a working-but-fragile customer-support agent from "demoed beautifully on Friday" to "running 24/7 in front of paying customers." You inherit a 150-line FastAPI proof-of-concept and ship four discrete improvements — observability, state + fallback, confidence calibration, and feedback loops — until it has the nervous system a production agent needs.

> Most AI engineering work isn't building an agent from zero. It's hardening an agent someone built from zero. This course is the rehearsal of that.

## The story

```
Friday: a colleague demoed a customer support agent. It worked.
Monday: leadership wants it in front of customers next week.
Tuesday: you open the codebase. There are no traces. No retries. The conversation
         state is in a Python dict. The system prompt is a hardcoded string.
         There's a 12-row eval set but no harness to run it.
You: build the nervous system.
```

That's the course. The starting agent (on `demo/customer-support-agent`) is real, runs locally, and answers customer questions on a small KB. Each exercise branch hardens one production-grade axis. The final branch grades the integrated system as one.

## Course map

| Branch | What you do | Time |
|---|---|---|
| [`tour/from-demo-to-production`](../../tree/tour/from-demo-to-production) | meta-skills — what changes when you cross the demo→prod line, what the grader checks | 30 min |
| [`demo/customer-support-agent`](../../tree/demo/customer-support-agent) | the inherited demo. Read it, run it, dogfood it; identify its production-grade gaps | 1h |
| [`exercise/01-observability`](../../tree/exercise/01-observability) | wire up Langfuse so every LLM/tool/retrieval call is traced, cost-attributed, replayable | 4–6h |
| [`exercise/02-state-and-fallback`](../../tree/exercise/02-state-and-fallback) | LangGraph Postgres checkpointer (durable conversation state), summary memory, primary→fallback model chain, retries, streaming | 6–10h |
| [`exercise/03-confidence-calibration`](../../tree/exercise/03-confidence-calibration) | calibrated `confidence` on every response (claimed conf within 0.15 of empirical accuracy on hidden gold set); threshold-based escalation | 6–8h |
| [`exercise/04-feedback-loops`](../../tree/exercise/04-feedback-loops) | `/feedback` endpoint, promote-to-eval workflow, prompt-as-versioned-artifact, eval harness with per-prompt scorecards | 6–8h |
| [`final/integrated`](../../tree/final/integrated) | the four exercises wired together, graded as one production system | 4h |

Total: 25–35 hours of focused work.

## What "production-grade" means in this course (concretely)

A simulated **Engineering Manager — AI Platform** grades each exercise. Their bar:

> "I want to be able to (a) pull any customer's conversation in 30 seconds and see exactly what happened, (b) restart a worker without losing in-flight conversations, (c) ride out an Anthropic outage without going down, (d) tell my support team what fraction of bot replies they should trust without reading, and (e) prove the prompt is better than last week's."

Cardinal sins (any one → unshippable, regardless of other passing axes):
- A trace missing the LLM prompt+response (means observability is decorative)
- Conversation state lost on worker restart
- A 429 from the primary LLM that propagates as a 5xx to the user
- Confidence claimed without an empirical mapping to back it (uncalibrated number = lie)
- A prompt-only change with no eval re-run

## How submissions are graded

**The deliverable is a hosted URL** — same uniform contract every assignment honours:

```
POST /chat                 user message → agent reply + trace_id + confidence
POST /feedback             {trace_id, rating, comment?}  (added in exercise 04)
GET  /trace/{trace_id}     full agent trace
GET  /eval                 your eval set + your scores
GET  /health               readiness probe
```

The LMS judge worker probes each endpoint with a curated set of scenarios per exercise — happy paths, adversarial inputs, restart-mid-conversation tests, simulated rate-limit responses, calibration probes against a hidden gold set, feedback-loop end-to-end tests. The `rubric.md` on each exercise is written in the manager persona's voice.

See [`SUBMISSION.md`](SUBMISSION.md) for the full contract.

## Quick start

```bash
git clone https://github.com/tusharbisht/cs-demo-agent-to-production.git
cd cs-demo-agent-to-production
git checkout tour/from-demo-to-production    # 30-min orientation
cat EXERCISE.md
git checkout demo/customer-support-agent     # the inherited demo
cat README.md && python agent.py             # run it
```

Then `exercise/01-observability` and onward.

## What you'll need

- An LLM API key (Anthropic / OpenAI / OpenRouter — your choice; the course ships an Anthropic example by default)
- A Langfuse account (free tier — `cloud.langfuse.com` or self-hosted)
- A Postgres database for exercise 02 onward (local docker-compose or hosted)
- A hosting provider (Render / Fly / Railway / your VPS)

Free tiers across these are sufficient.

## What is NOT graded

- Whether you used FastAPI vs. Express vs. Spring Boot
- Whether you used Langfuse vs. Helicone vs. Phoenix vs. homemade traces
- Whether you used LangGraph vs. raw Postgres + a session repo
- Your code style

What IS graded: **what your agent returns, what its trace shows, how its confidence tracks reality, and whether feedback flows back into a measurable improvement.**

## See also

- [`SUBMISSION.md`](SUBMISSION.md) — uniform endpoint contract
- [`CLAUDE.md`](CLAUDE.md) — authoring conventions
- The two prior courses this format inherits from:
  - [`tusharbisht/system-design-hands-on`](https://github.com/tusharbisht/system-design-hands-on) — system-design fundamentals (RAG, agents, vector DBs, MCP, classic distributed-systems primitives)
  - [`tusharbisht/forward-deployed-engineering`](https://github.com/tusharbisht/forward-deployed-engineering) — FDE-shaped workday agents graded by simulated managers
