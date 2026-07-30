# Aether

A local-first open-source AI workspace with smart model routing and a visible
Plan → Capability → Validate → Deliver pipeline for every response.

## Features (MVP)
- Chat interface with project-based organization and per-project memory
- Local AI via Ollama, with automatic model routing
- A Planner that picks between Tools (single-step actions), Skills
  (multi-step sequences), or raw reasoning — registry-driven, not keyword
  matching, so new capabilities are automatically selectable
- 5 Tools (code execution, file read/write/list, web search) and 5 Skills
  (research + save, file digest, fuzzy file lookup, calculate + explain)
- Validation and bounded retry/escalation before a response is ever
  delivered — no internal error strings leak to the user
- The UI shows which capability actually handled each response (e.g.
  `plan·llm → skill:research_and_save_file → qwen3.5:9b → ok`), plus a
  Capabilities panel listing everything Aether can currently do

## Tech Stack
- Frontend: React
- Backend: FastAPI
- Models: Ollama

## Running locally

```bash
./run.sh
```

Starts Ollama (if it isn't already running), the backend, and the frontend
dev server together, with output printed to the terminal. Press Ctrl+C to
stop everything the script started. See the comments at the top of
`run.sh` for the details it handles automatically (port conflicts, first-run
`npm install`, etc.).

## Vision

Aether's long-term goal is an AI Operating System (AIOS): a kernel of reusable
intelligence services (Planning, Tools, Skills, Memory, Governance, ...) that
any agent or model can use, instead of intelligence living inside one agent.

- **`ARCHITECTURE.md`** — the target AIOS design, mapped against what exists in this repo today, service by service
- **`STATUS.md`** — current state, what's working, what's broken, critical blockers
- **`ROADMAP.md`** — the phased plan to close the gap, in dependency order

Read `STATUS.md` first if you're picking this project back up after a break.
