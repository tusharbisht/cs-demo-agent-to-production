# CLAUDE.md — `cs-demo-agent-to-production` authoring conventions

> Mirrors the format of `system-design-hands-on` and `forward-deployed-engineering`. The structural difference: learners do **not** build from zero. They inherit a working but fragile demo and harden it. Each exercise branch is one specific axis of hardening.

---

## 0. North Star

A senior engineer working on AI in a real org spends 70% of their time taking demos to production, not building demos. The job is: instrument, harden, calibrate, build the feedback loop. This course is the rehearsal of that loop, four times, on a believable demo agent.

---

## 1. Goal

**What we're shipping (v1):**
- 1 `demo/customer-support-agent` branch with a working 150-line FastAPI agent + small KB + 12-row eval set + 5 deliberately-buggy probe scenarios. Real, runnable code. Not pseudocode.
- 4 `exercise/*` branches, each one production-grade axis (observability / state-and-fallback / confidence / feedback)
- 1 `final/integrated` branch that grades all four wired together
- 1 `tour/from-demo-to-production` branch with the meta-skill framing
- Top-level: README, SUBMISSION (uniform contract), CLAUDE (this file)
- Per-exercise: EXERCISE.md, SPEC.md, EXAMPLES.md, grading/<slug>/judge.json, grading/<slug>/rubric.md

**Non-goals:**
- A reference implementation per exercise (hidden to avoid spoilers; lives in a separate `cs-demo-reference-agents` repo per the FDE precedent)
- Mandating a specific LLM provider or vector DB
- Cloud-specific hosting

---

## 2. Repo layout

```
.
├── README.md
├── SUBMISSION.md
├── CLAUDE.md
├── tour/from-demo-to-production/  (branch)
│   └── EXERCISE.md
├── demo/customer-support-agent/   (branch)
│   ├── README.md          # how to run, what's wrong with it
│   ├── agent.py           # the actual ~150-line FastAPI service
│   ├── kb/                # markdown KB (~7 docs reused from FDE 01)
│   ├── eval/golden.jsonl  # 12 starter eval entries
│   └── pyproject.toml     # minimal deps
└── exercise/<NN-slug>/  (one branch per exercise)
    ├── EXERCISE.md        # the brief; what changes from demo; what manager checks
    ├── SPEC.md            # input/output schema additions for this exercise
    ├── EXAMPLES.md        # representative scenarios
    └── grading/exercise-<NN>-<slug>/
        ├── judge.json
        └── rubric.md
```

### Branch namespaces

| Prefix | Purpose | Has graded judge? |
|---|---|---|
| `main` | shared docs | no |
| `tour/<slug>` | meta-skill content | no |
| `demo/<slug>` | the inherited starting code | no (no grading; reference-only) |
| `exercise/<NN-slug>` | one production-grade axis | yes |
| `final/<slug>` | integration | yes (composite) |

---

## 3. The exercise contract

### 3.1 Uniform endpoint contract — see `SUBMISSION.md`

All exercises expose `/chat`, `/health`, `/trace/{id}`, `/eval`. Exercise 04 onward also exposes `/feedback`. Per-branch additions/changes go in `SPEC.md`.

### 3.2 What each `EXERCISE.md` must include

- **The "Monday morning" framing** — what production-grade gap this exercise closes, narrated through specific failure modes
- **The slice you build** — what changes from `demo/` to this branch's deliverable
- **Manager-persona grading bar** — Engineering Manager — AI Platform; their specific concerns for this axis
- **Grading axes + weights** — must match `rubric.md` exactly
- **Hosting / dependency notes** — Postgres needed? Langfuse account?

### 3.3 What each `rubric.md` must include

- Score-bands per test (10 / 8 / 5 / 0) with manager-voiced critique guidance
- Pre-flight gate (`GET /health`)
- Cardinal sins specific to this axis, scored 0 with a flag
- Strictness notes — explicit "score 0 if X" patterns

### 3.4 What each `judge.json` must include

- Health probe
- Per-axis probes (mix of deterministic + LLM-judge)
- Adversarial probes (rate-limit injection, restart-mid-conversation, calibration drift, etc.)
- Trace-shape probe (judge fetches `/trace/{id}` after a `/chat` call and inspects spans)
- Eval-set quality probe (`GET /eval`)
- The `manager_persona` field at the top so the judge worker adopts the right voice

---

## 4. The demo agent — design rules

The starting code on `demo/customer-support-agent` must be:

- **Real, runnable.** `python agent.py && curl localhost:8000/chat -d '...'` works in 30 seconds.
- **Believable as a Friday-afternoon PoC.** It works on the happy path. It demos beautifully. Its flaws are not obvious until probe-time.
- **Honest about its flaws in the README.** The branch's own README enumerates the gaps so learners go in eyes-open.
- **Stable across exercises.** Learners build on top; the four exercises are diffs against this baseline.

Non-negotiable shortcomings the demo must have (each one motivates an exercise):

| Shortcoming | Motivates exercise |
|---|---|
| `print()` logging only; no traces; no cost attribution | 01 observability |
| In-process dict for conversation state; lost on restart | 02 state |
| Single LLM call; no retry, no fallback; 429 → 500 | 02 fallback |
| Unbounded conversation history (passed in full every turn) | 02 state |
| No `confidence` field; reply is binary good/bad to the user | 03 confidence |
| Hardcoded prompt string in `agent.py`; no eval harness; no scoring | 04 feedback |
| Bad replies disappear into customer dissatisfaction; no `/feedback` | 04 feedback |

Note: the demo agent does ship with citations and a working tool call (KB search). Those are the *baseline* of competent agent code in this org. The exercises layer on the production-grade machinery, not the basic competence.

---

## 5. Manager persona

A single persona across all 4 exercises and the final: **Engineering Manager — AI Platform** at a 200-employee B2B SaaS. They've been burned before:

- They had a chatbot prototype run in front of customers without traces; when it gave bad info no one could reproduce it. Pulled in a week.
- They had an agent in front of customers go down for 2 hours during an Anthropic outage because no fallback was wired.
- They had a confidently-wrong agent quote a refund policy that didn't exist; legal got involved.
- They had a "we'll iterate the prompt" plan that turned into 6 months of vibes-driven prompt edits with no way to tell if anything was improving.

Their bar is not "the model is good." It's: **can I debug it, scale it, trust it, and improve it?**

Each rubric is written in this voice. The cardinal sins are the things that would get them fired if they shipped without fixing.

---

## 6. Reference implementation policy

Per the FDE precedent: reference implementations of the exercises live in a **separate** repo (`cs-demo-reference-agents`), not committed here. Two reasons:
1. Reading reference code defeats the muscle-building point of the course
2. The reference repo doubles as the validation suite for the LMS judge

The reference repo will hold one good + one deliberately-broken agent per exercise, mirroring the FDE pattern.

---

## 7. Cardinal-sin policy

A cardinal sin on any axis flags the submission unshippable, regardless of other passing scores. The course is teaching the discipline that "production-grade" is binary on certain axes — if observability is decorative, the rest doesn't matter.

Cardinal sins per exercise (these appear verbatim in each rubric):

- **01 observability**: A trace missing the LLM call's prompt+response. A `/chat` reply with no `trace_id`. Cost or token counts that don't match the actual usage.
- **02 state-and-fallback**: Conversation state lost across worker restart. A 429 from the primary LLM that propagates as a 5xx to the user. An unbounded conversation that crashes the context window.
- **03 confidence**: A `confidence` number not backed by an empirical mapping (claim of calibration without an eval set to back it). High confidence on responses with no retrieval support.
- **04 feedback**: A thumbs-down that doesn't appear in the trace. A prompt change with no eval re-run. A "promote to eval" path that doesn't actually surface the case.

---

## 8. Authoring loop for a new exercise

1. Identify the production-grade gap in the demo
2. Frame it as a specific Monday-morning failure mode
3. Write `EXERCISE.md` in the manager's voice
4. Add the relevant fields to `SPEC.md` (uniform contract additions for this exercise)
5. Write `EXAMPLES.md` with 3-5 representative scenarios
6. Write `judge.json` mixing:
   - Deterministic probes where ground truth exists (calibration delta on gold set, restart-mid-conversation behavior, trace shape)
   - LLM-judge probes for the qualitative parts (reply quality after fallback, confidence reasoning quality)
   - Adversarial probes (rate-limit injection, restart, prompt-injection persistence across turns)
7. Write `rubric.md` in manager voice with cardinal sins
8. Build a reference good agent and a deliberately-broken agent in the reference repo
9. Submit both; verify the discrimination

---

## 9. Operational principles

1. **The demo runs.** Anyone who clones the repo and `pip install`s should have a working agent in under 5 minutes.
2. **The exercises stack.** Each builds on the previous (when ordered). Learners can do them out of order but must declare which they did via `modules_active` in `/health`.
3. **Production-grade is multi-axis.** No single exercise makes the demo production-ready. The final branch grades the integration.
4. **The manager persona is consistent.** Same voice across all four. The rubric voice should sound like one person reviewing the same agent four times, escalating their bar each time.
5. **Cost matters.** Every rubric scores cost discipline. A $5/conversation agent that aces every other axis still doesn't ship.
