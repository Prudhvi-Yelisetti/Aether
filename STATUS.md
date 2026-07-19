# Aether — Current Status

_Last updated: July 19, 2026, after completing Phase A. Update this file whenever a Critical/Important item is resolved or a new one is found._

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A complete.** All 4 Critical issues fixed and verified. Phase 2–3 functionality preserved, now on a safe foundation. |
| Commits | 3 on disk (not yet committed: the Phase A changes below) |
| Local usage | 1 project, 25 chats intact — verified byte-identical count before/after the SQLAlchemy migration |
| Critical blockers | **0** — see "Resolved" section below |
| Next phase | `ROADMAP.md` → Phase B (routing unification, memory upsert) |

## How to run it now

The backend has new dependencies (SQLAlchemy, Alembic, structlog) installed in a dedicated venv rather than system Python:

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```

If you ever need to recreate the venv:
```bash
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn pydantic requests sqlalchemy alembic structlog
```

Code execution requires `bwrap` (bubblewrap) on the host — already present on this machine. If missing: `sudo pacman -S bubblewrap`.

File-reading is now scoped to `~/aether-workspace/` (created automatically). Files elsewhere are refused.

## Resolved — Phase A (Security & Correctness)

All verified working together via a live end-to-end test (uvicorn + curl), not just unit-tested in isolation.

1. ✅ **Global SQLite singleton** → `db/database.py` now uses a pooled SQLAlchemy engine (`pool_size=10, max_overflow=20`); every call in `storage/project_store.py` opens/closes its own session. Verified: pre-existing 25 chats read back correctly after the swap.
2. ✅ **`eval()` on user input** → replaced with `safe_eval_math()` in `plugin_manager.py`, an AST walker that only accepts numeric literals and `+ - * /`. Anything else raises and falls through to the LLM path.
3. ✅ **Code sandbox bypassable** → `code_runner.py` now runs all generated code inside `bwrap` with `--unshare-all` (no network, no PID/IPC visibility), a read-only root filesystem, and `ulimit`-enforced CPU/memory/process caps. Verified live: outbound socket connection fails with "Network is unreachable"; write to `/etc/passwd` fails with "No such file or directory" (the path isn't even visible); an infinite loop is killed at the 5s timeout.
4. ✅ **Arbitrary file read** → `file_reader.py` now resolves every candidate path against an allowlisted `~/aether-workspace/` directory using `pathlib`, rejecting anything that resolves outside it. Verified: `../../../etc/passwd` is refused; a real file inside the workspace reads correctly.

Also folded into this pass (originally slated for Phase B, moved up because they were touched by the same files):

5. ✅ **Alembic migrations** — initialized and stamped at a baseline revision matching the pre-existing schema exactly (no destructive ALTERs run against your live data). Future schema changes are real migrations from here on.
6. ✅ **Structured logging** — `structlog` + a request-ID middleware in `main.py`. Every request gets a short ID threaded through routing, plugin execution, and the Ollama call, so one failing request can be traced end-to-end in the logs instead of vanishing into a bare `except`. Verified live: a single `request_id` appeared on 5 log lines spanning the full `/chat` call, including two `ollama_unreachable` errors that previously would have been silent.

## Important (Phase B — not yet started)

- Memory extraction is still string-matching (`extract_memory` in `main.py`) — low recall, writes unbounded duplicate rows, no upsert. The ORM model (`db/orm_models.py`) has a comment marking where the upsert constraint should go once this lands.
- Two disconnected routing systems: `router.py` (model selection) and `plugin_manager.py` (`decide_plugin` vs `ai_decide_plugin`) don't share state. `decide_plugin` is imported in `main.py` but never called.
- Every chat request still costs 2+ sequential Ollama calls minimum (routing decision, then generation).
- Frontend: `fetchProjects()` called twice in `createProject()` in `App.js` — not yet fixed.

## What's already right — keep these

- **Plugin architecture** (`ai_decide_plugin` → `execute_plugin`) is the correct embryo of a Tool Service — now also the correct embryo of a *safe* Tool Service.
- **`project_id` as a first-class entity** — correct precursor to Project Brain.
- **`router.py` as an isolated concern** — routing strategy can evolve independently of the LLM wrapper (still needs unifying with plugin routing in Phase B).

## Immediate next action

Commit the Phase A changes, then start `ROADMAP.md` → Phase B.
