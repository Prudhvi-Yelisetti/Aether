# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented and fully complete.** A 4th Tool (`write_file`) and 4th Skill (`research_and_save_file`) were added and live-verified end-to-end (a real prompt now produces a real file). A pre-existing DuckDuckGo/query-extraction fragility that expansion surfaced was found and fixed the same day. The model-name duplication that caused this session's biggest bug is now centralized into one place.

**Push status, precisely** (this session diagnosed but could not resolve SSH access):
- `ebf40a3`, `62002a9` — confirmed pushed by Prudhvi
- `5196af7`, `8e65c28`, `1880557`, `df2463b`, `8f0bf13`, `18b2d8c` — committed locally, **push not confirmed**. A real SSH key exists on the machine; it just needs its passphrase entered locally (`ssh-add ~/.ssh/id_ed25519`, run by Prudhvi, not through this session) before `git push origin main` will work. Working tree is otherwise clean — nothing uncommitted right now.

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, full retrofit of Script/Validation/Metrics onto the Step contract
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output
- **Phase E1** — the Planner, registry-driven capability selection, live-LLM path verified (fast, reliable)
- **Phase E2** — complete, both increments: deterministic failure-string check + opt-in/observability-only LLM-based validation
- **Phase E3** — complete, bounded retry (with backoff) + escalate

**Capability inventory as of this handoff**: 4 Tools (`code`, `file`, `web`, `write_file`), 4 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`).

## This session's findings, in order

1. **Model-name bug.** Every LLM call site hardcoded model names (`llama3`, `mistral`) that don't exist on this machine — the live-LLM decision path had been silently failing over to fallback the whole time. Fixed across 7 files.

2. **Latency variance, root cause found.** `qwen3.5:9b` is a hybrid thinking model and the Ollama payload never set `think`, so every call ran an unbounded hidden reasoning trace. A/B proof: 30.9s with `think` unset vs 0.8s with `think=False`, same correct output. Fixed via `think: bool = False`.

3. **E2 (Validator), first check.** `main.py` computed a failure-string `success` flag for logging but never used it to protect the delivered response. Built `services/validation_service.py` as a single source of truth.

4. **E3 (Decision), first pass.** `validate_response()` classifies each failure as `retryable` or not. New `services/decision_service.py`: one attempt, validate, retry once if retryable, escalate otherwise.

5. **E3 follow-up: retry backoff, with a self-caught correction.** First live verification attempt *overclaimed* a result — a real successful recovery, but the log showed no retry had actually fired; it worked for an unrelated reason (lucky timing). Corrected with a deterministic test instead (`decide()` called with a fake attempt that fails once then succeeds — confirmed exactly 2 attempts, a measured 2.0s gap).

6. **E2 completed: LLM-based validation, opt-in and observability-only.** `validate_response_llm()` asks a model whether the response addresses the prompt. Off by default, logs only. Live-verified three cases: good answer (accepted), off-topic answer (flagged), judge unavailable (fails open).

7. **`services/router.py` deleted.** Dead, zero-caller file with the original model-name bug. Re-confirmed zero references, deleted, re-verified live.

8. **Tool/Skill expansion.** Added `WriteFileTool`/`write_file` (Aether could only read files before) and `ResearchAndSaveFileSkill`, composing the *existing* `WebSearchStep`+`SummarizeStep` with the new `WriteFileStep`. Live-verified through `/chat`, twice: the Planner correctly selected the new Skill (`source: llm`) from plain natural language, zero hardcoding needed. **Found, not yet fixed at this point**: `web_search`'s step failed on both live attempts — `"No useful results found"`.

9. **DuckDuckGo + query-extraction fragility, fixed same day.** Root-caused item 8's finding: DuckDuckGo's Instant Answer API does narrow exact-topic keying, and `extract_search_query()`'s LLM-extracted phrasing (e.g. `"Great Wall of China research"`) often didn't match it even though the raw topic (`"the Great Wall of China"`) did. This affects the *original* `research_topic` Skill identically, not just the new one. Fixed two things: tightened `extract_search_query()`'s prompt to preserve original topic wording and forbid added filler words (3 of 4 test prompts now extract cleanly); added a genuine second data source to `web_search.py` — a Wikipedia OpenSearch + summary fallback for when DDG returns nothing, since OpenSearch is far more forgiving of imperfect phrasing. **Caught a real bug in the fallback's own first version**: Wikipedia's API returns 403 without a `User-Agent` header, silently swallowed by a bare `except`, so the fallback looked "empty" rather than "broken" — found by testing the raw HTTP call directly, not trusting the wrapped function. Fixed, re-verified. **Full live proof**: the exact prompt that failed 100% of the time in item 8 now has `web_search` succeed on 3 consecutive live `/chat` attempts, and the 3rd fully completed end-to-end — real file, real content, on disk.

10. **Model name centralized; SSH push properly diagnosed.** The bug in item 1 was possible because the model name was hardcoded independently in 7 files rather than defined once — closed it, all 7 now import `FAST_MODEL`/`STRONG_MODEL` from `routing.py`. No circular imports, confirmed zero hardcoded model-name strings remain elsewhere. Live-verified with a full `/chat` request after the refactor, not just a clean import. Separately, investigated the SSH push failure instead of just re-reporting it: found a real, valid key on the machine — the issue is no `ssh-agent` running, not a missing/broken key. Attempted `ssh-add`, hit the (correct) passphrase prompt, and stopped there rather than asking for or accepting a passphrase through this session. The fix is one command in Prudhvi's own terminal.

Full detail, including every `experiences` table row and every live test across the whole session, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

Nothing — working tree is clean. Everything through item 10 above is committed locally as `18b2d8c` (HEAD). Only the push to `origin/main` is outstanding — see "Push status" above for the precise, diagnosed reason and the one-command fix.

Local DB baseline (verified clean throughout): 1 project, 3 memory rows, 25 chats unchanged across every test this session and every prior one.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.** Don't cross this boundary without the same security scrutiny Phase A required.
- **Model selection and capability selection are two separate calls.**
- **The Planner's decision prompt is built dynamically from the live registries**, not hardcoded — proven again this session: `research_and_save_file` was selectable from natural language the moment it was registered, no prompt changes needed.
- **`generate()` vs `generate_strict()`**: `generate()` for a human to read directly; `generate_strict()` for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns.**
- **The graceful fallback chain can hide total live-LLM failure indistinguishably from healthy degradation.** Check `experiences.tool_source` directly.
- **A detection existing in code doesn't mean it's acted on.**
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable.
- **Compose existing Steps into a new Skill rather than writing new logic.**
- **A bare `except Exception: return None` can hide a completely broken integration, not just "no results this time."** The Wikipedia fallback's first version silently ate a 403 on every call. When a fallback keeps returning "nothing," test the raw call directly before trusting the wrapped function.
- **Fix the root architectural gap, not just the symptom that exposed it.** The DuckDuckGo problem wasn't "this one query fails" — it was "this API is narrow by design." The fix added a real second data source, not just a better-worded query for the same narrow API.
- **`aether.db` is untracked from git** but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed to include `ebf40a3`, `62002a9`; 6 more commits sit on top locally, working tree otherwise clean, see "Push status" above)
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`, `plugins/web_search.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Run `ssh-add ~/.ssh/id_ed25519` locally, then `git push origin main`.** Nothing is uncommitted — this is the only remaining step to get all 6 pending commits onto GitHub.
2. Decide direction for what's next (Prudhvi's call):
   - Run `llm_validate: true` on real traffic before considering enforcement
   - Keep expanding the Tool/Skill set
   - Investigate whether web search's residual failure cases (very messy phrasing that beats both DDG and Wikipedia) are worth another pass
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata that `Step` now has via `ScriptMeta`.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled. Not urgent.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- Web search still isn't 100% reliable even after the fix (see item 9) — real, honest residual limit, worth another pass only if it recurs in practice.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence. Found the model-name bug, the `think`-mode root cause, and the DuckDuckGo/query-extraction fragility this way.
- **`verification-before-completion`** — strict "test live, don't claim done without proof" discipline. Caught the model-name bug, the timeout-vs-think-mode misdiagnosis, a real HTTP 500 in E2's own wiring, an overclaimed retry-recovery result, and a silently-broken Wikipedia fallback (403, swallowed by a bare `except`). Every one of these was caught by testing the actual mechanism, not trusting a good-looking outcome.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control (`ollama serve`, `uvicorn`) via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap between messages — use `setsid nohup ... < /dev/null &` instead. `/tmp` also gets cleared during long gaps — re-check process state directly after any pause rather than trusting old logs. The connector itself has gone fully unresponsive mid-session more than once (4-minute tool-call timeouts) — just retry after a pause; nothing was lost either time, but always re-read a file before assuming an in-flight edit landed.
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`) — don't assume anything listening there is Aether. This session ran Aether's backend on port 8010.
- Long-running local LLM calls can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls rather than one long blocking call.
- Any external API call (Wikipedia, and possibly others added later) may need a `User-Agent` header or similar identification — don't assume a "no results" response means the query was bad; check the raw HTTP status first.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8010` (or `--port 8000` if `stud-os` isn't running). Apply new migrations after pulling with `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled.
