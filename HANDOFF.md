# Handoff: Aether AIOS — architecture review, security hardening, Phase A–E3 implementation, Tool/Skill expansion, frontend rebuild, llm_validate real-traffic eval, AppImage packaging, Settings + full multi-modal support

## Goal

Prudhvi is building Aether: a chatbot MVP evolving toward an AI Operating System (AIOS) — intelligence as reusable kernel services (Tools, Skills, Planning, Validation, Decision, Governance, etc.) rather than logic embedded in one agent. Full vision: `ARCHITECTURE.md` in the repo. Every phase below was implemented with live verification, not just planning — read `STATUS.md` for the full evidence behind each claim here.

## Status

**Phases A through E3 are implemented and fully complete.** 5 Tools, 5 Skills. The frontend shows a live capability/decision trace, historical traces, `llm_validate` verdicts, project memory, a New Project modal, and — new this session — a Settings panel (model override, default-validate). **Full multi-modal support**: images (auto-downscaled client-side), plain-text documents, and PDF/DOCX (native text extraction, vision-model OCR as a fallback for scanned PDFs) can all be attached to a chat message. **Packaged as a self-contained AppImage** (`packaging/appimage/`, `~/Aether-x86_64.AppImage`) — every feature above has been live-verified against the actual packaged build, not just the dev environment.

**Push status, precisely** (Prudhvi confirmed the push landed once, partway through item 13 — everything since across two full sessions is new local commits, not yet re-confirmed):
- `ebf40a3` through `1b21f67` — confirmed pushed to `origin/main`
- `961e2b6` through `900ff91` (16 commits) — committed locally, **push not confirmed**
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

**Capability inventory**: 5 Tools (`code`, `file`, `web`, `write_file`, `list_files`), 5 Skills (`research_topic`, `file_digest`, `calculate_and_explain`, `research_and_save_file`, `find_and_digest_file`). Plus (not Tools/Skills, a parallel capability): image, text-file, and PDF/DOCX attachments on any chat message, all routed straight to reasoning (skip planning) on the vision-capable model when an image is present.

## This session's findings, in order

1. **Model-name bug.** Every LLM call site hardcoded model names that don't exist on this machine. Fixed across 7 files.
2. **Latency variance, root cause found.** `qwen3.5:9b`'s hybrid thinking mode ran unbounded on every call — 37x speedup fixing it.
3. **E2 (Validator), first check.** `services/validation_service.py` as single source of truth for failure-string detection.
4. **E3 (Decision), first pass.** `services/decision_service.py`: retry once if retryable, escalate otherwise.
5. **E3 follow-up: retry backoff, with a self-caught correction.** First live verification attempt overclaimed a result — corrected with a deterministic test.
6. **E2 completed: LLM-based validation, opt-in and observability-only.** `validate_response_llm()`.
7. **`services/router.py` deleted.** Dead duplicate with the original model-name bug.
8. **First Tool/Skill expansion.** `write_file` + `ResearchAndSaveFileSkill`. Found `web_search` failing on real prompts.
9. **DuckDuckGo + query-extraction fragility, fixed same day.** Tightened extraction; added a Wikipedia fallback.
10. **Model name centralized; SSH diagnosed** (real key, just needs a local passphrase entry).
11. **Second Tool/Skill expansion: `list_files` + fuzzy file lookup.** Closed the most common permanent failure.
12. **API extended, frontend rebuilt from scratch.** Live capability trace as the signature UI element. Found and fixed a real dispatcher gap (`execute_plugin()` had no `write_file`/`list_files` branches) through the new UI.
13. **`llm_validate` run on real traffic for the first time.** 18/18 judged responses agreed with an independent read. Found and fixed two more real bugs the traffic surfaced (filename-override bug, a 500 crash in two Skills).
14. **Both item-13 issues fixed, plus a UI polish batch** — `calculate_and_explain`'s confusion bug, memory bleed-through (prompt-level mitigation), historical capability traces, `llm_validate` UI, Memory panel, New Project modal.
15. **Packaged as a self-contained AppImage.** Found and fixed a real bug while generating the seed DB: the baseline Alembic migration had always been a no-op, so bootstrapping a genuinely fresh Aether database had *never* worked or been tested — every session before this built on the one pre-Alembic dev database. Fixed with idempotent table creation, verified safe both fresh and against a copy of the real dev DB. Also found and fixed a second real bug by testing shutdown, not just startup: `AppRun` backgrounded its server processes inside bash subshells without `exec`, so killing the tracked PID killed a wrapper and orphaned the real process — it never actually stopped. `packaging/appimage/build.sh` reproduces the whole build end-to-end, not a one-off manual process.
16. **UI polish round 2**: fixed the validate toggle (root-caused via DOM measurement — it was a disconnected, unstyled native checkbox, not just "looks off"); added a Settings panel (model override live from a new `GET /models`, default-validate, both backend-wired not filler); added full multi-modal image support (checked `GET /api/tags` for vision capability before building anything, forces the vision model and skips planning for image-attached requests); added drag-and-drop. **Found and fixed a real bug from Prudhvi's own independent use** (not a synthetic test): large real photos consistently timed out during vision inference — fixed with a longer image-specific timeout as a safety net, and client-side downscaling as the actual fix (2MB → ~215KB). Also surfaced two real lessons about testing methodology itself — see `STATUS.md` item 16 and the Environment notes below.
17. **Document attachments.** Prudhvi: "I can't upload anything except image files" — real gap, the composer only accepted `image/*`. Added plain-text file support first (zero new dependencies), then PDF/DOCX after Prudhvi asked directly which approach was best ("unlimited OCR vs libraries, do whatever is best") — went with **libraries first (PyMuPDF, python-docx), vision-model OCR only as a fallback for genuinely scanned PDFs**, not a bundled OCR engine, reasoned out in `STATUS.md` item 17. Verified live through the actual UI with three real files (native PDF, DOCX with a table, and a genuinely scanned PDF confirmed to have zero extractable text before testing) — all three correct. Rebuilt the AppImage with the new dependencies and re-verified against the packaged build.

Full detail, including every verification step and exact commands, is in `STATUS.md` — read that, not just this summary, before treating any of this as settled.

## Uncommitted changes (as of this handoff)

None — working tree is clean. Everything through `900ff91` (item 17) is committed locally. 16 commits (`961e2b6` through `900ff91`) are outstanding for push — see "Push status" above.

## Key decisions

- **`ScriptMeta` is versioned identity metadata, never executable code-as-data.**
- **Model selection and capability selection are two separate calls.**
- **The Planner's decision prompt is built dynamically from the live registries**, not hardcoded.
- **`generate()` vs `generate_strict()`**: `generate()` for a human to read directly; `generate_strict()` for any automated caller checking success programmatically.
- **Validation and Decision are two separate concerns.**
- **The graceful fallback chain can hide total live-LLM failure indistinguishably from healthy degradation.** Check `experiences.tool_source` directly.
- **A new probabilistic check doesn't have to gate behavior on day one.** `validate_response_llm()` is observability-only until proven reliable.
- **Compose existing Steps into a new Skill rather than writing new logic.**
- **Not every Step's output is human-facing text.** `WriteFileStep` returns a string for the user; `SaveMemoryStep` returns structured data. The Skill→response boundary is where that gets bridged.
- **Labeling matters as much as content in a local-LLM prompt.** Same stored rows, different framing, meaningfully different model behavior.
- **A new interaction surface can expose bugs old tests never would.** Proven three separate times now: `execute_plugin()`'s missing branches (item 12), the AppRun shutdown bug (item 15, found by testing shutdown not startup), and the image timeout (item 16, found by Prudhvi's own independent real-world use, not a synthetic test).
- **An attached image or file skips Tool/Skill planning entirely** (`Plan(capability_type="reasoning", source="rule")`) — none of the current Skills know what to do with image bytes or inline file content, so letting the LLM planner route one into e.g. `calculate_and_explain` would be nonsensical rather than just wrong.
- **Libraries first, model capability as a fallback, not a bundled special-purpose dependency.** Item 17's PDF/DOCX decision: PyMuPDF/python-docx handle the common case exactly and instantly; the vision model (already tested, zero new binary dependency) handles the rare scanned-document case, instead of bundling Tesseract into a self-contained AppImage for something most documents don't need.
- **Check installed capability before choosing a design.** `GET /api/tags`'s `capabilities` field settled both the vision-model and PDF/DOCX questions before any code was written.
- **A synthetic test built by manually retyping a long encoded string is a real corruption risk.** Two hand-embedded copies of the same base64 string differed by 396 characters in item 16 — fetch real bytes instead whenever a test needs exact fidelity.
- **A dev frontend pointed at an already-built AppImage's backend produces confidently wrong results.** The squashfs bundle is frozen at build time regardless of what the frontend's env vars claim to be doing.

## Relevant files & artifacts

- `~/Projects/Aether` — the repo (local, git-tracked; `origin/main` confirmed through `1b21f67`; 16 more commits sit on top locally, working tree clean, see "Push status")
- `~/Aether-x86_64.AppImage` — the packaged build (not in git, gitignored) — rebuild with `./packaging/appimage/build.sh` after any source change
- `ARCHITECTURE.md` — target AIOS vision, mapped against current code, gap-by-gap
- `STATUS.md` — current state, resolved items with live-verification notes, known gaps — **read this first**
- `ROADMAP.md` — phased checklist, dependency-ordered, checkboxes reflect actual completion
- `run.sh` — starts Ollama + backend + frontend together for local dev
- `packaging/appimage/` — `build.sh` (reproduces the whole AppImage from source), `AppRun` (the packaged launcher), `Aether.desktop`, `aether-icon.svg`, `.cache/` (gitignored, appimagetool)
- Backend key modules: `services/planning_service.py`, `services/validation_service.py`, `services/decision_service.py`, `services/tools/`, `services/skills/`, `services/steps/` (esp. `summarize_step.py`), `services/reasoning_service.py`, `services/extraction.py`, `services/routing.py` (`FAST_MODEL`/`STRONG_MODEL`/`VISION_MODEL`), `services/ollama_service.py` (memory-prompt framing, `IMAGE_REQUEST_TIMEOUT_SECONDS`), `services/document_extraction.py` (PDF/DOCX extraction + OCR fallback), `plugins/web_search.py`, `alembic/versions/44f9e98b07f2_*.py` (chats capability-trace columns), `alembic/versions/cb702a809575_*.py` (the fixed baseline migration)
- Frontend key modules: `frontend/src/App.js`, `frontend/src/api.js`, `frontend/src/settings.js` (localStorage persistence), `frontend/src/components/` (`Sidebar`, `ChatWindow`, `CapabilityTrace`, `CapabilitiesPanel`, `MemoryPanel`, `NewProjectModal`, `SettingsPanel`), `frontend/src/App.css`, `frontend/src/index.css` (design tokens)
- Backend venv at `backend/.venv` (SQLAlchemy, Alembic, structlog, PyMuPDF, python-docx — not system Python); `backend/requirements.txt` is the frozen, reproducible record (didn't exist before item 15)

## Next steps

1. **Push the 16 outstanding commits** (`961e2b6` through `900ff91`) — `ssh-add ~/.ssh/id_ed25519` locally, then `git push origin main`.
2. Decide direction for what's next (Prudhvi's call):
   - Run a **larger, more adversarial `llm_validate` batch** before considering enforcement — 18/18 agreement so far is promising but small-sample
   - Keep expanding the Tool/Skill set
   - **Tune the unmeasured guesses from items 16–17**: image downscale target (1280px/JPEG 0.85), OCR page cap (5), file-context budget (~50k chars) — none tested against an actual quality complaint or failure, just picked as reasonable defaults
   - Add a UI affordance for truncation/page-cap situations — currently invisible to the person attaching a large document
3. Known gap, not urgent: `Tool` and `Skill` objects still lack the AI Object Model's full metadata that `Step` has via `ScriptMeta`.
4. Real design gap, not urgent: the memory bleed-through fix (item 14) is prompt-level, not structural.
5. Minor cleanup, not urgent: test/debug projects have accumulated across two separate databases now (dev + AppImage) — harmless.

## Open questions

- No decision made yet on whether/when to tackle the Tool/Skill AI Object Model gap.
- Whether `think` should ever be enabled. Not urgent.
- Whether/when to promote `validate_response_llm()` from observability-only to enforcement — still small-sample.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not measured against a real outage.
- Web search still isn't 100% reliable on very messy phrasing — real, honest residual limit.
- Whether the memory bleed-through fix needs to go further than prompt framing.
- Whether the image-downscale/OCR-page-cap/file-context-budget numbers need tuning — no measured basis yet, just reasonable-sounding defaults.

## Suggested skills

- **`systematic-debugging`** — don't accept a surface explanation once it's contradicted by evidence. Found the model-name bug, the `think`-mode root cause, DuckDuckGo fragility, the `FindFileStep` matching bug, the `execute_plugin()` gap, `calculate_and_explain`'s missing context, memory bleed-through, the baseline-migration bootstrap bug, the AppRun shutdown bug, and the image-timeout root cause this way.
- **`verification-before-completion`** — strict "test live, don't claim done without proof" discipline. This session's clearest example: two "Failed to load image" reproductions were accepted as the real bug before a byte-level diff revealed the test data itself was corrupted — redone with real fetched bytes before drawing any conclusion.
- **`frontend-design`** / **`ui-styling`** — used for the UI rebuild and every polish round since: brief-driven design tokens, reusing established patterns (`.panel-overlay`/`.panel`, `.trace-chip`) for new surfaces rather than inventing one-off styles.

## Environment notes for the next session

- Desktop Commander access to `~/Projects/Aether`, plus direct process control via `start_process`/`interact_with_process`. Background processes started with plain `nohup ... & disown` get killed when the parent shell session is recycled — use `setsid nohup ... < /dev/null &` instead, or just use `run.sh`, which already handles this.
- **This machine reboots or otherwise loses all running processes unpredictably, sometimes mid-conversation** — `uptime` has shown as little as 8–14 minutes multiple times across two sessions now, not just at session boundaries. Never assume anything is still running: `ps aux | grep -E "run.sh|uvicorn|react-scripts|ollama|mount_Aether"` first, restart clean if empty. **Ollama specifically has gone down silently between turns more than once** — a request that returns `ollama_unreachable` in the backend log isn't necessarily a code bug, check `curl localhost:11434/api/tags` and restart it (`ollama serve &`) before assuming otherwise. `/tmp` gets cleared in the same events — recreate scratch files rather than assuming they survived. Git commits and the source tree are unaffected.
- **A dev frontend pointed at an already-built AppImage's backend produces confidently wrong results when iterating on a backend fix.** The AppImage's backend is a frozen squashfs copy from build time — a source-level fix won't be reflected there no matter what `REACT_APP_API_URL` claims. When testing a backend change, either run a fresh dev backend (`cd backend && .venv/bin/uvicorn main:app --reload --port <free-port>`) and point the dev frontend explicitly at it, or verify via `curl`/log inspection which literal process actually answered the test request before trusting the result.
- **The user's own AppImage instance may be running and in active use — don't kill it to free ports.** Check `ps aux | grep mount_Aether` before assuming ports 8000/3000 are free; if occupied, run a dev backend/frontend pair on different ports (e.g. 8020/3001) instead of stopping what the user's looking at. Rebuild and relaunch the AppImage only after confirming changes work in the dev environment first.
- **When testing something that needs exact byte fidelity (base64, binary file contents), never manually retype or hand-embed the data across tool calls.** A ~5700-character base64 string got silently corrupted this way (two copies differed by 396 characters) and produced a real-looking but misleading error. Use `fetch()` on a real served file, `setInputFiles` with a real file path, or `read_file`/`cat` on an actual file — anything that moves bytes without a human (or an LLM) re-serializing them as text in between.
- **A Playwright browser session can get stuck behind a stale `SingletonLock`** from a previous session's crashed/killed Chrome process (`~/.cache/ms-playwright-mcp/mcp-chrome-*/SingletonLock` etc.) — shows up as "Browser is already in use." Check if any process actually holds it (`ps aux | grep mcp-chrome`); if not, just delete the lock files and retry.
- **A stale Chrome/GTK native file-picker cache is a real, observed issue on this machine, outside Aether's control.** Prudhvi's file-picker dialog showed only 6 months-old files while the real directory had 100+ current ones — confirmed not a sandboxing/permissions issue (native Chrome, correct `XDG_DOWNLOAD_DIR`). Workaround: type a full path into the dialog's "Name:" field, or just use drag-and-drop (bypasses the native picker entirely, which is part of why it was added).
- **The Desktop Commander MCP server itself has gone unresponsive mid-session repeatedly across every session so far** — every tool call, including trivial ones, timing out at 4 minutes. Distinct from the app stack dying. Just retry the same simple call every so often until it responds again.
- `edit_block`'s find/replace occasionally rejects an edit with a generic "must provide old_string+new_string" error on a call that does provide both — works on immediate retry with the same or simplified content. New files need `desktop-commander:write_file`, not `edit_block` (existing files only) or the sandboxed `create_file`/`str_replace` tools (those write to Claude's own container, not the real machine).
- Long-running local LLM calls (especially vision/OCR ones, up to ~180s now for images) can exceed the MCP tool layer's own ~4 minute call ceiling — launch with `nohup bash -c '...' > logfile &` and poll the logfile with short `sleep N; cat logfile` calls, or check the backend's own log file directly rather than waiting synchronously on a single tool call.
- Commit messages with apostrophes/quotes inside a `bash -c "..."` git commit `-m` string reliably break — write the message to a temp file (`desktop-commander:write_file`) and use `git commit -F <file>` instead.
- To run everything: `~/Aether-x86_64.AppImage` (packaged) or `./run.sh` (dev) from the repo root.
