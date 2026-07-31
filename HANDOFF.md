# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion, frontend rebuild, llm_validate real-traffic eval

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented and fully complete.** 5 Tools, 5 Skills, all live-verified including standalone Tool selection (not just via a Skill). The frontend was fully rebuilt from scratch around a live capability/decision trace, verified end-to-end through a real browser. This session ran `llm_validate` against real traffic for the first time (18/18 judge agreement, small sample) and found + fixed two more real bugs along the way — see item 13 below.

**Push status, precisely** (still unresolved — the key exists, it just needs its passphrase entered locally by Prudhvi, not through a chat session; asked again this session, confirmed still not done):
- `ebf40a3` through `1b21f67` — confirmed pushed to `origin/main` at various points
- `19c5fd8`, `3dc1406`, `8fe70fc`, `f10d6fc`, `961e2b6` — committed locally, **push not confirmed**
- Working tree clean, nothing uncommitted

Completed phases (see `ROADMAP.md` for full checklists, `STATUS.md` for verification details on each item):
- **Phase A** — security: pooled SQLAlchemy DB, removed `eval()`, `bwrap`-sandboxed code execution, allowlisted file reads, Alembic migrations, structured logging + request IDs
- **Phase B** — unified routing, LLM-based memory extraction with upserts, frontend fix
- **Phase C** — formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table
- **Phase D** — Step/Skill abstraction, full retrofit of Script/Validation/Metrics onto the Step contract
- **Phase E0** — fixed a real bug where LLM failures were fed downstream as if they were valid output
- **Phase E1** — the Planner, registry-driven capability selection, live-LLM path verified
- **Phase E2** — complete, both increments: deterministic failure-string check + opt-in/observability-only LLM-based validation
- **Phase E3** — complete, bounded retry (with backoff) + escalate

**Capability inventory**: 5 Tools (`code`, `file`, `web`, `write_file`, `list_files`), 5 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`, `find_and_digest_file`).

## This session's findings, in order

1. **Model-name bug.** Every LLM call site hardcoded model names (`llama3`, `mistral`) that don't exist on this machine — the live-LLM decision path had been silently failing over to fallback the whole time. Fixed across 7 files.
2. **Latency variance, root cause found.** `qwen3.5:9b`'s hybrid thinking mode ran unbounded on every call. A/B proof: 30.9s with `think` unset vs 0.8s with `think=False`. Fixed via `think: bool = False`.
3. **E2 (Validator), first check.** `main.py` computed a failure-string `success` flag but never used it to protect the delivered response. Built `services/validation_service.py` as a single source of truth.
4. **E3 (Decision), first pass.** `validate_response()` classifies failures as `retryable` or not. New `services/decision_service.py`: retry once if retryable, escalate otherwise.
5. **E3 follow-up: retry backoff, with a self-caught correction.** Added a 2s delay before retrying. First live verification attempt *overclaimed* a result — corrected with a deterministic test instead of trusting a lucky-timing outcome.
6. **E2 completed: LLM-based validation, opt-in and observability-only.** `validate_response_llm()` — off by default, logs only, never gates delivery until proven reliable on real traffic.
7. **`services/router.py` deleted.** Dead, zero-caller file with the original model-name bug.
8. **First Tool/Skill expansion.** `WriteFileTool`/`write_file` and `ResearchAndSaveFileSkill`, composing existing Steps with one new one. Found, not yet fixed: `web_search` failing on real prompts.
9. **DuckDuckGo + query-extraction fragility, fixed same day.** Tightened extraction prompt; added a genuine second data source (Wikipedia OpenSearch + summary). Caught a real bug in the fallback's own first version (missing `User-Agent` header).
10. **Model name centralized; SSH properly diagnosed.** All 7 files now import from `routing.py`. SSH: real key, just needs a local passphrase entry (which Prudhvi then did for the first batch of commits).
11. **Second Tool/Skill expansion: `list_files` + fuzzy file lookup.** Closed "File not found," the most common permanent failure all session. Caught a real matching bug (whole-sentence-vs-filename comparison too crude) before shipping, fixed with a token-level fallback.
12. **API extended, frontend rebuilt from scratch, and a real dispatcher gap found through the new UI.** Prudhvi's ask: the old UI didn't reflect any of what had been built. Extended `/chat` to return capability/decision info (it always computed this, never returned it); added `GET /capabilities`. Rebuilt the frontend around a live trace (`plan·llm → skill:research_and_save_file → qwen3.5:9b → ok`) as the signature UI element, plus a Capabilities panel listing every Tool/Skill live from the registries. **Then found a real, previously-undiscovered bug through the new UI**: `execute_plugin()` (the dispatcher for a directly-selected Tool, as opposed to one called via a Skill) predates `write_file`/`list_files` entirely and silently returned `None` for both — every earlier test of those tools went through a Skill, bypassing this dispatcher. Fixed, live-verified through the API and then the real browser, the same way the bug was found.
13. **`llm_validate` run on real traffic for the first time, per Prudhvi's explicit call for this session.** Sent 22 varied prompts through `/chat` with `llm_validate: true` across two batches in an isolated project. **18 of 18 applicable judged responses agreed with an independent read** — every pass genuinely on-topic, every flag genuinely bad, including two hits of the same underlying `calculate_and_explain` bug (confirms it's systematic, not fixed this session, flagged as a known gap). Small sample and the judge shares a model family with the generator, so this is promising, not proof — recommendation is a larger, more adversarial batch before promoting to gating, not promotion itself. **Found and fixed two more real bugs the traffic itself surfaced, independent of the judge**: (a) `research_and_save_file` ignored any filename the user actually typed, always slugifying the search query instead — silently saved "eiffel_summary.txt" as "eiffel_tower.txt"; (b) `file_digest`/`research_topic` crashed with a 500 on their own success path — both end in `SaveMemoryStep`, whose dict output was returned raw as the chat response and crashed `validate_response()`'s `response.strip()`. Neither Skill had previously been exercised by a broad prompt mix. Both fixed in `planning_service.py` (commit `961e2b6`), both live-verified — see `STATUS.md` item 13 for full detail including the exact verification commands.

Full detail, including every `experiences` table row and every live test across the whole project, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

None — working tree is clean. Everything through `961e2b6` (item 13) is committed locally. Only the push to `origin/main` is outstanding for the last five commits (`19c5fd8`, `3dc1406`, `8fe70fc`, `f10d6fc`, `961e2b6`) — see "Push status" above.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.**
- **Model selection and capability selection are two separate calls.**
- **The Planner's decision prompt is built dynamically from the live registries**, not hardcoded — proven repeatedly: every new Tool/Skill this session was selectable from natural language the moment it was registered.
- **`generate()` vs `generate_strict()`**: `generate()` for a human to read directly; `generate_strict()` for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns.**
- **The graceful fallback chain can hide total live-LLM failure indistinguishably from healthy degradation.** Check `experiences.tool_source` directly.
- **A detection existing in code doesn't mean it's acted on.**
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable.
- **Compose existing Steps into a new Skill rather than writing new logic.**
- **A bare `except Exception: return None` can hide a completely broken integration, not just "no results this time."**
- **Unit tests with clean, short inputs aren't enough for anything that will receive natural language.**
- **A new interaction surface (like a rebuilt UI) can expose bugs old tests never would.** `execute_plugin()`'s missing `write_file`/`list_files` branches existed since those tools were added, survived every earlier live API test, and was only found by clicking through the new UI with a natural prompt. When adding a new surface, re-test old capabilities through it.
- **`aether.db` is untracked from git** but stays on disk, already in `.gitignore`.
- **Broad, uncurated real-traffic testing finds bugs that hand-picked live tests don't.** Item 13's `file_digest`/`research_topic` crash existed since Phase D and survived because every earlier live test of the memory-writing path happened to go through a different Skill. Running `llm_validate` on varied real traffic surfaced this bug independent of the judge itself.
- **Not every Step's output is human-facing text.** `WriteFileStep` returns a string meant for the user; `SaveMemoryStep` returns structured data. The Skill→response boundary in `execute_plan()` is the one place that should bridge that, not individual Steps or `validate_response()`.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed to include everything through `1b21f67`; 5 more commits sit on top locally, working tree clean, see "Push status")
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- `run.sh` — starts Ollama + backend + frontend together for local testing (see README's "Running locally")
- Backend key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/`, `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`, `plugins/web_search.py`
- Frontend key modules: `frontend/src/App.js`, `frontend/src/api.js`, `frontend/src/components/` (`Sidebar`, `ChatWindow`, `CapabilityTrace`, `CapabilitiesPanel`), `frontend/src/App.css`, `frontend/src/index.css` (design tokens)
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Push the 5 outstanding commits** (`19c5fd8`, `3dc1406`, `8fe70fc`, `f10d6fc`, `961e2b6`) — `ssh-add ~/.ssh/id_ed25519` locally, then `git push origin main`. Asked again this session; still not done as of this handoff.
2. Decide direction for what's next (Prudhvi's call):
   - Run a **larger, more adversarial `llm_validate` batch** (50+, including prompts crafted specifically to fool the judge) before considering enforcement — 18/18 agreement so far is promising but a small sample, and the judge shares a model family with the generator
   - **Fix the `calculate_and_explain` bug found this session**: its explain step goes into a confused "you've shared a number without context" loop instead of answering, reproduced on two separate real prompts ("15% of 240", "√144")
   - Keep expanding the Tool/Skill set
   - Polish the new UI further: a proper "New Project" modal instead of `window.prompt()`, surfacing `llm_validate` or project memory context in the UI, historical-message capability traces (currently only fresh messages show one — `/project/{id}/chats` doesn't return `model`/capability info per message)
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata that `Step` has via `ScriptMeta`.
4. Worth a look, not confirmed as a bug: two `llm_validate` eval responses this session referenced an unrelated earlier prompt's text ("validation test payload") unprompted — possibly project memory bleeding across unrelated prompts within the same project, or possibly just an artifact of running a mixed eval batch in one shared project. Not chased down this session.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled. Not urgent.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- Web search still isn't 100% reliable on very messy phrasing — real, honest residual limit.
- Should historical chat messages also show a capability trace? Would need `/project/{id}/chats` to return `model`/capability fields per message (currently only `prompt`/`response`) — a small backend extension, not done yet.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence. Found the model-name bug, the `think`-mode root cause, the DuckDuckGo/query-extraction fragility, the `FindFileStep` matching bug, and the `execute_plugin()` dispatcher gap this way.
- **`verification-before-completion`** — strict "test live, don't claim done without proof" discipline. Every fix this session that skipped a live re-test after the code "looked right" turned out to need at least one more round — including catching a self-inflicted bug (an edit that deleted a function body) by reading the file back rather than trusting the tool call succeeded.
- **`frontend-design`** / **`ui-styling`** — used for the UI rebuild (item 12): brief-driven design tokens (color/type/layout), a single well-motivated signature element (the capability trace) rather than generic chat-app styling.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap — use `setsid nohup ... < /dev/null &` instead, or just use `run.sh`, which already handles this. **This session hit this twice in the same conversation** (once mid-setup, once again after a user-side pause) — even `setsid nohup` didn't survive one of the gaps, so treat "is anything actually running" as unknown after any pause, not just long ones; `ps aux | grep -E "run.sh|uvicorn|react-scripts|ollama"` first, restart clean if empty. `/tmp` also gets cleared during these gaps, sometimes more than once per session — re-create any scratch files (prompt lists, etc.) rather than assuming they survived, and re-check process state directly (`curl` health checks) after any pause rather than trusting old logs. A single sequential curl loop of ~10 real LLM calls (5-6s each without `think`, longer for skill chains with a web search + summarize) is long enough to hit the MCP tool layer's own ~4 minute call ceiling — launch it with `nohup bash -c '...' > logfile &` / `disown` and poll the logfile with short `sleep N; cat logfile` calls from the start, don't wait until a synchronous call times out first. The connector itself has gone fully unresponsive mid-session repeatedly (4-minute tool-call timeouts) — just retry after a pause; nothing was lost any of the times this happened, but always re-read a file before assuming an in-flight edit landed, and re-check `git log`/`git status` before assuming commit/push state. `edit_block`'s find/replace occasionally rejects an edit with a generic "must provide old_string+new_string" error on a call that does provide both, for no clear reason — worked on immediate retry with the same or simplified content both times this session; not worth over-diagnosing.
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`) — `run.sh` auto-detects this and falls back to 8010, setting `REACT_APP_API_URL` to match. Don't assume anything listening on 8000 is Aether without checking.
- **Watch for multiple `run.sh` instances running simultaneously** — happened once this session (likely started in two terminal tabs), causing two backends (8000 and 8010) with ambiguity about which the frontend was actually using. Check `ps aux | grep -E "run.sh|uvicorn|react-scripts"` before assuming a clean single instance; stop everything and restart fresh if in doubt.
- Long-running local LLM calls can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls.
- Any external API call may need a `User-Agent` header or similar identification — don't assume "no results" means the query was bad; check the raw HTTP status first.
- Playwright screenshots save to the real machine's filesystem (found at `~/aether_*.png` this session), not Claude's own sandbox — use `desktop-commander:read_file` on the real path to actually view them, not the sandboxed `view` tool.
- To run everything: `./run.sh` from the repo root. Manual equivalent in README.md / STATUS.md's "How to run it now."
