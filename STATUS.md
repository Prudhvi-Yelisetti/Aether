# Aether — Current Status

_Last updated: July 30, 2026, after extending the API to expose capability/decision info, adding a `/capabilities` endpoint, rebuilding the frontend from scratch around a live Plan→Capability→Validate→Deliver trace, and fixing a real dispatcher gap (`execute_plugin()` never had `write_file`/`list_files` branches) found by testing through the new UI. Update this file whenever a Critical/Important item is resolved or a new one is found._

**Continuing in a new session? Read `HANDOFF.md` first — it's the compact version of everything below.**

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete. E0 + E1 complete and live-verified. E2 (both increments) and E3 (with backoff) all live and proven. 5 Tools, 5 Skills — all live-verified, including standalone Tool selection (not just via a Skill), the gap that item 12 below closed. Frontend fully rebuilt around a live capability/decision trace, verified end-to-end through a real browser.** |
| Commits | `ebf40a3` through `1b21f67` — pushed to `origin/main` (confirmed by Prudhvi at various points this project). `19c5fd8`, `3dc1406`, `8fe70fc`, `f10d6fc` — committed locally, **push not yet confirmed**; SSH key exists but needs its passphrase entered locally (`ssh-add`) each session — diagnosed, not fixable from this session. Working tree clean, nothing uncommitted. |
| Local usage | 2 projects (`test`, `claude-verification` — the latter created this session for isolated testing), 3 memory rows, 30+ chats — verified intact through every migration and test run across all sessions |
| Critical blockers | 0 |
| Next phase | Run `llm_validate` on real traffic before considering enforcement, keep expanding the Skill/Tool set, or polish the new UI further (a proper "new project" modal instead of `window.prompt`, surfacing memory context) — Prudhvi's call |

## How to run it now

```bash
./run.sh
```
Starts Ollama (if not already running), the backend, and the frontend dev server together — see `README.md`'s "Running locally" section. Falls back to port 8010 for the backend if 8000 is already taken by something else on the machine.

Manual equivalent: `cd backend && .venv/bin/uvicorn main:app --reload --port 8000`, then `cd frontend && npm start`. Apply new migrations after pulling: `.venv/bin/alembic upgrade head`. Ollama must be running with `qwen3.5:9b` and `qwen3-coder:latest` pulled — these are the only two models the codebase references (centralized in `routing.py`'s `FAST_MODEL`/`STRONG_MODEL`, see item 9). **Note**: on this dev machine, Ollama and the backend/frontend dev servers have repeatedly died between multi-hour gaps in sessions (survived a shell/session recycle, not a reboot) — always re-check `curl localhost:11434/api/tags`, the backend's own `/`, and `localhost:3000` before assuming any of them are still up.

## Session narrative, in order

### 1. Model-name bug (the real reason the live-LLM path was never tested)

Ollama had been down an entire prior session. Starting it up revealed every LLM call site hardcoded `"llama3"` or `"mistral"` as the model name — neither installed (only `qwen3.5:9b` and `qwen3-coder:latest` are). Every live call failed instantly on "model not found," silently routed to fallback — indistinguishable from Ollama being down at all. Proven live: first test request returned the raw Ollama error string verbatim as the chat response.

**Fixed across 7 files.** Flagged `services/router.py` (a dead, zero-caller duplicate with the same bug) for deletion rather than removing it unilaterally.

*(Resolved 2026-07-23: deleted, after confirming zero references anywhere and no test suite to break.)*

### 2. Latency variance — root cause was `think` mode, not timeout or hardware

Decision-call latency swung 45s–150s+ after the model-name fix. Root cause: `qwen3.5:9b` is a hybrid thinking model and the Ollama payload never set `think`, so every call — including one-line classification prompts — ran an unbounded hidden reasoning trace. A/B proof: 30.9s with `think` unset vs 0.8s with `think=False`, same correct output — **37x speedup**. Fixed via an explicit `think: bool = False` parameter, defaulting off everywhere. Re-verified: 3 consecutive requests, all successful, 5–6s each.

### 3. E2 — first deterministic Validator check

`main.py` computed a failure-string `success` flag for logging but never used it to protect the delivered `response`. Built `services/validation_service.py` as a single source of truth (`FAILURE_PREFIXES`, `validate_response()`) — was duplicated, slightly differently, in `reasoning_service.py`. A real HTTP 500 from a stale import was caught live during the first wiring attempt, fixed, re-verified.

### 4. E3 — bounded retry + escalate, live-proven on all three paths

`validate_response()` classifies each failure as `retryable` or not. New `services/decision_service.py`: one attempt, validate, retry once if retryable, escalate otherwise. Live-verified: normal delivery, immediate escalation for a permanent failure (no wasted retry), retry-then-escalate for a transient failure still failing. **Known gap at the time**: zero backoff between attempts.

### 5. E3 follow-up — retry backoff added, with an honest correction

Added `RETRY_DELAY_SECONDS = 2.0`. First live verification attempt *overclaimed* a result — a real successful recovery, but the log showed no retry had actually fired; it worked for an unrelated reason (lucky timing on a fresh Ollama restart). Caught by checking the log against the claim, corrected with a deterministic test instead: `decide()` called with a fake attempt that fails once then succeeds — confirmed exactly 2 attempts and a measured 2.0s gap matching the delay.

### 6. E2 completed — LLM-based validation, opt-in and observability-only

Added `validate_response_llm()` — asks a model whether a response addresses the prompt. Deliberately **not** wired to gate delivery or retry: off by default (`ChatRequest.llm_validate`), only logs a verdict when enabled. Rationale: an unreliable LLM judge silently rejecting good answers would be worse than not judging at all — needs a monitoring period on real traffic before being trusted to enforce anything. Live-verified three cases: good answer (accepted), off-topic answer (flagged), judge unavailable (fails open, doesn't penalize the response).

### 7. First Tool/Skill expansion — `write_file`, `research_and_save_file`

Closed a real gap: Aether could only read files, never write one. Added `WriteFileTool`/`write_file` (4th Tool) and `ResearchAndSaveFileSkill` (4th Skill), composing the *existing* `WebSearchStep`+`SummarizeStep` with the new `WriteFileStep`. Live-verified the Planner selects it correctly from natural language. **Found, not yet fixed at this point**: `web_search` failed on live attempts with "No useful results found."

### 8. DuckDuckGo + query-extraction fragility, fixed same day

Root-caused item 7's finding: DuckDuckGo's Instant Answer API does narrow exact-topic keying, and `extract_search_query()`'s LLM-extracted phrasing (e.g. "Great Wall of China research") often didn't match it even though the raw topic did — affects the *original* `research_topic` Skill identically. Fixed two things: tightened the extraction prompt to preserve original wording (3 of 4 test prompts now extract cleanly); added a genuine second data source to `web_search.py` — a Wikipedia OpenSearch + summary fallback for when DDG returns nothing. **Caught a real bug in the fallback's own first version**: Wikipedia's API returns 403 without a `User-Agent` header, silently swallowed by a bare `except`. Fixed, re-verified. Full live proof: the exact prompt that failed 100% of the time in item 7 now succeeds on 3 consecutive live attempts, one fully end-to-end (real file, real content).

### 9. Model name centralized, SSH push properly diagnosed

Item 1's bug was possible because the model name was hardcoded independently in 7 files. Closed it: all 7 now import `FAST_MODEL`/`STRONG_MODEL` from `routing.py` — confirmed zero hardcoded model-name strings remain anywhere else. Live-verified with a full `/chat` request post-refactor.

Separately, investigated the SSH push failure instead of re-reporting it: a real, valid key exists on the machine — the issue is no `ssh-agent` running to hold the unlocked key, not a broken key. Attempted `ssh-add`, hit the correct passphrase prompt, stopped there — never asked for or accepted a passphrase through the session. **The fix is one command in Prudhvi's own terminal**: `ssh-add ~/.ssh/id_ed25519`, then `git push origin main` works normally.

### 10. Second Tool/Skill expansion — `list_files`, fuzzy file lookup

"File not found" had been the most common permanent Tool/Skill failure all session. Added `ListFilesTool`/`list_files` (5th Tool) and `FindAndDigestFileSkill` (5th Skill), composing a new `FindFileStep` (deterministic fuzzy matching, named `"filename"` so its output lands exactly where the *existing* `ReadFileStep` expects it) with `ListFilesStep` (new) + `ReadFileStep`+`SummarizeStep` (existing, reused). **A real matching bug caught before shipping**: the first version of `FindFileStep` passed every unit test with short, filename-like candidates but failed twice live on realistic full-sentence prompts ("summarize my jazz file for me") — whole-sentence-vs-filename character matching is too crude. Fixed with a token-level fallback (strip filler words, match individual words against each filename's stem); re-verified both previously-failing prompts now succeed fully end-to-end.

**Capability inventory as of this item**: 5 Tools (`code`, `file`, `web`, `write_file`, `list_files`), 5 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`, `find_and_digest_file`).

### 11. Frontend verified live (old UI) — a real CORS bug found and fixed

The frontend hadn't been touched since well before Phase A. Checked whether it still worked rather than assuming: routes and response shapes still matched. One real gap surfaced — every test all session had omitted `project_id`, meaning none of Phase E1–E3 or either Tool/Skill expansion had been exercised through the actual project-scoped flow the real frontend uses.

**Real bug found on first page load**: genuine CORS errors — the frontend hardcodes port 8000, which this machine's other project (`stud-os`) was occupying; Aether's own CORS config was fine. Fixed properly: `API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000"` in all fetch calls, defaulting to the original value.

Live-verified via a real browser (Playwright, not curl): real project + chat history loaded with visible memory recall, sent a brand-new message, got a correct answer, confirmed via backend logs and the DB. **First time this whole session's backend work was exercised through the real UI rather than curl.** Also confirmed the production build (`npm run build`) compiles cleanly and serves correctly with the env var set.

*(This UI was then fully rebuilt from scratch the same session — see item 12.)*

### 12. API extended, frontend rebuilt from scratch, and a real dispatcher gap found through the new UI

Prudhvi's ask: the old UI (item 11) was a bare CRUD shell that didn't reflect any of what had actually been built — no visibility into which Tool/Skill handled a request, no way to see what Aether can even do. Asked for a full rebuild.

**Backend prerequisite**: `/chat` always computed `the_plan` (capability_type, capability_name, source) and `decision` (attempts, escalated) but never returned any of it. Extended the response to include all five fields alongside the existing `model_used`. New `GET /capabilities` returns `{tools, skills}` straight from the same registries the Planner itself queries — not a hand-maintained list that can drift. Live-verified both: a real `/chat` request now returns `capability_type: reasoning, capability_source: llm, attempts: 1, escalated: false`; `/capabilities` returns real tool/skill descriptions matching the registries.

**Design concept**: Aether's real architecture *is* a pipeline — Plan → Capability → Validate → Deliver. Made that pipeline the UI's signature visible element instead of a generic chat bubble: a small trace under each AI response reading `plan·llm → skill:research_and_save_file → qwen3.5:9b → ok` (or `retried ×1` / `escalated` when that's what happened). Dark, technical "instrument panel" palette (deep graphite-blue, not pure black or the generic cream/terracotta default) with a calm cyan system accent and distinct amber/coral for retry vs. escalation, so warning states carry real meaning. Monospace (JetBrains Mono) reserved for system/capability labels — literal identifiers; humanist sans (IBM Plex Sans) for actual conversation — a content-driven pairing, not arbitrary. New Capabilities panel (sidebar button) lists every registered Tool and Skill with real descriptions and step sequences, live from `/capabilities`.

Structure: split the single-file `App.js` into `api.js` (centralized fetch calls) and `components/` (`Sidebar`, `ChatWindow`, `CapabilityTrace`, `CapabilitiesPanel`). All original working logic (project/chat loading, message history, chat_id registration) preserved exactly, not rewritten.

**Live-verified, real browser (Playwright)**: `npm test` passes (replaced a stale default-CRA test), `npm run build` compiles cleanly, real project + chat history loaded unchanged, sent a fresh message that triggered `research_and_save_file` — the trace rendered exactly as designed and the skill genuinely executed (a real file was saved), opened the Capabilities panel and confirmed all 5 Tools and 5 Skills show with live descriptions, confirmed panel close works. `run.sh` re-verified working unchanged against all of this.

**A real, previously-undiscovered bug found through this new UI, not through curl**: asking "List the files in the workspace" through the actual UI correctly got planned as `tool:list_files`, but silently escalated with `empty_response`. Root cause: `execute_plan()`'s `tool` capability_type branch calls `execute_plugin()` (`plugin_manager.py`) — a dispatcher with hardcoded if/elif branches that **predates `write_file` and `list_files` entirely**. Every earlier test of those two tools went through a Skill (`ResearchAndSaveFileSkill`, `FindAndDigestFileSkill`), which calls the Tool objects directly via the registry, completely bypassing this dispatcher. Selecting either tool *directly* (not via a Skill) fell through every branch to a bare `return None`.

**Fixed**: added `write_file` and `list_files` branches to `execute_plugin()`. `write_file` extracts a filename (`extract_filename()`, falling back to `slugify_filename()`) and content (new `extract_write_content()` in `extraction.py`, same pattern as `extract_search_query()`/`generate_code()`); `list_files` just calls the tool directly, no input needed. **Caught and fixed a mistake in my own first edit attempt along the way**: an overly-broad match deleted `generate_code()`'s entire function body — caught by reading the file back before assuming the edit landed, not by trusting the tool call succeeded.

**Live-verified, both branches, through the real API and then the actual browser UI**:
- `"List the files in the workspace"` → `capability_type: tool, capability_name: list_files, attempts: 1, escalated: false`, real file listing returned.
- `"Save the text hello from claude to a file called claude_test.txt"` → `capability_type: tool, capability_name: write_file, attempts: 1, escalated: false`, `"Saved to claude_test.txt (17 bytes)."` — read the actual file back and confirmed the content is exactly right, not garbled.
- Re-tested `"List the files in the workspace"` through the real browser UI (the same way the bug was found) — trace correctly shows `plan·llm → tool:list_files → qwen3.5:9b → ok`, real listing including the newly-written `claude_test.txt`.

**Two run.sh instances were accidentally left running simultaneously** at one point this session (likely started twice in different terminal tabs) — stopped both cleanly and started one fresh instance before continuing, to avoid ambiguity about which backend the frontend was actually talking to.

## What's already right — keep these

- **Registry-driven decision prompt** (E1) — resist ever hardcoding tool/skill names back into a decision prompt; if a new capability needs special-casing in `planning_service.py`, something's wrong with that capability's `description`, not the Planner. Proven again this session: both new Skills were selectable from natural language the moment they were registered.
- **Model selection vs. capability selection as two separate calls** — matches `ARCHITECTURE.md`'s service boundaries.
- **Graceful multi-layer fallback (LLM → rule → reasoning)** — kept the system usable through Ollama being down, and (double-edged) is exactly what let the model-name bug go unnoticed for as long as it did.
- **Validation and Decision as two separate concerns** — `validate_response()` only classifies; `decide()` only acts on that classification.
- **`experiences.tool_source`** is the one reliable signal for "did the live LLM actually get used" — check it, don't guess from the reply.
- **Compose existing Steps into a new Skill rather than writing new logic** — every new Skill this session reused existing Steps unchanged and added exactly one new piece.
- **A bare `except Exception: return None` can hide a completely broken integration, not just "no results this time."** — the Wikipedia fallback's first version silently ate a 403.
- **Unit tests with clean, short inputs aren't enough for anything that will receive natural language.** `FindFileStep` passed every unit test and still failed live, twice, on realistic sentences.
- **A brand-new UI surface can expose bugs that unit/API tests never would.** The `execute_plugin()` gap (item 12) existed since `write_file`/`list_files` were added, survived every earlier live test, and was only found by clicking through the actual UI with a natural prompt a real user would type. When adding a new interaction surface, re-test old capabilities through it — don't assume passing tests elsewhere means it's covered.
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable — apply the same pattern to future LLM-judged checks.

## Known gaps

- `think` hardcoded off everywhere via a default parameter. Fine for now; revisit only if answer quality on hard questions becomes a real concern, with the same live-proof discipline.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage's actual duration.
- `validate_response_llm()` is observability-only by design — whether/when to promote it to actually gate delivery is an open, deliberate decision.
- `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) the way `Step` has via `ScriptMeta`. Not urgent until governance (Phase F+) needs it.
- Web search still isn't 100% reliable on very messy phrasing (real, honest residual limit, not a regression).
- Push to `origin/main` needs a passphrase entered locally (`ssh-add ~/.ssh/id_ed25519`) each session — not something a future session can fix remotely.
- The new UI's "New Project" flow still uses `window.prompt()` (a native browser dialog) rather than a proper in-app modal — functional, not polished. Flagged, not fixed, this session.
- The UI doesn't yet surface `llm_validate` (the opt-in LLM-based validation flag) or project memory context — both exist in the backend but aren't exposed in the new UI yet.

## Immediate next action

Enter the SSH key's passphrase locally (`ssh-add ~/.ssh/id_ed25519` in your own terminal, not through this session) and push `origin/main` — everything through `f10d6fc` is committed and waiting. Then decide: run `llm_validate` on real traffic before considering enforcement, keep expanding the Skill/Tool set, or polish the new UI (project-creation modal, surfacing memory/llm_validate). See `HANDOFF.md` for the full session-transition brief.

## Earlier phases (condensed — see git history for full detail)

**Phases A–D, E0**: pooled SQLAlchemy DB, removed `eval()`, sandboxed code execution, allowlisted file access, Alembic migrations, structured logging, unified routing, LLM-based memory extraction with upserts, formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table, Step/Skill abstraction with real `Script`/`Validation`/`Metrics` (`ScriptMeta`, `Step.validate()`, `step_metrics` table), 3 original Skills (`research_topic`, `file_digest`, `calculate_and_explain`), and a fix for `generate()` vs `generate_strict()` misuse in the code-gen/query-extraction paths.

**E1 — the Planner** (`eb874c7`): `services/planning_service.py`, registry-driven capability selection. Model selection split out of `routing.py` into its own concern (`select_model()`). Graceful degradation chain: LLM decision → rule-based fallback → raw reasoning.
