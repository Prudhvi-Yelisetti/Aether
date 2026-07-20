# Aether — Current Status

_Last updated: July 20, 2026, after completing Phase A, B, C, D, and building out Skills toward Phase E1. Update this file whenever a Critical/Important item is resolved or a new one is found._

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete. E0 complete.** 3 real Skills now exist (building toward E1's precondition). |
| Commits | Phase A (`e4720c2`), B (`57f3dd1`), C (`c299fbf`), D (`d9a8599`) committed and pushed. E0 + the new Skills below not yet committed. |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration and every test run across all phases |
| Critical blockers | 0 |
| Next phase | Once E1 is unblocked (see below), build the Planner |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.

## Resolved — Phases A–D

See git history of this file (or the commits themselves: `e4720c2`, `57f3dd1`, `c299fbf`, `d9a8599`) for full details. Summary: pooled DB, sandboxed code execution, allowlisted file access, unified routing, upserted memory, formal Tool contract + registry, single Reasoning Service entry point, Experience log, Step/Skill abstraction.

## Resolved — E0 (carried over from C/D) — not yet committed

`execute_plugin`'s code-gen path and web query-extraction now use `generate_strict()` instead of `generate()`. Verified live with Ollama down: code-gen returns `"Could not generate code: ..."` instead of feeding the failure string into the sandbox; web search falls back to the raw prompt instead of searching for the literal error text.

## In progress — preparing for E1 — not yet committed

`ROADMAP.md`'s Phase E header requires "enough Skills/Steps that a linear if/else chain genuinely can't route between them anymore" before building a Planner. That wasn't true with only `ResearchTopicSkill` existing (Phase D's single proof-of-concept, unwired). Prudhvi chose to build more Skills first rather than build the Planner against one example. Two more Skills now exist:

1. **`FileDigestSkill`** (`services/skills/file_digest_skill.py`) — `filename` → read file (Tool) → summarize (reasoning) → save to memory (Tool). **Reuses the exact same `SummarizeStep` and `SaveMemoryStep` classes as `ResearchTopicSkill`** — only the predecessor step and the context keys passed in differ. No new "explain a file" implementation was written.
2. **`CalculateAndExplainSkill`** (`services/skills/calculate_and_explain_skill.py`) — `code` → run it (Tool) → explain the result (reasoning). Deliberately a different shape: 2 steps not 3, doesn't touch memory at all. Also reuses `SummarizeStep`.

**A real design gap was found and fixed while building these**, not just two more clean Skills: `SummarizeStep` and `SaveMemoryStep` originally hardcoded which context key they read from (`"web_search"`, `"summarize"`) — meaning they looked reusable but weren't actually reusable by a second Skill without duplicating them. Fixed by making both take a configurable `source_key` (and `SaveMemoryStep`, a configurable `memory_key`) via their constructors. `ResearchTopicSkill` was updated to pass these explicitly (`source_key="web_search"`, etc.) rather than relying on the old implicit defaults, so the reuse is visible in the code, not hidden behind default-parameter coincidence.

Two new deterministic Steps were also added to support this: `ReadFileStep` (wraps the `file` Tool) and `RunCodeStep` (wraps the `code` Tool) — both trivial wrappers, same pattern as `WebSearchStep`.

Added `services/skills/registry.py` (`SkillRegistry`, mirroring `ToolRegistry`) — **not** the Planner itself, just makes "what Skills exist" queryable the way Tools already are. `registry.describe_all()` returns all 3 Skills with their step sequences.

**Verified live** (Ollama still down throughout, same as every prior verification this session):
- All 3 Skills registered and correctly described via `SkillRegistry.describe_all()`
- `CalculateAndExplainSkill`: `RunCodeStep` correctly computed `sum(range(1,101)) = 5050` deterministically; `SummarizeStep` (reused, different `source_key`) correctly fail-gated with Ollama down
- `FileDigestSkill`: legitimate file reads work; **Phase A's path-traversal protection still holds** through this new Skill (`../../../etc/passwd` correctly blocked at the `read_file` step)
- No test data reached the real `memory` table in any failed run — confirmed via direct DB query (still exactly 3 original rows)

## E1 status: still gated, now on a real decision

3 Skills with genuinely different shapes (3-step w/ memory, 3-step w/ memory but different source, 2-step w/o memory) now exist. This is a reasonable amount of variety for a Planner to discriminate between — Prudhvi should decide whether this is "enough" or whether to build further before starting E1.

## What's already right — keep these

- **Configurable Step constructors (`source_key`, `memory_key`)** — this is the actual mechanism that makes Step reuse real rather than aspirational. Any new Step should default to this pattern.
- **`services/skills/registry.py`** — correct minimal scaffolding for E1; resist the urge to add selection logic here, that's the Planner's job specifically.
- **3 genuinely distinct Skill shapes** — better Planner-design input than 3 skills that all happen to look the same.

## Immediate next action

Review and commit the E0 fix + new Skills, then decide on E1 (build the Planner now, or keep expanding the Skill set first).
