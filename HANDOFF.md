# Handoff: Aether AIOS — architecture review, security hardening, and Phase A–E1 implementation

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. This session did the actual implementation work, phase by phase, with live verification at every step — not just planning.

## Status

**Everything through Phase E1 is implemented, tested live, committed, and pushed** (`eb874c7`, up to date with `origin/main`, working tree clean as of this handoff).

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, including a full retrofit of Script/Validation/Metrics onto the Step contract (see "Key decisions" below) — 3 Skills exist: `research_topic`, `file_digest`, `calculate_and_explain`
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output (code, search queries)
- **Phase E1** — the Planner (`services/planning_service.py`), registry-driven capability selection (Tool/Skill/reasoning), wired live into `main.py`

**One real gap, stated plainly**: Ollama was never once running this entire session. Every fallback/offline code path has full live verification. The Planner's *actual* LLM-driven decision path (ask Ollama, parse `skill:research_topic`, execute it) has only been unit-tested against simulated responses — never against a real model. **Run one real end-to-end test with Ollama up before trusting this in daily use.**

Local DB baseline (verified clean as of this handoff): 1 project, 3 memory rows, 25 chats, 0 test rows in `experiences`/`step_metrics`.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.** Storing a Step's logic as a string and `exec()`/`eval()`-ing it would reintroduce the exact vulnerability class Phase A removed. This boundary is stated explicitly in `services/steps/script_meta.py` — don't let a future request to make Scripts "dynamically editable" cross it without the same security scrutiny.
- **Model selection and capability selection are two separate calls**, not one bundled decision. `ARCHITECTURE.md` assigns model selection to the Reasoning Service, not Planning; Phase B's `routing.route()` had blurred them together. Fixed in E1: `services/routing.py` now does model selection only (`select_model()`); `services/planning_service.py` does capability selection only.
- **The Planner's decision prompt is built dynamically from the live registries** (`ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`), not hardcoded capability names. This is the actual substance of "capability registry, not keyword matching" — adding a 4th Tool or Skill makes it selectable automatically.
- **`generate()` vs `generate_strict()`**: `generate()` is for output a human reads directly (chat replies) — a friendly failure string is the correct response. `generate_strict()` (raises `ReasoningError`) is for any automated caller that checks success programmatically (Steps, code-gen feeding a sandbox, query-extraction feeding a search). Getting this backwards caused two real bugs this session (see `STATUS.md`).
- **Skills are deliberately not auto-wired until their Planner exists**, and once E1 landed, all 3 were wired live — this was a staged, verified rollout, not a one-shot integration.
- **`aether.db` is untracked from git** (real user data doesn't belong in version control) but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, real, git-tracked, pushed to `origin/main`)
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key new modules this session: `services/planning_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Run one real request with Ollama actually running** — this is the single highest-priority open item. Confirms the Planner's live LLM decision path, not just its fallback chain.
2. Decide direction for what's next (Prudhvi's call, not predetermined):
   - **E2** (Validator: deterministic + eventually LLM-based validation of a Skill/request's *final* output before delivery — distinct from the per-Step `validate()` that already exists)
   - **E3** (Decision: deliver / retry / escalate, instead of always delivering)
   - Or expand the Tool/Skill set further before adding more Planning-layer sophistication
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) that `Step` now has via `ScriptMeta`. Worth the same treatment once governance (Phase F+) actually needs it.

## Open questions

- Is 3 Skills + 3 Tools "enough" capability variety, or should more be built before layering E2/E3 on top? (This exact question gated E1 earlier in the session — Prudhvi chose to build more Skills first. Same judgment call applies going forward.)
- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.

## Suggested skills

- **`systematic-debugging`** — if the live-Ollama test in Next Steps #1 surfaces unexpected Planner behavior, use this rather than guessing at a fix.
- **`verification-before-completion`** — this entire session ran on a strict "test live, verify against the real DB, don't claim done without proof" discipline. Keep doing that — it caught two real bugs (the `SummarizeStep` memory-corruption bug, the `generate()`/`generate_strict()` success-detection gap) that would otherwise have shipped silently.
- No document-generation or research skills are relevant here — this is pure implementation work in an existing repo via Desktop Commander (local filesystem) and Playwright (verified no local servers running during this session's checks).

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether` and Playwright access to the local browser were both used this session and worked, with occasional connector timeouts (Desktop Commander stalled twice — always re-verified actual file/process state after reconnecting rather than assuming an in-flight edit had landed). If the same happens next session, follow the same pattern: re-read before re-writing, never assume.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8000`. Apply new migrations after pulling with `.venv/bin/alembic upgrade head`.
