# Aether

A local-first open-source AI workspace with smart model routing.

## Features (MVP)
- Chat interface
- Project-based organization
- Local AI via Ollama
- Basic model routing

## Tech Stack
- Frontend: React (planned)
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
