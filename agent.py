"""Customer support agent — demo build (Friday-afternoon PoC).

This is the working but production-fragile starting code. Read it, run it,
break it. Don't try to fix it here — the four exercise/ branches harden
it one axis at a time.

Known production-grade gaps (each motivates an exercise/ branch):

1. NO OBSERVABILITY (exercise/01)
   - print() statements only
   - no trace IDs on responses
   - no cost / token / latency capture
   - cannot replay or debug a past conversation

2. IN-PROCESS STATE (exercise/02)
   - CONVERSATIONS dict is a Python dict; lost on restart
   - cannot horizontally scale (replicas don't share state)
   - history grows unbounded; will overflow context window past ~30 turns
   - no retries; no fallback model; LLM 429 propagates to user as 500

3. NO CONFIDENCE SIGNAL (exercise/03)
   - reply has no confidence field
   - downstream support team cannot tell what to trust
   - no escalation policy

4. NO FEEDBACK LOOP (exercise/04)
   - SYSTEM_PROMPT is a hardcoded string in this file
   - eval/golden.jsonl exists but no harness runs it
   - bad replies vanish into customer dissatisfaction
   - no /feedback endpoint
"""
import os
import json
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()
KB_DIR = Path(__file__).parent / "kb"
STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = (STATIC_DIR / "index.html").read_text() if (STATIC_DIR / "index.html").exists() else ""

# ---------- KB load -------------------------------------------------------

KB: dict[str, str] = {}
for f in KB_DIR.glob("*.md"):
    KB[f.name] = f.read_text()

# ---------- "state" -------------------------------------------------------

# Demo-grade: a Python dict. Lost on restart. Doesn't span replicas. Unbounded.
# (exercise/02 replaces this with a LangGraph Postgres checkpointer)
CONVERSATIONS: dict[str, list[dict]] = {}

# ---------- prompt --------------------------------------------------------

# Demo-grade: hardcoded in source. (exercise/04 promotes this to a versioned
# artifact with an eval scorecard attached)
SYSTEM_PROMPT = """You are a tier-1 customer support agent for a B2B SaaS product.

Tone: empathetic, direct, concise. Never reassure beyond what the KB supports.

You have a search_kb tool. Use it BEFORE answering any factual question. Cite the
KB doc you used. If the KB doesn't cover the question, say so plainly and offer
to escalate — do NOT make up policy.

Escalate to a human when: refund > $200, account-security report, GDPR/data
deletion, or repeated unresolved complaint. Do not draft a reply for those — just
explain you're routing them to a human.
"""

# ---------- tool ----------------------------------------------------------


def search_kb(query: str, k: int = 3) -> list[dict]:
    """Naive keyword retrieval. (Real prod would use embeddings; out of scope here.)"""
    q_terms = [t.lower() for t in query.split() if len(t) > 3]
    scored: list[tuple[float, str, str]] = []
    for doc_id, body in KB.items():
        body_low = body.lower()
        score = sum(body_low.count(t) for t in q_terms)
        if score > 0:
            scored.append((score, doc_id, body))
    scored.sort(reverse=True)
    return [{"doc_id": d, "snippet": b[:400]} for _, d, b in scored[:k]]


TOOLS = [
    {
        "name": "search_kb",
        "description": "Search the customer-support knowledge base for relevant docs. Always call this before answering a factual question.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }
]


# ---------- LLM call ------------------------------------------------------

CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = os.environ.get("MODEL", "claude-sonnet-4-5")


def run_llm(history: list[dict]) -> str:
    """Call Claude with the conversation history + system prompt + tool.

    Demo-grade: no retry, no fallback, no timeout. A 429 here propagates a 500.
    (exercise/02 wraps this in a fallback chain with retries.)
    """
    # Loop until the model returns text instead of a tool_use
    msgs = list(history)
    for _step in range(4):  # arbitrary max-tool-call cap
        resp = CLIENT.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=msgs,
        )
        # Did the model emit a tool_use?
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            print(f"[demo-agent] LLM done in {_step + 1} step(s); reply len={sum(len(t) for t in text_blocks)}")
            return "\n".join(text_blocks)
        # Run each tool, append result, loop
        msgs.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            if tu.name == "search_kb":
                hits = search_kb(tu.input["query"])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(hits),
                })
                print(f"[demo-agent] search_kb('{tu.input['query']}') → {len(hits)} hits")
        msgs.append({"role": "user", "content": tool_results})
    return "I'm having trouble getting you an answer right now. Could you rephrase?"


# ---------- HTTP ----------------------------------------------------------


class ChatIn(BaseModel):
    conversation_id: str
    user_id: str
    message: str


@app.get("/", response_class=HTMLResponse)
def index_html():
    """Browser-friendly chat UI. A learner who runs `make run` and opens
    http://localhost:8000 in a browser gets a working chatbot — no curl
    required to verify the agent is up. The HTML+JS+CSS lives at
    static/index.html (~150 lines, no external deps)."""
    if not INDEX_HTML:
        # The static file went missing — degrade gracefully to JSON help.
        return HTMLResponse(
            "<h1>cs-demo-agent</h1><p>static/index.html missing. "
            "Try <code>GET /info</code> or <code>POST /chat</code> directly.</p>",
            status_code=200,
        )
    return HTMLResponse(INDEX_HTML)


@app.get("/info")
def info():
    """Programmatic landing endpoint — the JSON shape the previous demo served at /.
    Kept for scripts and curl-based smoke tests."""
    return {
        "agent": "cs-demo-agent (demo/customer-support-agent)",
        "build": "demo-v1",
        "endpoints": {
            "GET /": "browser chat UI (HTML)",
            "GET /info": "this payload",
            "GET /health": "readiness probe",
            "POST /chat": "send a customer message; receive a reply",
        },
        "try": (
            "curl -X POST http://localhost:8000/chat "
            "-H 'Content-Type: application/json' "
            "-d '{\"conversation_id\":\"c1\",\"user_id\":\"u1\","
            "\"message\":\"What does the Analytics addon cost?\"}'"
        ),
        "kb_docs_loaded": len(KB),
        "modules_active": [],
    }


@app.get("/health")
def health():
    return {"ok": True, "build": "demo-v1", "model": MODEL, "modules_active": []}


@app.post("/chat")
def chat(body: ChatIn):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(500, detail="ANTHROPIC_API_KEY not set")
    history = CONVERSATIONS.setdefault(body.conversation_id, [])
    history.append({"role": "user", "content": body.message})
    print(f"[demo-agent] conv={body.conversation_id} user={body.user_id} turn={len(history)}")
    try:
        reply_text = run_llm(history)
    except anthropic.APIError as e:
        # Demo-grade: a 429 / 5xx from upstream propagates to the user.
        print(f"[demo-agent] LLM error: {e}")
        raise HTTPException(500, detail=f"LLM error: {type(e).__name__}")
    history.append({"role": "assistant", "content": reply_text})
    return {
        "conversation_id": body.conversation_id,
        "reply": reply_text,
        # Demo-grade: no citations, no confidence, no trace_id, no token counts.
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
