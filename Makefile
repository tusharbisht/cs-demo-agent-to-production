.PHONY: setup run smoke clean

# uv-first ergonomics. `make setup` is idempotent — safe to re-run.
# Falls back gracefully to a hint if uv isn't installed.

setup:
	@command -v uv >/dev/null 2>&1 || { \
	  echo "uv not found. Install it:"; \
	  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
	  echo "  (or: brew install uv)"; \
	  echo ""; \
	  echo "Or use the stdlib path:"; \
	  echo "  python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ."; \
	  exit 1; \
	}
	uv sync
	@echo ""
	@echo "Setup complete. Next:"
	@echo "  export ANTHROPIC_API_KEY=sk-ant-..."
	@echo "  make run"

run:
	@test -n "$$ANTHROPIC_API_KEY" || { echo "ERROR: ANTHROPIC_API_KEY not set in env"; exit 1; }
	uv run python agent.py

# Smoke test: spin up the agent in the background, hit /health and /chat once,
# print results, tear down. Useful for verifying setup without manual curl.
smoke:
	@test -n "$$ANTHROPIC_API_KEY" || { echo "ERROR: ANTHROPIC_API_KEY not set"; exit 1; }
	@uv run python agent.py & \
	  PID=$$!; \
	  sleep 3; \
	  echo "--- /health ---"; \
	  curl -s http://localhost:8000/health | python3 -m json.tool || true; \
	  echo "--- /chat ---"; \
	  curl -s -X POST http://localhost:8000/chat \
	    -H "Content-Type: application/json" \
	    -d '{"conversation_id":"smoke","user_id":"u_smoke","message":"What does the Analytics addon cost?"}' \
	    | python3 -m json.tool || true; \
	  kill $$PID 2>/dev/null; \
	  wait $$PID 2>/dev/null || true

clean:
	rm -rf .venv __pycache__ *.egg-info
