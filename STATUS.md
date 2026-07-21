# Aether — Current Status

_Last updated: July 21, 2026, after completing Phase A–D, E0, closing the Step contract's Script/Validation/Metrics gap, and building E1 (the Planner). Update this file whenever a Critical/Important item is resolved or a new one is found._

**Continuing in a new session? Read `HANDOFF.md` first — it's the compact version of everything below.**

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete. E0 + E1 complete.** A real registry-driven Planner now decides Tool vs. Skill vs. reasoning for every `/chat` request. |
| Commits | Everything through E1 committed and pushed (`eb874c7`, up to date with `origin/main`, working tree clean). |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration and test run this session |
| Critical blockers | 0 |
| Next phase | E2 (Validator) / E3 (Decision), or expand the Skill set further first — Prudhvi's call |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.

## Resolved — Phases A–D, E0, Step contract gap

See git history of this file for full details (commits `e4720c2`, `57f3dd1`, `c299fbf`, `d9a8599`). Summary: pooled DB, sandboxed code execution, allowlisted file access, unified routing, upserted memory, formal Tool contract + registry, single Reasoning Service entry point, Experience log, Step/Skill abstraction with real `Script`/`Validation`/`Metrics` (`ScriptMeta`, `Step.validate()`, `step_metrics` table), `generate_strict()` fix applied to the code-gen/web-query paths.

## Resolved — E1: the Planner (committed as `eb874c7`)

Prudhvi asked for the architecture built "however you think is perfect" — this is the natural next piece now that 3 structurally distinct Skills exist (satisfying Phase E's own stated precondition).

1. **`services/planning_service.py`** — `plan(prompt, project_id) -> Plan`. The core design point, and what makes this a genuine improvement over the old `ai_decide_plugin()`: the LLM decision prompt is built **dynamically from `ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`**, not a hardcoded 3-option string. Adding a 4th Tool or Skill makes it selectable automatically — nothing in `planning_service.py` needs to change. This is literally what `ROADMAP.md`'s E1 meant by "based on a capability registry, not keyword matching."
2. **Graceful degradation chain**: registry-driven LLM decision → (if Ollama down) the old rule-based `decide_plugin()` as an offline fallback, Tool-only → (if that also finds nothing) raw reasoning. Verified live: with Ollama down, `9*9` still hit the free rule-based math path (no LLM call at all), and `"hello how are you"` correctly fell through the whole chain to `reasoning` with `source: "fallback"`.
3. **Model selection split out from capability selection**, correcting a real inconsistency from Phase B: `ARCHITECTURE.md` assigns "Model selection" to the *Reasoning* Service, not Planning, but Phase B's `routing.route()` bundled both into one call. `services/routing.py` now does model selection only (`select_model()`); `planning_service.py` does capability selection only. Two independent decisions, not one blurred one — `main.py` calls both explicitly.
4. **`services/extraction.py`** — pulled the query/filename/code-generation extraction logic out of `plugin_manager.py` into shared helpers, since the Planner needs the exact same extraction for building Skill input that `execute_plugin()` already did for Tool input. No prompt duplicated across two files.
5. **`main.py` rewritten** to call `plan()` then `execute_plan()` instead of the old `routing.route()` + `execute_plugin()` pair. `request_id` is now fetched at the top of the handler (via structlog contextvars) instead of after response generation, so it can be threaded into `Skill.run()` for step-metrics logging.

**A second real bug was found and fixed while verifying this**, not introduced by E1 but exposed by re-reading old E0-era `experiences` rows: the *old* success-detection heuristic in `main.py` didn't include `"Could not generate code"` as a failure prefix (that message didn't exist yet when the heuristic was first written), so an E0 test got logged as `success: true` despite genuinely failing. Fixed in the new `main.py`'s heuristic, which now also includes `"Couldn't complete this"` (the new Skill-failure message format).

**A connector outage happened mid-verification** (Desktop Commander stalled on 3 consecutive calls, including a trivial `get_config`). One edit (a missing `plan_decided` log line for the rule-based math path) was confirmed NOT to have landed by re-reading the file after reconnecting, rather than assumed either way — then reapplied and re-verified from a clean server restart.

**Verified live, full clean run after reconnecting, Ollama still down throughout**:
- `9*9` → rule-based math path, `plan_decided` logged correctly, `experiences` row shows `tool: code, tool_source: rule, success: 1`
- `"hello how are you"` → falls through the full chain to reasoning, `experiences` row shows `tool: null, tool_source: fallback, success: 0` (honestly reflecting Ollama being down)
- Existing project data (`GET /projects`) still reads correctly through the new `main.py`
- DB confirmed clean before and after: 3 memory rows, 25 chats, throughout

## What's already right — keep these

- **Registry-driven decision prompt** — this is the actual architectural upgrade E1 was supposed to deliver. Resist ever hardcoding tool/skill names back into a decision prompt; if a 4th capability needs special-casing in `planning_service.py`, something's wrong with that capability's `description`, not with the Planner.
- **Model selection vs. capability selection as two separate calls** — matches `ARCHITECTURE.md`'s actual service boundaries. Don't re-merge them for convenience.
- **Graceful multi-layer fallback (LLM → rule → reasoning)** — the system stays usable with the model provider fully down, proven repeatedly this session since Ollama was never once available.

## Known gaps, unchanged from before

- `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) the way `Step` now has via `ScriptMeta`. Not urgent until governance (Phase F+) needs it.
- The Planner's LLM decision path itself has never been tested against a live Ollama response this entire session — only its fallback chain has real end-to-end verification. `_parse_decision()` and `_build_decision_prompt()` were unit-tested directly (proven correct against simulated inputs), but the full "ask Ollama, get back `skill:research_topic`, execute it" path is unverified against a real model. **Worth running once Ollama is available**, before trusting this in daily use.

## Immediate next action

Run one real end-to-end test with Ollama actually up, to close the one remaining unverified path (the live LLM decision, not just its fallback). Then decide: E2/E3 next, or expand the Skill/Tool set further first. See `HANDOFF.md` for the full session-transition brief.
