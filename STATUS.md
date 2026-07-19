# Aether — Current Status

_Last updated: July 19, 2026, after completing Phase A and Phase B. Update this file whenever a Critical/Important item is resolved or a new one is found._

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + Phase B complete.** Security/correctness fixed, routing unified, memory upserts, migrations tracked. |
| Commits | Phase A committed and pushed (`e4720c2`). Phase B changes below not yet committed. |
| Local usage | 1 project, 3 memory rows, 25 chats — all verified intact through both phases' migrations |
| Critical blockers | 0 |
| Important issues open | 0 (all 5 from Phase A/B resolved) |
| Next phase | `ROADMAP.md` → Phase C (Tool Service formalization) |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```

New dependencies live in `backend/.venv` (SQLAlchemy, Alembic, structlog), not system Python. Recreate with:
```bash
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn pydantic requests sqlalchemy alembic structlog
```

Code execution requires `bwrap` (present on this machine). File-reading is scoped to `~/aether-workspace/`.

To apply new migrations after pulling changes: `.venv/bin/alembic upgrade head`.

## Resolved — Phase A (Security & Correctness) — committed as `e4720c2`

1. ✅ Global SQLite singleton → pooled SQLAlchemy engine
2. ✅ `eval()` → AST-based safe math evaluator
3. ✅ Bypassable sandbox → `bwrap` isolation (no network, read-only fs, resource limits)
4. ✅ Arbitrary file read → allowlisted `~/aether-workspace/`
5. ✅ No migrations → Alembic, stamped at baseline, zero data loss
6. ✅ Silent failures → `structlog` + request-ID middleware

## Resolved — Phase B (Architecture Cleanup) — not yet committed

1. ✅ **Routing unified** — new `services/routing.py` replaces the two disconnected systems (`router.py`'s model selection + `plugin_manager.py`'s always-on LLM tool decision). One `route(prompt, mode)` call now returns `{model, tool, tool_source}`. It tries the free rule-based `decide_plugin()` first and only falls back to an LLM call when the rules don't match — verified live: `"search python news"` was routed with `tool_source: "rule"`, meaning zero extra Ollama calls were spent deciding to use the web tool.
2. ✅ **Memory extraction is now LLM-based** — `services/memory_extraction.py` asks the model for structured `{key: value}` facts instead of string-matching fixed phrases like "i like"/"i prefer". Falls back to `{}` (no facts) on any parse failure rather than raising.
3. ✅ **Memory upserts** — added a `UniqueConstraint("project_id", "key")` to `Memory` via Alembic migration `f33fab44be66` (SQLite batch-mode table rebuild; existing 3 rows verified intact after). `save_memory()` now uses `INSERT ... ON CONFLICT DO UPDATE`. Verified live: saving `name` twice with different values leaves exactly one row with the latest value, not two.
4. ✅ **Frontend duplicate call removed** — `fetchProjects()` was called twice in `createProject()` in `App.js`; now called once.
5. ✅ **Bare `except:` blocks** — none remain; Phase A's `structlog`-based error handling already covered the modules touched here (`ollama_service.py`, `project_store.py`).

## Important (Phase C candidates — see ROADMAP.md)

None outstanding from Phase A/B. Next real gaps are architectural, not bugs:
- No formal Tool contract (input/output schema) — plugins are still ad hoc functions
- No model-provider abstraction — `ollama_service.py` is still the only path to an LLM, hardcoded
- No Experience log — executions aren't recorded anywhere for future learning

## What's already right — keep these

- **`services/routing.py`** is now the single source of truth for "what should handle this request" — this is the natural seam where a future Planning Service will attach.
- **`project_id` as a first-class entity** — correct precursor to Project Brain.
- **Upsert-based memory** — correct precursor to a real Memory Service; the (project_id, key) constraint is the right primitive to build typed facts on top of later.

## Immediate next action

Review and commit the Phase B changes, then start `ROADMAP.md` → Phase C.
