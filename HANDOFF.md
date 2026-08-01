# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion, frontend rebuild, llm_validate real-traffic eval + UI polish

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented and fully complete.** 5 Tools, 5 Skills, all live-verified including standalone Tool selection (not just via a Skill). The frontend was fully rebuilt from scratch around a live capability/decision trace, then extended this session to show historical traces, `llm_validate` verdicts, and project memory, with a proper New Project modal — all live-verified end-to-end through a real browser. This session also root-caused and fixed the two real issues the previous session's `llm_validate` eval found (`calculate_and_explain`'s confusion, memory bleed-through) — see item 14 below.

**Push status, precisely** (Prudhvi confirmed the push landed partway through last session — everything since is new local commits, not yet re-confirmed):
- `ebf40a3` through `1b21f67` — confirmed pushed to `origin/main`
- `961e2b6` through `bb3c659` (7 commits) — committed locally, **push not confirmed this session**
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
13. **`llm_validate` run on real traffic for the first time, per Prudhvi's explicit call for this session.** Sent 22 varied prompts through `/chat` with `llm_validate: true` across two batches in an isolated project. **18 of 18 applicable judged responses agreed with an independent read** — every pass genuinely on-topic, every flag genuinely bad, including two hits of the same underlying `calculate_and_explain` bug (confirms it's systematic, fixed in item 14 below). Small sample and the judge shares a model family with the generator, so this is promising, not proof — recommendation is a larger, more adversarial batch before promoting to gating, not promotion itself. **Found and fixed two more real bugs the traffic itself surfaced, independent of the judge**: (a) `research_and_save_file` ignored any filename the user actually typed, always slugifying the search query instead — silently saved "eiffel_summary.txt" as "eiffel_tower.txt"; (b) `file_digest`/`research_topic` crashed with a 500 on their own success path — both end in `SaveMemoryStep`, whose dict output was returned raw as the chat response and crashed `validate_response()`'s `response.strip()`. Neither Skill had previously been exercised by a broad prompt mix. Both fixed in `planning_service.py` (commit `961e2b6`), both live-verified — see `STATUS.md` item 13 for full detail including the exact verification commands.
14. **Both remaining item-13 issues fixed, plus a full UI polish batch — all live-verified.** Prudhvi's direction: confirm the push, fix both real issues item 13 found, then polish the UI. (a) `calculate_and_explain`'s confusion bug root-caused: `SummarizeStep` explained bare code output ("Output:\n36.0\n") with zero indication of what question it answers — fixed with an optional `context["question"]` that grounds the explain prompt, a no-op for every other caller (commit `4f10b1b`). (b) Memory bleed-through root-caused: `SaveMemoryStep`'s skill artifacts and `extract_memory_facts()`'s durable user facts share one `Memory` table with no relevance filtering, and the prompt labeled all of it "User profile" plus "use when relevant" — so the model worked irrelevant prior skill output into unrelated answers. Fixed at the prompt-framing level: relabeled, added an explicit "ignore if not relevant" instruction (commit `0338c4b`) — a mitigation, not a structural fix, see Known gaps. (c) Backend support added for UI polish: migration `44f9e98b07f2` persists capability-trace fields per chat so historical messages can show one; `llm_validation` is now stored and returned instead of computed-then-discarded; new `GET /project/{id}/memory` endpoint (commit `41fe644`). (d) Full UI polish batch, all live-verified via Playwright against the real running app: New Project modal replacing `window.prompt()`/`alert()` (tested both the success and duplicate-name-error paths), a `llm_validate` "validate" toggle in the composer wired to a real `llm·valid`/`llm·flagged` trace chip, historical chats now render their capability trace (pre-migration rows correctly show none), and a Memory panel showing exactly what's injected into reasoning prompts (commit `bb3c659`). See `STATUS.md` item 14 for full detail on every verification step.

Full detail, including every `experiences` table row and every live test across the whole project, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

None — working tree is clean. Everything through `bb3c659` (item 14) is committed locally. 7 commits (`961e2b6` through `bb3c659`) are outstanding for push — see "Push status" above.

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
- **A shared Step can't assume every caller's raw text is self-describing.** `SummarizeStep`'s bare "explain this simply" worked by accident for web search results and file content, failed for bare code output — fixed with an optional grounding parameter, unused unless a caller needs it.
- **Labeling matters as much as content in a local-LLM prompt.** Same stored rows, labeled "User profile / use when relevant" vs. "Stored context / ignore if not relevant," produced meaningfully different model behavior — but see Known gaps for where a prompt fix isn't the whole answer.
- **Verify a new backend field end-to-end (including a direct DB read) before building UI on top of it**, not just trusting the API response looks right.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed through `1b21f67`; 7 more commits sit on top locally, working tree clean, see "Push status")
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- `run.sh` — starts Ollama + backend + frontend together for local testing (see README's "Running locally")
- Backend key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/` (esp. `summarize_step.py`), `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py`, `services/ollama_service.py` (memory-prompt framing), `plugins/web_search.py`, `alembic/versions/44f9e98b07f2_*.py` (chats capability-trace columns)
- Frontend key modules: `frontend/src/App.js`, `frontend/src/api.js`, `frontend/src/components/` (`Sidebar`, `ChatWindow`, `CapabilityTrace`, `CapabilitiesPanel`, `MemoryPanel`, `NewProjectModal`), `frontend/src/App.css`, `frontend/src/index.css` (design tokens)
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog — not system Python)

## Next steps

1. **Push the 7 outstanding commits** (`961e2b6` through `bb3c659`) — `ssh-add ~/.ssh/id_ed25519` locally, then `git push origin main`.
2. Decide direction for what's next (Prudhvi's call):
   - Run a **larger, more adversarial `llm_validate` batch** (50+, including prompts crafted specifically to fool the judge) before considering enforcement — 18/18 agreement so far is promising but a small sample, and the judge shares a model family with the generator
   - Keep expanding the Tool/Skill set
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata that `Step` has via `ScriptMeta`.
4. Real design gap, not urgent: the memory bleed-through fix (item 14) is prompt-level, not structural — `SaveMemoryStep` skill artifacts and durable user facts still share one table with no relevance filtering or size cap. A proper Memory Service (`ARCHITECTURE.md`) would separate these; today's fix just tells the model to ignore what isn't relevant, which works but isn't a guarantee.
5. Minor cleanup, not urgent: several test/debug projects have accumulated in the local DB (`llm-validate-eval`, `memory-recall-check`, `ui-verification`, etc.) — harmless, could be deleted via the UI/API if the project list gets noisy.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled. Not urgent.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement — 18/18 agreement so far (item 13), still small-sample.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- Web search still isn't 100% reliable on very messy phrasing — real, honest residual limit.
- Whether the memory bleed-through fix needs to go further than prompt framing (a real Memory Service separating facts from skill artifacts) — flagged, not decided.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence. Found the model-name bug, the `think`-mode root cause, the DuckDuckGo/query-extraction fragility, the `FindFileStep` matching bug, the `execute_plugin()` dispatcher gap, `calculate_and_explain`'s missing question context, and the memory bleed-through mechanism this way.
- **`verification-before-completion`** — strict "test live, don't claim done without proof" discipline. Every fix across both sessions that skipped a live re-test after the code "looked right" turned out to need at least one more round — including catching a self-inflicted bug (an edit that deleted a function body) by reading the file back rather than trusting the tool call succeeded, and this session's full Playwright pass on every new UI element before calling any of it done.
- **`frontend-design`** / **`ui-styling`** — used for the UI rebuild (item 12) and this session's polish batch (item 14): brief-driven design tokens (color/type/layout), reusing established patterns (`.panel-overlay`/`.panel`) for new surfaces rather than inventing one-off styles.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled after a multi-hour gap — use `setsid nohup ... < /dev/null &` instead, or just use `run.sh`, which already handles this. **Every single-message gap this session killed the stack** — not just long pauses, any turn boundary where the user takes a while to respond. Treat "is anything actually running" as unknown at the start of every turn, not just after an explicit wait; `ps aux | grep -E "run.sh|uvicorn|react-scripts|ollama"` first, restart clean if empty, re-check `git status --short` too (uncommitted edits survive fine — it's only the running processes and `/tmp` that die). `/tmp` also gets cleared during these gaps — re-create any scratch files (prompt lists, etc.) rather than assuming they survived. A single sequential curl loop of ~10 real LLM calls (5-6s each without `think`, longer for skill chains with a web search + summarize) is long enough to hit the MCP tool layer's own ~4 minute call ceiling — launch it with `nohup bash -c '...' > logfile &` / `disown` and poll the logfile with short `sleep N; cat logfile` calls from the start, don't wait until a synchronous call times out first. **The Desktop Commander MCP server itself (not just the app stack) has gone fully unresponsive mid-session repeatedly this session** — every tool call, including trivial ones like `echo alive`, timing out at 4 minutes — distinct from the app stack dying; when it happens, just retry the same simple call every so often until it responds again, don't try to work around it. Nothing was lost any of the times this happened across both sessions, but always re-read a file before assuming an in-flight edit landed, and re-check `git log`/`git status` before assuming commit/push state. `edit_block`'s find/replace occasionally rejects an edit with a generic "must provide old_string+new_string" error on a call that does provide both, for no clear reason — worked on immediate retry with the same or simplified content every time this has happened; not worth over-diagnosing. New files need `desktop-commander:write_file`, not `edit_block` (which only edits existing files) or the sandboxed `create_file`/`str_replace` tools (those write to Claude's own container, not the real machine).
- Port 8000 on this machine is used by Prudhvi's *other* project (`stud-os`) — `run.sh` auto-detects this and falls back to 8010, setting `REACT_APP_API_URL` to match. Don't assume anything listening on 8000 is Aether without checking.
- **Watch for multiple `run.sh` instances running simultaneously** — happened once in an earlier session (likely started in two terminal tabs), causing two backends (8000 and 8010) with ambiguity about which the frontend was actually using. Check `ps aux | grep -E "run.sh|uvicorn|react-scripts"` before assuming a clean single instance; stop everything and restart fresh if in doubt.
- Long-running local LLM calls can exceed the MCP tool layer's own ~4 minute call ceiling — launch such commands with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls.
- Any external API call may need a `User-Agent` header or similar identification — don't assume "no results" means the query was bad; check the raw HTTP status first.
- Playwright screenshots save to the real machine's filesystem (found at `~/aether_*.png` this session), not Claude's own sandbox — use `desktop-commander:read_file` on the real path to actually view them, not the sandboxed `view` tool.
- To run everything: `./run.sh` from the repo root. Manual equivalent in README.md / STATUS.md's "How to run it now."
