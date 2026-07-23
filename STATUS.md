# Aether — Current Status

_Last updated: July 23, 2026, after settling E1's live-LLM latency variance, shipping E2's first deterministic Validator check, shipping E3's bounded retry/escalate Decision step, and adding retry backoff to E3 (with a self-caught correction on the first, wrongly-attributed verification attempt — see the narrative below). Update this file whenever a Critical/Important item is resolved or a new one is found._

**Continuing in a new session? Read `HANDOFF.md` first — it's the compact version of everything below.**

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete. E0 + E1 complete and live-verified (fast, reliable). E2 (first deterministic check) and E3 (bounded retry/escalate, now with backoff) both live and proven.** |
| Commits | `ebf40a3` (model-name + `think` + timeout + E2) and `62002a9` (E3 first pass) both committed and pushed to `origin/main` — Prudhvi pushed these after the earlier SSH failure in this session. **Uncommitted on top**: E3's retry backoff (`RETRY_DELAY_SECONDS`, `time.sleep()` in `decision_service.py`). |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration and test run across all sessions |
| Critical blockers | 0 |
| Next phase | Rest of E2 (LLM-based validation) / expand the Skill set — Prudhvi's call |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.
Ollama must be running (`ollama serve`) with `qwen3.5:9b` and `qwen3-coder:latest` pulled — these are the only two models the codebase now references. **Note**: on this dev machine, both `ollama serve` and the backend process have died between every multi-hour gap in sessions (survived a shell/session recycle, not a reboot) — always re-check `curl localhost:11434/api/tags` and the backend's own `/` before assuming either is still up.

## Session narrative — 2026-07-21/22, in order

### 1. Model-name bug (the real reason the live-LLM path was never tested)

The prior session correctly flagged "run one real test with Ollama up" as the top priority — Ollama had been down the entire session. Starting Ollama up revealed the real blocker was worse: **every LLM call site in the backend hardcoded `"llama3"` or `"mistral"` as the model name — neither is installed.** Only `qwen3.5:9b` and `qwen3-coder:latest` are pulled on this machine. So even with Ollama running, every live call failed instantly on `"model 'X' not found"`, caught by `generate_strict()` as a `ReasoningError`, silently routed to the offline fallback — indistinguishable from Ollama being down at all.

Proven live: first test request returned `"Error from mistral: {'error': \"model 'mistral' not found\"}"` verbatim as the chat response; the `experiences` row logged `tool_source: fallback` at 1.7ms (instant failure, not a real attempt).

**Fixed across 7 files** to use the two models actually installed (`qwen3.5:9b` for decisions/reasoning/extraction, `qwen3-coder:latest` for code generation): `routing.py`, `planning_service.py`, `plugin_manager.py` (3 call sites), `extraction.py` (2 call sites), `memory_extraction.py`, `services/steps/summarize_step.py`, plus the misleading `model="llama3"` defaults in `reasoning_service.py`/`ollama_service.py`.

**Not fixed, flagged for cleanup**: `services/router.py` is a dead, zero-caller duplicate of `routing.py`'s old logic, with the same broken model names. Recommend deleting — didn't do so unilaterally since it's a file removal, not a bug fix.

### 2. Latency variance — root cause was `think` mode, not timeout or hardware

After the model-name fix, decision-call latency for the identical prompt swung 45s–150s+ across repeated tests. First attempt at a fix (raise `REQUEST_TIMEOUT_SECONDS` 60→150) bought exactly one successful full response and didn't fix the underlying flakiness — the real signal that this was a symptom, not the cause.

Investigated properly: `qwen3.5:9b` is a hybrid **thinking** model (`ollama list` shows `"capabilities":[...,"thinking"]`), and the Ollama request payload never set the `think` field. Proved with a controlled A/B — identical decision prompt, identical correct output (`"none"`):

| `think` | latency | hidden reasoning trace |
|---|---|---|
| unset (previous default) | 30.9s | 369 chars |
| `false` (explicit) | 0.8s | 0 chars |

**37x speedup, same correctness.** The variance was the model running an unbounded internal reasoning trace on every call, including one-line classification prompts that need zero reasoning. Not reload cost, not hardware limits — proven, since 150s still wasn't always enough.

**Fix**: `ollama_service.generate_response()` now takes `think: bool = False`, passed explicitly to Ollama's API, defaulting off everywhere. `REQUEST_TIMEOUT_SECONDS` restored to 60. Re-verified live: 3 consecutive identical requests, all `tool_source: llm`, all `success: true`, 5.1–6.1s each. No more flakiness, no more fallback-on-timeout.

**Worth deciding later, not urgent**: `think` is off everywhere now, including for real chat answers — the right default for latency, but means Aether never uses its reasoning capability even on hard questions. Consider an opt-in `think=True` for a future "powerful" mode if answer quality on hard questions ever becomes a concern — don't flip the default back without the same kind of live proof this fix required.

### 3. E2 — first deterministic Validator check

`main.py` already computed a `success` flag from a hardcoded failure-string-prefix list for the experience log — but never used that knowledge to protect the `response` actually delivered to the user. The detection existed; nothing acted on it. The same list was also duplicated, slightly differently, in `reasoning_service.py` — the identical "one fact, N hardcoded copies" pattern that caused the model-name bug.

Built `services/validation_service.py` as the single source of truth: `FAILURE_PREFIXES` (reasoning-layer + tool/skill-layer failure strings) and `validate_response()`. `reasoning_service.py` now imports the reasoning-only subset instead of keeping its own copy.

A real bug in the first wiring attempt was caught live, not assumed clean: an import-rename left one stale reference in `reasoning_service.py`, surfacing as an HTTP 500 the moment it was tested. Fixed, modules re-verified to import cleanly, re-tested successfully.

Verified live, both directions: normal request → passes validation unchanged; Ollama stopped mid-session → `generate()` returned `"Could not reach Ollama..."`, validator caught it, user received a clean message instead of the raw internal string.

*(This endpoint wiring was later superseded by E3 below — `main.py` no longer calls `validate_response()` directly, it delegates to `decide()`, which calls validation internally.)*

### 4. E3 — bounded retry + escalate, live-proven on all three paths

Built directly on E2: `validate_response()` now also classifies each known failure as `retryable` or not — e.g. `"Could not reach Ollama"` is transient (worth a retry), `"File not found"` is permanent (retrying the identical call fails identically, don't bother). New `services/decision_service.py` owns the policy: run one attempt, validate, retry once if retryable, escalate to a clear honest message if still invalid after that. `main.py`'s `/chat` endpoint now delegates entirely to `decide()`.

**Live-verified, all three paths, exact matching log + DB evidence**:

| scenario | attempts | retryable | outcome |
|---|---|---|---|
| normal request, Ollama up | 1 | n/a | delivered normally, `tool_source: llm`, `success: true` — unchanged from before E3 |
| request a nonexistent file | 1 | false | escalated immediately, no wasted retry (1.8s total), `decision_escalated` logged with `retryable: false` |
| Ollama stopped for the whole request | 2 | true | one retry fired (`decision_retry`, `attempt_number: 2`), then escalated when the retry also failed (`decision_escalated`, `retryable: true, attempts: 2`) |

**Known gap, honestly flagged**: retries fire with **zero backoff** — in the Ollama-down test, both attempts completed within milliseconds of each other. Fine for slowness (a retry gets a fresh timeout budget); useless for a genuinely-down-for-a-moment Ollama, since the retry hits the identical dead window. Didn't chase an artificial timing demo to "prove" recovery the current design can't actually deliver — worth adding a short delay (1–2s) before retrying if this matters in practice.

**Scope boundary, explicit**: bounded retry + escalate only, matching the roadmap's own framing. No exponential backoff, no configurable retry count, no per-capability-type policy beyond what the failure-prefix taxonomy already encodes.

### 5. E3 follow-up — retry backoff added, with an honest correction

Closed the gap above: `decision_service.py` now waits `RETRY_DELAY_SECONDS = 2.0` before the retry attempt, so a real transient outage gets an actual chance to clear instead of the retry hitting the identical dead window instantly.

**First verification attempt overclaimed a result — corrected here rather than left standing.** Tried to prove recovery live: killed Ollama, then launched a chat request and `ollama serve` at nearly the same instant, expecting the retry to land after Ollama came back up. The request *did* succeed (24.8s, correct answer, "The capital of Italy is Rome"), but checking the full log for that request showed **no `decision_retry` and no `ollama_unreachable` event at all** — the very first attempt succeeded outright. What actually happened: enough real time had already elapsed across the sequence of tool calls (kill → confirm down → launch) that Ollama's HTTP listener was already up by the time the request's first attempt ran; the 14.7s the Planner's own decision call took was cold-model-load time, not a failed connection. A good outcome, wrong mechanism — this did not test the retry path at all, and claiming otherwise would have been exactly the kind of unproven claim this project has been explicit about avoiding.

**Corrected with a deterministic test instead of relying on live infra timing**: called `decide()` directly with a controlled fake `attempt_fn` that fails once (returns a known transient-failure string) then succeeds. Result: `attempts: 2`, `valid: True`, `escalated: False`, response is the recovered value — and the measured gap between the two calls was exactly `2.0s`, matching `RETRY_DELAY_SECONDS`. This is the actual proof that the retry-with-backoff mechanism works, independent of whether a live Ollama restart happens to land in the window or not.

The plain "Ollama down for the whole request" scenario (E3's original three-path table above) was re-confirmed with the delay in place: total request time is now ~2.0s instead of ~1.6ms, matching the added `time.sleep(2.0)` exactly.

## What's already right — keep these

- **Registry-driven decision prompt** (E1) — the actual architectural upgrade. Resist ever hardcoding tool/skill names back into a decision prompt; if a 4th capability needs special-casing in `planning_service.py`, something's wrong with that capability's `description`, not with the Planner.
- **Model selection vs. capability selection as two separate calls** — matches `ARCHITECTURE.md`'s service boundaries. Don't re-merge them for convenience.
- **Graceful multi-layer fallback (LLM → rule → reasoning)** — kept the system usable through Ollama being fully down for an entire prior session, and (double-edged, see below) is exactly what let the model-name bug go unnoticed for as long as it did.
- **Validation and Decision as two separate concerns** (E2/E3) — `validate_response()` only classifies; `decide()` only acts on that classification. Don't collapse them for convenience the same way model/capability selection shouldn't be collapsed.
- **`experiences.tool_source`** is the one reliable signal for "did the live LLM actually get used" — response text alone degrades too gracefully to tell. Check it, don't guess from the reply, whenever verifying live-LLM behavior specifically.

## Known gaps

- Model name is a hardcoded pair (`qwen3.5:9b` / `qwen3-coder:latest`) duplicated across 7 files rather than defined once. Worth centralizing into `routing.py`'s constants and importing everywhere — the model-name bug was made possible by there being 7 places to get it wrong instead of one.
- `services/router.py` — dead file, same model-name bug, not deleted. Zero callers, but a landmine if anyone ever imports it by mistake.
- `think` hardcoded off everywhere via a default parameter. Fine for now; revisit only if answer quality on hard questions becomes a real concern, with the same live-proof discipline.
- `RETRY_DELAY_SECONDS = 2.0` is a guess, not a measured value — chosen as "long enough to plausibly clear a brief restart, short enough not to hurt perceived latency," never validated against a real outage's actual duration. Revisit with real data if it matters.
- `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) the way `Step` now has via `ScriptMeta`. Not urgent until governance (Phase F+) needs it.

## Immediate next action

Push `ebf40a3` and the E3 commit(s) on top (needs SSH access this session doesn't have). Then decide: continue E2 with LLM-based validation, or expand the Skill/Tool set. See `HANDOFF.md` for the full session-transition brief.

## Earlier phases (condensed — see git history for full detail)

**Phases A–D, E0** (commits `e4720c2`, `57f3dd1`, `c299fbf`, `d9a8599` and others): pooled SQLAlchemy DB, removed `eval()`, sandboxed code execution, allowlisted file access, Alembic migrations, structured logging, unified routing, LLM-based memory extraction with upserts, formal Tool contract + `ToolRegistry`, single Reasoning Service entry point, `experiences` table, Step/Skill abstraction with real `Script`/`Validation`/`Metrics` (`ScriptMeta`, `Step.validate()`, `step_metrics` table), 3 Skills (`research_topic`, `file_digest`, `calculate_and_explain`), and a fix for `generate()` vs `generate_strict()` misuse in the code-gen/query-extraction paths.

**E1 — the Planner** (`eb874c7`): `services/planning_service.py`, registry-driven capability selection (`ToolRegistry.describe_all()` + `SkillRegistry.describe_all()` build the decision prompt dynamically — adding a 4th Tool/Skill needs no code change here). Model selection split out of `routing.py` into its own concern (`select_model()`), correcting a Phase B inconsistency. Graceful degradation chain: LLM decision → rule-based fallback → raw reasoning, verified live with Ollama down (rule-based math path, and full fallback-to-reasoning for a non-math prompt). At the time, the live-LLM decision path itself was unverified — closed this session (see "Session narrative" above).
