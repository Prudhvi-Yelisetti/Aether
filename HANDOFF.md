# Handoff: Aether AIOS — architecture review, security hardening, and Phase A–E1 implementation

# Handoff: Aether AIOS — architecture review, security hardening, and Phase A–E1 implementation, live-LLM verification

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. This session did the actual implementation work, phase by phase, with live verification at every step — not just planning.

## Status

**Everything through Phase E1 is implemented and was committed/pushed as of `eb874c7`.** This session (the following one) ran the live-Ollama verification E1's handoff called for, and found + fixed real bugs it exposed. **These fixes are NOT YET COMMITTED** — see "Uncommitted changes" below.

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, including a full retrofit of Script/Validation/Metrics onto the Step contract — 3 Skills exist: `research_topic`, `file_digest`, `calculate_and_explain`
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output (code, search queries)
- **Phase E1** — the Planner (`services/planning_service.py`), registry-driven capability selection (Tool/Skill/reasoning), wired live into `main.py`

**This session's finding, stated plainly**: the previous handoff's "run one real test with Ollama up" was necessary but not sufficient. Ollama was started, and the very first live test revealed every LLM call site in the backend hardcoded model names (`llama3`, `mistral`) that don't exist on this machine (only `qwen3.5:9b` and `qwen3-coder:latest` are pulled) — so the live-LLM decision path had been silently, instantly failing over to fallback this whole time, indistinguishable from Ollama being down. Fixed across 7 files. Re-tested: the live decision path succeeded (`experiences.tool_source = "llm"`), but latency was wildly inconsistent (45s–150s+) for the identical prompt. Chased that down properly instead of just raising the timeout further: **`qwen3.5:9b` is a hybrid thinking model, and the Ollama request payload never set `think`, so every call — including one-line classification prompts — ran an unbounded hidden reasoning trace.** Proved with a controlled A/B (same prompt, same correct output): 30.9s with `think` unset vs 0.8s with `think=False`. Fixed by adding an explicit `think: bool = False` parameter to `ollama_service.generate_response()`. Re-verified live: 3 consecutive identical requests, all `tool_source: "llm"`, all `success: true`, 5–6 seconds each. **Both the original live-LLM-path question and the latency variance are closed, with proof.**

Then started **E2 (Validator)**, scoped to its first deterministic check per Prudhvi's decision. Found the actual gap: `main.py` already computed a `success` flag from failure-string prefixes for the experience log, but never acted on it to protect the `response` actually delivered to the user — that's how a raw Ollama timeout string reached the user earlier in the session. Built `services/validation_service.py` as a single source of truth for failure detection (previously duplicated, slightly differently, in `reasoning_service.py` and `main.py` — same pattern as the model-name bug), wired it into `main.py` so failures get a clean message instead of a leaked internal string. **My first wiring attempt had a real bug — an import rename left one stale reference, causing a live HTTP 500** — caught by testing, not assumed clean, fixed, re-verified. Final live proof, both directions: normal request → `tool_source: llm, success: true`, 9.8s; Ollama stopped mid-session → validator caught the failure string, user got a clean message, `success: false`, `response_validation_failed` logged with reason.

Full detail, including every DB row from every test across both the still-flaky first fix attempt and the final ones, is in `STATUS.md` — read that, not just this summary.

## Uncommitted changes (as of this handoff)

Not yet committed:
- Model-name fix: `routing.py`, `planning_service.py`, `plugin_manager.py`, `extraction.py`, `memory_extraction.py`, `services/steps/summarize_step.py`, `reasoning_service.py`, `ollama_service.py` (default params)
- `think` fix: `ollama_service.py` — `generate_response()` now takes `think: bool = False`, passed explicitly in the Ollama API payload
- `REQUEST_TIMEOUT_SECONDS`: went 60 → 150 (band-aid, wrong fix) → back to 60 (correct, now that `think` is off)
- **New**: `services/validation_service.py` (E2's first deterministic check) — `FAILURE_PREFIXES`/`REASONING_FAILURE_PREFIXES` constants + `validate_response()`
- `reasoning_service.py` — imports `REASONING_FAILURE_PREFIXES` from `validation_service.py` instead of keeping its own copy
- `main.py` — `/chat` now calls `validate_response()` after generation; on failure, substitutes a clean message and logs `response_validation_failed` instead of delivering the raw internal string
- **Not fixed**: `services/router.py` is a dead, zero-caller file with the same model-name bug — recommend deleting, wasn't done unilaterally

Local DB baseline (verified clean throughout this session's testing): 1 project, 3 memory rows, 25 chats unchanged; `experiences` table gained 10 real test rows across both sessions (see `STATUS.md` for each row's outcome).

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.** Storing a Step's logic as a string and `exec()`/`eval()`-ing it would reintroduce the exact vulnerability class Phase A removed. This boundary is stated explicitly in `services/steps/script_meta.py` — don't let a future request to make Scripts "dynamically editable" cross it without the same security scrutiny.
- **Model selection and capability selection are two separate calls**, not one bundled decision. `ARCHITECTURE.md` assigns model selection to the Reasoning Service, not Planning; Phase B's `routing.route()` had blurred them together. Fixed in E1: `services/routing.py` now does model selection only (`select_model()`); `services/planning_service.py` does capability selection only.
- **The Planner's decision prompt is built dynamically from the live registries** (`ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`), not hardcoded capability names. This is the actual substance of "capability registry, not keyword matching" — adding a 4th Tool or Skill makes it selectable automatically.
- **`generate()` vs `generate_strict()`**: `generate()` is for output a human reads directly (chat replies) — a friendly failure string is the correct response. `generate_strict()` (raises `ReasoningError`) is for any automated caller that checks success programmatically (Steps, code-gen feeding a sandbox, query-extraction feeding a search). Getting this backwards caused two real bugs in an earlier session (see `STATUS.md`).
- **The graceful fallback chain (LLM → rule → reasoning) can hide total live-LLM failure indistinguishably from healthy degradation** — this is exactly what let the model-name bug go unnoticed. When verifying live-LLM behavior specifically, check `experiences.tool_source` in the DB directly; don't trust response text or "it answered fine" as proof the LLM path itself worked.
- **Skills are deliberately not auto-wired until their Planner exists**, and once E1 landed, all 3 were wired live.
- **A detection existing in code doesn't mean it's acted on** — `main.py` computed a failure-string `success` flag for the experience log for a while before this session noticed it was never used to protect the actual `response` delivered to the user. When adding an E3-style check later, verify it changes real behavior (what gets delivered/retried), not just what gets logged.
- **`aether.db` is untracked from git** (real user data doesn't belong in version control) but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, real, git-tracked, pushed to `origin/main` through `eb874c7`; uncommitted changes on top, see above)
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key new modules: `services/planning_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Commit everything uncommitted** (model-name + `think`-mode + timeout + E2 Validator fixes).
2. **Continue E2**: the empty-response branch in `validate_response()` exists but hasn't had its own dedicated live test (only the known-failure-prefix branch has). Worth a quick verification. After that, decide whether to add LLM-based validation now or move on.
3. Decide direction for what's next (Prudhvi's call):
   - Rest of **E2** (LLM-based validation — "does this response actually answer the question")
   - **E3** (Decision: deliver / retry / escalate) — now has a real signal to act on (`validate_response()`'s result), which it didn't before this session
   - Or expand the Tool/Skill set further
4. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) that `Step` now has via `ScriptMeta`. Worth the same treatment once governance (Phase F+) actually needs it.
5. Consider deleting `services/router.py` (dead code, same bug, zero callers).

## Open questions

- Is 3 Skills + 3 Tools "enough" capability variety, or should more be built before layering more Planning/Validation/Decision sophistication on top?
- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled (e.g. opt-in for a "powerful" mode) once answer quality on hard questions becomes a real question. Not urgent — don't flip it back on without the same kind of live proof this session required.
- Whether E2's validation failure should ever trigger a retry (that's E3's job) rather than always degrading straight to the clean fallback message — worth revisiting once E3 exists.

## Suggested skills

- **`systematic-debugging`** — this is exactly the pattern that found the model-name bug this session: don't accept "Ollama is down" as an explanation once Ollama is confirmed up; check what the code actually does with a live response.
- **`verification-before-completion`** — strict "test live, verify against the real DB, don't claim done without proof" discipline. This caught the model-name bug (which "worked" in the sense of returning HTTP 200 with plausible-looking text) and the timeout flakiness (which a single lucky test would have missed). Keep doing this.
- No document-generation or research skills are relevant here — this is pure implementation/ops work in an existing repo via Desktop Commander (local filesystem + process control).

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control (`ollama serve`, `uvicorn`) via `start_process`/`interact_with_process`, were used this session. Background processes started with plain `nohup ... & disown` were killed when the parent shell session was recycled after a multi-hour gap between messages — use `setsid nohup ... < /dev/null &` instead so they survive shell/session churn. `/tmp` was also cleared during that gap — don't rely on log files surviving a long pause; re-check process state directly (`ps aux`, `curl` health checks) after any gap before trusting old logs.
- Long-running local LLM calls (cold model load: single-digit to ~150s+ seen) exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls rather than one long blocking call.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8000`. Apply new migrations after pulling with `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled.
