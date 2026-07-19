# Aether — Current Status

_Last updated: July 19, 2026, after completing Phase A, B, C, and D. Update this file whenever a Critical/Important item is resolved or a new one is found._

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete.** Security fixed, routing unified, memory upserts, formal Tool contract, Reasoning Service, Experience log, and now a real Step/Skill abstraction. |
| Commits | Phase A (`e4720c2`), B (`57f3dd1`), C (`c299fbf`) committed and pushed. Phase D changes below not yet committed. |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration across all 4 phases |
| Critical blockers | 0 |
| Next phase | `ROADMAP.md` → Phase E (Planning, Validation, Decision) |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.

## Resolved — Phase A (Security & Correctness) — committed `e4720c2`

Pooled SQLAlchemy engine, safe math eval (no `eval()`), `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, `structlog` + request IDs.

## Resolved — Phase B (Architecture Cleanup) — committed `57f3dd1`

Unified routing (`services/routing.py`), LLM-based memory extraction, memory upserts via unique constraint + `ON CONFLICT`, frontend duplicate-call fix.

## Resolved — Phase C (Tool Service Formalization) — committed `c299fbf`

Tool contract (`services/tools/base.py`), 3 tools refactored to be deterministic-only, `ToolRegistry`, single Reasoning Service entry point, `experiences` table.

## Resolved — Phase D (Skill & Step Abstraction) — not yet committed

1. ✅ **Step contract** — `services/steps/base.py` defines `Step` (name, description, `run(context)`) and `StepResult`. Unlike a Tool, a Step is allowed to call the Reasoning Service — documented explicitly as the one place the "tools never reason" rule doesn't apply, and why.
2. ✅ **Skill contract** — `services/skills/base.py` defines `Skill` as an ordered list of Steps sharing one context dict. `Skill.run()` stops immediately if any Step fails (the minimal validation gate for this phase — a real Validator Service is Phase E).
3. ✅ **`ResearchTopicSkill`** (`services/skills/research_topic_skill.py`) — composes `WebSearchStep` (deterministic, wraps the `web` Tool) → `SummarizeStep` (reasoning) → `SaveMemoryStep` (deterministic, wraps `save_memory`). Deliberately **not wired into the live `/chat` path** — deciding when to invoke a Skill vs. a Tool vs. raw reasoning is a Planning Service's job (Phase E); wiring it in now would mean guessing at Planning Service behavior ahead of building it.

**A real bug was found and fixed while testing this phase**, not just a clean success story: `SummarizeStep` initially used the graceful `reasoning_service.generate()` (which turns Ollama failures into a friendly string rather than raising, correct for chat UX) — so when Ollama was down, the Step reported `success: True` with `"Could not reach Ollama..."` as if it were a real summary, and `SaveMemoryStep` actually wrote that string into memory as `last_research`. Fixed by adding `reasoning_service.generate_strict()`, which raises `ReasoningError` on the same failure cases instead of returning a string — used by `SummarizeStep` specifically because its result is checked programmatically, not read by a human. Re-verified: the Skill now stops at `summarize` with `success: False` when Ollama is down, and never reaches `save_memory`. The corrupted test row was found in the live `memory` table and deleted; your 3 original rows are untouched.

**This is worth remembering for Phase E and beyond**: any automated caller that checks a result's success/failure programmatically must use `generate_strict()`, not `generate()`. `generate()` is only safe for paths where a human reads the output directly (the main chat response).

## Known gap (from Phase C, not yet fixed)

`execute_plugin`'s code-gen path (LLM writes code → `CodeTool` runs it) still uses the graceful `generate()`, so if the LLM call fails, the failure string gets fed into the sandbox as if it were code — same class of bug as the one just fixed in `SummarizeStep`, just not yet applied here. Fails safely (a `SyntaxError` inside the sandbox) but should switch to `generate_strict()` too. Small, low-risk fix — good Phase E starter item.

## What's already right — keep these

- **`services/steps/` + `services/skills/`** — the abstraction is proven with a real multi-step composition, not just a contract on paper.
- **`generate()` vs `generate_strict()`** — a genuinely useful distinction that emerged from a real bug, not speculative design. Any future Step, Workflow, or Evolution proposal-checker should default to the strict variant.
- **`experiences` table** — still the correct foundation for a real Evolution Service later.

## Immediate next action

Review and commit the Phase D changes (including the `generate_strict()` fix), then start `ROADMAP.md` → Phase E. Consider applying the same `generate_strict()` fix to the Phase C code-gen path first, since it's now a known, understood, and cheap fix.
