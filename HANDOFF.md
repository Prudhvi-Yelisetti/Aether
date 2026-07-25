# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented and fully complete.** Two rounds of Tool/Skill expansion since: `write_file`/`research_and_save_file`, then `list_files`/`find_and_digest_file`. Both were live-verified end-to-end from realistic natural-language prompts, and both surfaced real bugs that got found and fixed the same day, not shipped and left. The model-name duplication that caused this session's biggest bug is now centralized into one place.

**Push status, precisely** (this session diagnosed but could not resolve SSH access):
- `ebf40a3`, `62002a9` — confirmed pushed by Prudhvi
- `5196af7`, `8e65c28`, `1880557`, `df2463b`, `8f0bf13`, `18b2d8c`, `8c3ef99` — committed locally, **push not confirmed**. A real SSH key exists on the machine; it just needs its passphrase entered locally (`ssh-add ~/.ssh/id_ed25519`, run by Prudhvi, not through this session) before `git push origin main` will work.
- **Uncommitted right now**: the second Tool/Skill expansion (`list_files`, `find_and_digest_file`) — see "Uncommitted changes" below.

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, full retrofit of Script/Validation/Metrics onto the Step contract
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output
- **Phase E1** — the Planner, registry-driven capability selection, live-LLM path verified (fast, reliable)
- **Phase E2** — complete, both increments: deterministic failure-string check + opt-in/observability-only LLM-based validation
- **Phase E3** — complete, bounded retry (with backoff) + escalate

**Capability inventory as of this handoff**: 5 Tools (`code`, `file`, `web`, `write_file`, `list_files`), 5 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`, `find_and_digest_file`).

## This session's findings, in order

1. **Model-name bug.** Every LLM call site hardcoded model names (`llama3`, `mistral`) that don't exist on this machine — the live-LLM decision path had been silently failing over to fallback the whole time. Fixed across 7 files.

2. **Latency variance, root cause found.** `qwen3.5:9b` is a hybrid thinking model and the Ollama payload never set `think`, so every call ran an unbounded hidden reasoning trace. A/B proof: 30.9s with `think` unset vs 0.8s with `think=False`, same correct output. Fixed via `think: bool = False`.

3. **E2 (Validator), first check.** `main.py` computed a failure-string `success` flag for logging but never used it to protect the delivered response. Built `services/validation_service.py` as a single source of truth.

4. **E3 (Decision), first pass.** `validate_response()` classifies each failure as `retryable` or not. New `services/decision_service.py`: one attempt, validate, retry once if retryable, escalate otherwise.

5. **E3 follow-up: retry backoff, with a self-caught correction.** First live verification attempt *overclaimed* a result — a real successful recovery, but the log showed no retry had actually fired; it worked for an unrelated reason (lucky timing). Corrected with a deterministic test instead.

6. **E2 completed: LLM-based validation, opt-in and observability-only.** `validate_response_llm()` asks a model whether the response addresses the prompt. Off by default, logs only.

7. **`services/router.py` deleted.** Dead, zero-caller file with the original model-name bug.

8. **First Tool/Skill expansion.** `WriteFileTool`/`write_file` (Aether could only read files before) and `ResearchAndSaveFileSkill`, composing the *existing* `WebSearchStep`+`SummarizeStep` with the new `WriteFileStep`. Live-verified the Planner selects it correctly (`source: llm`). **Found, not yet fixed at this point**: `web_search` failed on both live attempts — `"No useful results found"`.

9. **DuckDuckGo + query-extraction fragility, fixed same day.** DuckDuckGo's Instant Answer API does narrow exact-topic keying, and `extract_search_query()`'s LLM-extracted phrasing often didn't match it. Fixed two things: tightened the extraction prompt to preserve original wording; added a genuine second data source (Wikipedia OpenSearch + summary) for when DDG returns nothing. **Caught a real bug in the fallback's own first version**: Wikipedia's API returns 403 without a `User-Agent` header, silently swallowed by a bare `except`. Fixed, re-verified. Full live proof: the exact prompt that failed 100% of the time in item 8 now succeeds on 3 consecutive live attempts, one fully end-to-end.

10. **Model name centralized; SSH push properly diagnosed.** All 7 files with hardcoded model names now import `FAST_MODEL`/`STRONG_MODEL` from `routing.py`. Live-verified with a full `/chat` request post-refactor. Separately, investigated (not just re-reported) the SSH push failure: a real key exists, it just needs its passphrase entered locally — attempted `ssh-add`, hit the correct prompt, stopped there rather than asking for or accepting a passphrase through this session.

11. **Second Tool/Skill expansion: `list_files` + fuzzy file lookup, with a real matching bug caught before shipping.** `ListFilesTool`/`list_files` (5th Tool) closes the "File not found" gap — the single most common permanent Tool/Skill failure all session. New `FindFileStep` does deterministic fuzzy matching, deliberately named `"filename"` so its output lands exactly where the *existing* `ReadFileStep` already expects it. New `FindAndDigestFileSkill` (5th Skill) composes `ListFilesStep`+`FindFileStep` (new) with `ReadFileStep`+`SummarizeStep` (existing, reused unchanged). **The first version of `FindFileStep` passed every unit test but failed live, twice**, on realistic natural-language prompts ("summarize my jazz file for me") — whole-sentence-vs-filename character matching is too crude, even though the Planner selection and every other step in the chain worked correctly both times. Root-caused from the logs, fixed with a token-level fallback (strip filler words, match individual words against each filename's stem), re-verified: both previously-failing prompts now succeed fully end-to-end with correct, on-topic output.

Full detail, including every `experiences` table row and every live test across the whole session, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

Committed locally through `8c3ef99`; push not confirmed for `5196af7` onward (see "Push status" above).

**Not yet committed at all** — the second Tool/Skill expansion (item 11):
- `plugins/file_lister.py` (new), `services/tools/list_files_tool.py` (new), `services/tools/registry.py` (registered)
- `services/steps/find_file_step.py` (new)
- `services/skills/find_and_digest_file_skill.py` (new), `services/skills/registry.py` (registered)
- `services/planning_service.py` (`_build_skill_input()`'s new `find_and_digest_file` branch)
- `STATUS.md`, `ROADMAP.md`, this file — updated with all of the above

Local DB baseline (verified clean throughout): 1 project, 3 memory rows, 25 chats unchanged across every test this session and every prior one.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.**
- **Model selection and capability selection are two separate calls.**
- **The Planner's decision prompt is built dynamically from the live registries**, not hardcoded — proven twice more this session, for both new Skills.
- **`generate()` vs `generate_strict()`**: `generate()` for a human to read directly; `generate_strict()` for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns.**
- **The graceful fallback chain can hide total live-LLM failure indistinguishably from healthy degradation.** Check `experiences.tool_source` directly.
- **A detection existing in code doesn't mean it's acted on.**
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable.
- **Compose existing Steps into a new Skill rather than writing new logic.** Both this session's new Skills reused 2 existing Steps unchanged and added exactly one new one each.
- **A bare `except Exception: return None` can hide a completely broken integration, not just "no results this time."**
- **Fix the root architectural gap, not just the symptom that exposed it.** The DuckDuckGo problem wasn't "this one query fails" — it was "this API is narrow by design."
- **Unit tests with clean, short inputs aren't enough for anything that will receive natural language.** `FindFileStep` passed every unit test and still failed live, twice, on realistic full-sentence prompts. Test with the messy input a real user would type.
- **`aether.db` is untracked from git** but stays on disk, already in `.gitignore`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed to include `ebf40a3`, `62002a9`; 7 more commits sit on top locally, plus the uncommitted expansion above, see "Push status")
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- Key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`, `plugins/web_search.py`
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Commit the second Tool/Skill expansion** (item 11, currently uncommitted).
2. **Run `ssh-add ~/.ssh/id_ed25519` locally, then `git push origin main`.** This is the only remaining step to get everything onto GitHub.
3. Decide direction for what's next (Prudhvi's call):
   - Run `llm_validate: true` on real traffic before considering enforcement
   - Keep expanding the Tool/Skill set
   - Investigate whether web search's residual failure cases are worth another pass
4. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata that `Step` now has via `ScriptMeta`.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled. Not urgent.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- Web search still isn't 100% reliable even after the fix — real, honest residual limit.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence. Found the model-name bug, the `think`-mode root cause, the DuckDuckGo/query-extraction fragility, and the `FindFileStep` matching bug this way.
- **`verification-before-completion`** — strict "test live, don't claim done without proof" discipline. Every fix this session that skipped a live re-test after the code "looked right" turned out to need at least one more round — the model-name bug, the timeout-vs-think-mode misdiagnosis, a real HTTP 500 in E2's own wiring, an overclaimed retry-recovery result, a silently-broken Wikipedia fallback, and a fuzzy-matcher that passed every unit test but failed live twice. None of these were caught by "it imports cleanly" — all were caught by testing the actual live mechanism.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control (`ollama serve`, `uvicorn`) via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap between messages — use `setsid nohup ... < /dev/null &` instead. `/tmp` also gets cleared during long gaps — re-check process state directly after any pause rather than trusting old logs. The connector itself has gone fully unresponsive mid-session more than once (4-minute tool-call timeouts) — just retry after a pause; nothing was lost either time, but always re-read a file before assuming an in-flight edit landed.
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`) — don't assume anything listening there is Aether. This session ran Aether's backend on port 8010.
- Long-running local LLM calls can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls rather than one long blocking call.
- Any external API call may need a `User-Agent` header or similar identification — don't assume a "no results" response means the query was bad; check the raw HTTP status first.
- To run the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8010` (or `--port 8000` if `stud-os` isn't running). Apply new migrations after pulling with `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled.
