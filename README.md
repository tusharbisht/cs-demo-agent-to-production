# `demo/customer-support-agent` — the inherited demo

> ⚠ This is the **starting state**. Do not modify it here. Each `exercise/*` branch is built on top of this baseline. Read this branch end-to-end first; identify the production-grade gaps; *then* go to `exercise/01-observability`.

## What this is

A 150-line FastAPI customer-support agent. It works. A colleague demoed it on Friday, leadership saw it, and now they want it in front of customers next week.

It uses:
- **FastAPI** + the **Anthropic Python SDK** directly (no LangChain — that comes in exercise 02)
- A small **markdown KB** at `kb/` (~7 docs covering billing, account access, refund policy, known bugs, escalation criteria)
- One **`search_kb` tool** the model can call
- A hardcoded **`SYSTEM_PROMPT`** in `agent.py`
- An **in-process Python dict** for conversation state
- A 12-row **eval set** at `eval/golden.jsonl` — but no harness to run it

## Dependencies (the source of truth)

The dependencies needed to run this agent are declared in [`pyproject.toml`](pyproject.toml) and pinned in [`uv.lock`](uv.lock). The Python version is pinned in [`.python-version`](.python-version).

**Runtime deps:** `fastapi`, `uvicorn[standard]`, `anthropic`, `pydantic`. **Dev extras:** `httpx`, `pytest`. That's the whole list — the demo is intentionally minimal. Each `exercise/*` branch will add its own (e.g., `langfuse` in 01, `langgraph` + `langgraph-checkpoint-postgres` in 02, `scikit-learn` in 03).

## Run it (recommended path: uv)

[`uv`](https://docs.astral.sh/uv/) is the fastest Python package manager. It manages the venv, the lockfile, and the Python version for you. Install once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or:  brew install uv
```

Then:

```bash
git clone https://github.com/tusharbisht/cs-demo-agent-to-production.git
cd cs-demo-agent-to-production
git checkout demo/customer-support-agent

uv sync                                    # creates .venv, installs deps from uv.lock
export ANTHROPIC_API_KEY=sk-ant-...
make run                                   # or: uv run python agent.py
```

**Now open [http://localhost:8000](http://localhost:8000) in a browser.** You'll get a minimal chatbot UI — type a customer-support question, hit Enter, see the reply with token / cost / latency metadata. No curl required to verify the agent is alive.

`make smoke` runs the agent, hits `/health` + `/chat` once, prints results, and tears down — useful as an offline sanity check.

## Run it (fallback: stdlib venv + pip)

If you can't or won't install `uv` — or you hit the macOS Homebrew "externally-managed-environment" error doing `pip install` system-wide — use a venv:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

export ANTHROPIC_API_KEY=sk-ant-...
python agent.py
```

The deps will resolve from `pyproject.toml`. You won't get `uv.lock` reproducibility, but the agent will run.

## Talk to it

The chat UI at [http://localhost:8000](http://localhost:8000) is the easy path. If you want to see the raw `/chat` JSON contract (which the exercises grade against), curl it directly:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "c_demo",
    "user_id": "u_test",
    "message": "Hi, my invoice was $89 but the Pro plan is $79. What gives?"
  }'
```

Other endpoints:
- `GET /health` — readiness probe
- `GET /info` — JSON listing of endpoints (programmatic equivalent of the chat UI's landing page)

You'll get a reply that cites the Analytics add-on. The agent works. Try a few more turns on the same `conversation_id` — it remembers context.

Now try this:

```bash
# 1. Have a multi-turn conversation
curl ...c_keep ... "Hi I need help"
curl ...c_keep ... "What's your refund window?"
curl ...c_keep ... "I'm on Pro+ btw"

# 2. Restart the agent (Ctrl-C, re-run)
# 3. Continue the conversation
curl ...c_keep ... "So based on what I said earlier..."
```

The agent has no idea what you talked about. The dict went away with the process.

## Production-grade gaps (each motivates an exercise)

Read through `agent.py` and find these. They're commented in-line. The `tour/from-demo-to-production` branch frames them as concrete failure modes.

1. **No observability** → `exercise/01-observability`
   - `print()` statements only; no trace IDs, no cost capture, no replay
   - When a customer says "the bot told me wrong info," you cannot reconstruct what happened

2. **In-process conversation state** → `exercise/02-state-and-fallback` (state half)
   - `CONVERSATIONS` dict in `agent.py:33` — lost on restart, single replica only
   - Unbounded growth: the 50-turn conversation will overflow the context window

3. **No retries / fallback / timeouts** → `exercise/02-state-and-fallback` (resilience half)
   - `run_llm()` in `agent.py:75` calls Anthropic with no protection
   - A 429 propagates as a 500 to the user
   - No fallback to a cheaper model on outage; no degraded-mode KB-only template

4. **No confidence signal** → `exercise/03-confidence-calibration`
   - Response shape: `{conversation_id, reply}`. No `confidence`, no `should_escalate`
   - Downstream support team can't tell "send to user" from "human review"

5. **No feedback loop, no eval harness, hardcoded prompt** → `exercise/04-feedback-loops`
   - `SYSTEM_PROMPT` is a string in `agent.py:38`. No version control, no scorecard
   - `eval/golden.jsonl` exists but no command to run it
   - No `POST /feedback` — bad replies vanish into customer dissatisfaction
   - No path from "this reply was bad" → "add to eval set" → "verify the prompt is better"

## What this branch does NOT show you

- How to fix any of the above. (That's the exercises.)
- A path to "production" via shortcuts. (There isn't one.)
- A stack opinion. (You'll bring Langfuse + LangGraph in the exercises; the demo is deliberately library-free so the contrast is clear.)

## Files

```
agent.py                # the entire ~150-line service
kb/                     # 7 markdown docs (reused from forward-deployed-engineering 01)
eval/golden.jsonl       # 12 starter eval entries
pyproject.toml          # minimal deps: fastapi + anthropic + pydantic
```

## Suggested first 60 minutes

1. `python agent.py` and have 3-4 conversations with it. Try edge cases.
2. Read `agent.py` end-to-end. Find the in-line `# Demo-grade:` comments.
3. Open `eval/golden.jsonl`. Run a few entries through the agent manually. Score them in your head.
4. Write down 5 things you'd fix before this can ship to a real customer.
5. Compare your list to `tour/from-demo-to-production`'s framing. They should overlap heavily.

Then go to `exercise/01-observability`.
