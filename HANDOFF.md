# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented; E2 and E3 are each fully complete.** A 4th Tool (`write_file`) and 4th Skill (`research_and_save_file`) were added on top, both live-verified.

**Push status, precisely** (this session never got working SSH access to `origin`):
- `ebf40a3`, `62002a9` — confirmed pushed by Prudhvi
- `5196af7` (E3 backoff), `8e65c28` (E2 completion), `1880557` (deleted dead `services/router.py`) — committed locally, **push not confirmed**
- The Tool/Skill expansion — **not yet committed at all**, see "Uncommitted changes" below

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, full retrofit of Script/Validation/Metrics onto the Step contract
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output (code, search queries)
- **Phase E1** — the Planner (`services/planning_service.py`), registry-driven capability selection, live-LLM path verified (fast, reliable — see below)
- **Phase E2** — complete, both increments: deterministic failure-string check + opt-in/observability-only LLM-based validation
- **Phase E3** — complete, bounded retry (with backoff) + escalate

**Capability inventory as of this handoff**: 4 Tools (`code`, `file`, `web`, `write_file`), 4 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`).

## This session's findings, in order

1. **Model-name bug.** Every LLM call site hardcoded model names (`llama3`, `mistral`) that don't exist on this machine (only `qwen3.5:9b` and `qwen3-coder:latest` are pulled) — the live-LLM decision path had been silently, instantly failing over to fallback the whole time. Fixed across 7 files.

2. **Latency variance, root cause found.** `qwen3.5:9b` is a hybrid thinking model and the Ollama payload never set `think`, so every call ran an unbounded hidden reasoning trace even for one-line classification prompts. A/B proof: 30.9s with `think` unset vs 0.8s with `think=False`, same correct output. Fixed via `think: bool = False`.

3. **E2 (Validator), first check.** `main.py` computed a failure-string `success` flag for logging but never used it to protect the delivered response. Built `services/validation_service.py` as a single source of truth (was duplicated, slightly differently, in two places).

4. **E3 (Decision), first pass.** `validate_response()` now classifies each failure as `retryable` or not. New `services/decision_service.py`: one attempt, validate, retry once if retryable, escalate otherwise.

5. **E3 follow-up: retry backoff, with a self-caught correction.** Added a 2s delay before retrying. First live verification attempt *overclaimed* a result — a real successful recovery, but the request's own log showed no retry had actually fired; the fix worked for an unrelated reason (lucky timing). Caught by checking the log against the claim, corrected with a deterministic test instead (`decide()` called directly with a fake attempt that fails once then succeeds — confirmed exactly 2 attempts and a measured 2.0s gap).

6. **E2 completed: LLM-based validation, opt-in and observability-only.** `validate_response_llm()` asks a model whether the response addresses the prompt. Deliberately not wired to gate delivery — off by default, logs only. Live-verified three cases: good answer (accepted), deliberately off-topic answer (flagged), judge itself unavailable (fails open, doesn't penalize the response).

7. **`services/router.py` deleted.** Dead, zero-caller file with the original model-name bug, flagged for deletion across several updates. Re-confirmed zero references, no test suite to break, deleted, re-verified live.

8. **Tool/Skill expansion.** Added `WriteFileTool`/`write_file` (a real gap — Aether could only read files before, never write one) and `ResearchAndSaveFileSkill`, which composes the *existing* `WebSearchStep`+`SummarizeStep` with the new `WriteFileStep` — genuine reuse, not duplication. Live-verified through the actual `/chat` endpoint, twice: the Planner correctly selected the new Skill (`source: llm`) from plain natural language with zero hardcoding needed. Full pipeline (all 3 steps, real file written and read back) proven in isolation. Security boundaries (path traversal, oversized content) hold, matching the existing read tool. **Found, not fixed, a pre-existing bug along the way**: `web_search.py` calls DuckDuckGo's narrow Instant Answer API, and `extract_search_query()`'s LLM-extracted phrasing often doesn't match it even when a raw string would (`"the Great Wall of China"` works; `"Great Wall of China research"` doesn't). This affects the *original* `research_topic` Skill identically — not introduced by this session's work, and out of scope for a Tool/Skill expansion task.

Full detail, including every `experiences` table row and every live test across the whole session, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

Confirmed pushed to `origin/main`: `ebf40a3`, `62002a9`.

Committed locally, **push not yet confirmed** (no working SSH access this session):
- `5196af7` — E3's retry backoff
- `8e65c28` — E2's LLM-based validation
- `1880557` — deletion of dead `services/router.py`

**Not yet committed at all** — the Tool/Skill expansion:
- `plugins/file_writer.py` (new), `services/tools/write_file_tool.py` (new), `services/tools/registry.py` (registered)
- `services/steps/write_file_step.py` (new)
- `services/extraction.py` — new `slugify_filename()` helper
- `services/skills/research_and_save_file_skill.py` (new), `services/skills/registry.py` (registered, plus a stale-docstring fix)
- `services/planning_service.py` — `_build_skill_input()` now has a `research_and_save_file` branch
- `STATUS.md`, `ROADMAP.md`, this file — updated with all of the above

Local DB baseline (verified clean throughout): 1 project, 3 memory rows, 25 chats unchanged across every test this session and every prior one.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.** Don't cross this boundary without the same security scrutiny Phase A required.
- **Model selection and capability selection are two separate calls.** `services/routing.py` does model selection only; `services/planning_service.py` does capability selection only.
- **The Planner's decision prompt is built dynamically from the live registries**, not hardcoded — adding a 4th/5th Tool or Skill makes it selectable automatically. Proven again this session: `research_and_save_file` was selectable from natural language the moment it was registered, no prompt changes needed.
- **`generate()` vs `generate_strict()`**: `generate()` for output a human reads directly; `generate_strict()` for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns.** `validate_response()` only classifies; `decide()` only acts on that classification.
- **The graceful fallback chain can hide total live-LLM failure indistinguishably from healthy degradation.** Check `experiences.tool_source` directly; don't trust response text.
- **A detection existing in code doesn't mean it's acted on.** Verify any check actually changes behavior, not just what gets logged.
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable — apply the same pattern to future LLM-judged checks.
- **Compose existing Steps into a new Skill rather than writing new logic.** `ResearchAndSaveFileSkill` reused two Steps unchanged and added exactly one new one. Check for an existing Step before writing new logic — duplicating one is a design smell.
- **`aether.db` is untracked from git** but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed to include `ebf40a3`, `62002a9`; three more commits + the Tool/Skill expansion sit on top, uncommitted or push-unconfirmed, see above)
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Commit and push everything** listed under "Uncommitted changes" — confirm the three earlier commits actually reached `origin/main` too, this session never could verify.
2. Decide direction for what's next (Prudhvi's call):
   - Fix the DuckDuckGo/query-extraction fragility found this session (affects `research_topic` too, not just the new Skill)
   - Run `llm_validate: true` on real traffic before considering enforcement
   - Keep expanding the Tool/Skill set
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) that `Step` now has via `ScriptMeta`.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled (e.g. opt-in for a "powerful" mode). Not urgent — don't flip it back on without the same kind of live proof this session required.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement — needs a monitoring period on real traffic first.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- How to fix the DuckDuckGo Instant Answer API's narrow matching — a different search API, or having `extract_search_query()` preserve more of the original phrasing? Not decided.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence; keep digging until the mechanism is actually understood. Found the model-name bug, the `think`-mode root cause, and the DuckDuckGo/query-extraction fragility this way.
- **`verification-before-completion`** — strict "test live, verify against the real DB, don't claim done without proof" discipline. Caught the model-name bug, the timeout-vs-think-mode misdiagnosis, a real HTTP 500 in E2's own wiring, and an overclaimed "retry recovered it" result that turned out to be lucky timing instead. Keep doing this.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control (`ollama serve`, `uvicorn`) via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap between messages — use `setsid nohup ... < /dev/null &` instead. `/tmp` also gets cleared during long gaps — don't trust old log files after a pause; re-check process state directly first. The connector itself has also gone fully unresponsive mid-session more than once (4-minute tool-call timeouts) — when that happens, just retry after a pause; nothing was lost either time, but always re-read a file before assuming an in-flight edit landed.
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`) — don't assume anything listening there is Aether. This session ran Aether's backend on port 8010.
- Long-running local LLM calls can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls rather than one long blocking call.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8010` (or `--port 8000` if `stud-os` isn't running). Apply new migrations after pulling with `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled.
