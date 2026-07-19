# Aether — Current Status

_Last updated: July 19, 2026, after completing Phase A, B, and C. Update this file whenever a Critical/Important item is resolved or a new one is found._

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C complete.** Security fixed, routing unified, memory upserts, formal Tool contract + registry, single Reasoning Service entry point, Experience log. |
| Commits | Phase A (`e4720c2`) and Phase B (`57f3dd1`) committed and pushed. Phase C changes below not yet committed. |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration across all 3 phases |
| Critical blockers | 0 |
| Next phase | `ROADMAP.md` → Phase D (Skill/Step abstraction) |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.

## Resolved — Phase A (Security & Correctness) — committed `e4720c2`

Pooled SQLAlchemy engine, safe math eval (no `eval()`), `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, `structlog` + request IDs. See prior status entries for verification details (preserved in git history of this file).

## Resolved — Phase B (Architecture Cleanup) — committed `57f3dd1`

Unified routing (`services/routing.py`), LLM-based memory extraction, memory upserts via unique constraint + `ON CONFLICT`, frontend duplicate-call fix.

## Resolved — Phase C (Tool Service Formalization) — not yet committed

1. ✅ **Tool contract** — `services/tools/base.py` defines `Tool` (name, description, `InputModel`, `execute()`) and `ToolResult`. Input schemas are real JSON Schema via pydantic's `model_json_schema()` — verified `registry.describe_all()` produces a schema a future Planning Service could consume directly.
2. ✅ **Tools refactored to be deterministic-only** — per `ARCHITECTURE.md`'s "Tools never perform reasoning": `file_reader.read_file()` and `web_search.web_search()` now take already-structured input (a filename, a clean query) instead of parsing natural language themselves. That parsing moved to `plugin_manager.py`, which is where the reasoning steps belong. `CodeTool`, `FileTool`, `WebTool` in `services/tools/` wrap the three plugins.
3. ✅ **`ToolRegistry`** (`services/tools/registry.py`) — tools are registered once at import time; `plugin_manager.py` now dispatches through `registry.get(name)` instead of an if/elif chain. Adding a 4th tool means writing one class and one `.register()` call.
4. ✅ **Reasoning Service entry point** — `services/reasoning_service.py` is now the only module that imports `ollama_service` directly. `plugin_manager.py`, `memory_extraction.py`, and `main.py` all call `reasoning_service.generate()`. Adding a second model provider later means changing this one file.
5. ✅ **Experience log** — new `experiences` table (Alembic `3d051fbf7d64`, purely additive) records `{project_id, request_id, prompt, tool, tool_source, model, success, latency_ms, timestamp}` for every `/chat` call. Verified live: a `9*9` request produced a matching row with the same `request_id` as its structured logs, `tool_source: "rule"`, `success: true`, sub-millisecond latency.

Verified end-to-end: the full deterministic path (rule-routed math → `CodeTool` → `safe_eval_math`) works with zero LLM calls and zero network access, exactly as before the refactor — the Tool contract changes didn't regress any Phase A protections (traversal blocking, sandboxing all re-verified against the new `Tool.execute()` interface).

## Known gap (not introduced by Phase C, just made visible by it)

When Ollama is unreachable, `execute_plugin`'s code-gen path (LLM writes code → `CodeTool` runs it) doesn't check whether the LLM call itself failed before feeding the result into the sandbox as "code" — it fails safely (a Python `SyntaxError` inside the sandbox, not a security issue) but isn't a clean error message. Worth a small fix in Phase D.

## What's already right — keep these

- **`services/tools/`** — the Tool contract is the correct foundation for Phase D's Skill abstraction (a Skill will be a sequence of Tool calls sharing context).
- **`services/reasoning_service.py`** — correct single seam for model independence.
- **`experiences` table** — correct foundation for a real Evolution Service later (Phase F+), once there's enough volume to learn from.

## Immediate next action

Review and commit the Phase C changes, then start `ROADMAP.md` → Phase D.
