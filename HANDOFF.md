# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, live-LLM verification

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 (first pass) are implemented.** Commit `ebf40a3` (model-name fix, `think`-mode fix, timeout tuning, E2's first Validator check) is committed locally but **not pushed** — this session has no SSH key access on Prudhvi's machine (`git push` fails with `Permission denied (publickey)`; push manually). **E3 (bounded retry/escalate) is built and live-verified but not yet committed** — see "Uncommitted changes" below.

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, full retrofit of Script/Validation/Metrics onto the Step contract — 3 Skills exist: `research_topic`, `file_digest`, `calculate_and_explain`
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output (code, search queries)
- **Phase E1** — the Planner (`services/planning_service.py`), registry-driven capability selection (Tool/Skill/reasoning). **Live-LLM path since verified this session** — see below.
- **Phase E2** — first pass: `services/validation_service.py`, deterministic check that catches known internal-failure strings before they reach the user
- **Phase E3** — first pass: `services/decision_service.py`, bounded retry (one extra attempt for transient failures) + escalate (clear honest message when still invalid)

## This session's findings, in order

1. **Model-name bug.** The previous handoff's "run one real test with Ollama up" was necessary but not sufficient. Every LLM call site hardcoded model names (`llama3`, `mistral`) that don't exist on this machine (only `qwen3.5:9b` and `qwen3-coder:latest` are pulled) — so the live-LLM decision path had been silently, instantly failing over to fallback the whole time, indistinguishable from Ollama being down. Fixed across 7 files.

2. **Latency variance, root cause found.** After the model-name fix, decision-call latency swung 45s–150s+ for the identical prompt. Not reload cost or hardware — `qwen3.5:9b` is a hybrid thinking model and the Ollama payload never set `think`, so every call ran an unbounded hidden reasoning trace. Proved with an A/B: 30.9s with `think` unset vs 0.8s with `think=False`, same correct output. Fixed via a `think: bool = False` parameter. Re-verified: 3 consecutive requests, all `tool_source: llm`, all successful, 5–6s each.

3. **E2 (Validator), first check.** `main.py` already computed a `success` flag from failure-string prefixes for the experience log, but never acted on it to protect the delivered `response` — that's how a raw Ollama timeout string had reached users earlier in the session. Built `services/validation_service.py` as a single source of truth for failure detection (previously duplicated, slightly differently, in `reasoning_service.py` and `main.py`). A real bug in the first wiring attempt (stale reference after an import rename) caused a live HTTP 500 — caught by testing, fixed, re-verified.

4. **E3 (Decision), first pass.** Extended `validate_response()` to classify each failure as `retryable` or not (transient like "Could not reach Ollama" vs permanent like "File not found"). New `services/decision_service.py`: one attempt, validate, retry once if retryable, escalate otherwise. `main.py` now delegates entirely to `decide()`. **Live-verified on all three paths**: normal delivery (1 attempt), immediate escalation for a permanent failure (1 attempt, no wasted retry), retry-then-escalate for a transient failure that's still failing (2 attempts, `decision_retry` then `decision_escalated` logged).

Full detail, including every `experiences` table row from every test across the whole session, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

Committed as `ebf40a3` (not pushed): model-name fix (7 files), `think` fix, timeout tuning, E2's `validation_service.py`.

**Not yet committed**:
- `services/decision_service.py` (new) — E3's `decide()`
- `services/validation_service.py` — extended with `retryable` classification per failure prefix
- `backend/main.py` — refactored to delegate to `decide()` instead of calling `validate_response()` directly
- `STATUS.md` — rewritten (had accumulated duplication from incremental edits), now reflects E3
- **Not fixed, still flagged**: `services/router.py` is a dead, zero-caller file with the original model-name bug — recommend deleting, wasn't done unilaterally

Local DB baseline (verified clean throughout): 1 project, 3 memory rows, 25 chats unchanged across every test this session and the prior one.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.** Storing a Step's logic as a string and `exec()`/`eval()`-ing it would reintroduce the exact vulnerability class Phase A removed. Stated explicitly in `services/steps/script_meta.py` — don't cross this boundary without the same security scrutiny.
- **Model selection and capability selection are two separate calls.** `services/routing.py` does model selection only (`select_model()`); `services/planning_service.py` does capability selection only.
- **The Planner's decision prompt is built dynamically from the live registries** (`ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`), not hardcoded capability names — adding a 4th Tool or Skill makes it selectable automatically.
- **`generate()` vs `generate_strict()`**: `generate()` is for output a human reads directly — a friendly failure string is correct. `generate_strict()` (raises `ReasoningError`) is for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns, same pattern as model/capability selection.** `validate_response()` only classifies (valid? retryable?); `decide()` only acts on that classification (retry/escalate/deliver). Don't collapse them.
- **The graceful fallback chain (LLM → rule → reasoning) can hide total live-LLM failure indistinguishably from healthy degradation** — exactly what let the model-name bug go unnoticed. Check `experiences.tool_source` directly; don't trust response text as proof the LLM path worked.
- **A detection existing in code doesn't mean it's acted on.** `main.py` computed a failure-string `success` flag for a while before this session noticed it was never used to protect the actual delivered response. Verify any future check changes real behavior, not just what gets logged.
- **`aether.db` is untracked from git** (real user data doesn't belong in version control) but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked, `origin/main` at `76abfd3` remotely as of this writing; `ebf40a3` committed locally but not pushed; E3 uncommitted on top)
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Push `ebf40a3`** (needs SSH access this session didn't have), then **commit + push E3**.
2. Decide direction for what's next (Prudhvi's call):
   - Add retry backoff to E3 (known gap — zero delay between attempts limits real-outage recovery)
   - Rest of E2 (LLM-based validation — "does this response actually answer the question")
   - Expand the Tool/Skill set further
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) that `Step` now has via `ScriptMeta`. Worth the same treatment once governance (Phase F+) actually needs it.
4. Consider deleting `services/router.py` (dead code, same bug, zero callers).

## Open questions

- Is 3 Skills + 3 Tools "enough" capability variety, or should more be built before layering more Planning/Validation/Decision sophistication on top?
- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled (e.g. opt-in for a "powerful" mode) once answer quality on hard questions becomes a real question. Not urgent — don't flip it back on without the same kind of live proof this session required.
- Whether E3's retry should get backoff, and how much — currently zero delay, which works for slowness but not real outages.

## Suggested skills

- **`systematic-debugging`** — the pattern that found both the model-name bug and the `think`-mode root cause this session: don't accept a surface explanation ("Ollama is down", "needs a bigger timeout") once it's contradicted by evidence; keep digging until the mechanism is actually understood.
- **`verification-before-completion`** — strict "test live, verify against the real DB, don't claim done without proof" discipline. Caught the model-name bug, the timeout-vs-think-mode misdiagnosis, and a real HTTP 500 in this session's own E2 wiring. Keep doing this — every fix this session that skipped straight to "should be fixed now" without a live re-test turned out to need at least one more round.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control (`ollama serve`, `uvicorn`) via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap between messages — use `setsid nohup ... < /dev/null &` instead. `/tmp` also gets cleared during long gaps — don't trust old log files after a pause; re-check process state directly (`ps aux`, `curl` health checks) first.
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`, a different repo at `~/Projects/stud-os`) — don't assume anything listening there is Aether. This session ran Aether's backend on port 8010 instead to avoid confusion.
- Long-running local LLM calls (cold model load, or a genuine hang) can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls rather than one long blocking call.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8010` (or `--port 8000` if `stud-os` isn't running). Apply new migrations after pulling with `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled.
