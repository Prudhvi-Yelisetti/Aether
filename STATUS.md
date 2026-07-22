# Aether — Current Status

_Last updated: July 22, 2026, after settling E1's live-LLM latency variance (root cause: unset `think` mode, not timeout/hardware) and shipping E2's first deterministic Validator check, live-verified both the success and failure path. Update this file whenever a Critical/Important item is resolved or a new one is found._

**Continuing in a new session? Read `HANDOFF.md` first — it's the compact version of everything below.**

## Snapshot

| | |
|---|---|
| Vision | Aether AI Operating System (AIOS) — see `ARCHITECTURE.md` |
| Current state | **Phase A + B + C + D complete. E0 + E1 complete and live-verified (fast, reliable). E2 started: first deterministic Validator check live and proven.** |
| Commits | Everything through E1 committed and pushed (`eb874c7`). **Uncommitted**: model-name fix (7 files) + `think`-mode fix + timeout tuning + new `services/validation_service.py` + `main.py`/`reasoning_service.py` wiring for E2 — see below. |
| Local usage | 1 project, 3 memory rows, 25 chats — verified intact through every migration and test run across both sessions |
| Critical blockers | 0 |
| Next phase | Rest of E2 (more deterministic checks, then LLM-based validation) / E3 (Decision), or expand the Skill set further — Prudhvi's call |

## How to run it now

```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```
Apply new migrations after pulling: `.venv/bin/alembic upgrade head`.
Ollama must be running (`ollama serve`) with `qwen3.5:9b` and `qwen3-coder:latest` pulled — these are the only two models the codebase now references.

## Resolved this session — the live-LLM path was untestable, not just untested

Ollama was down for the entire prior session, so E1's HANDOFF.md correctly flagged the live-LLM decision path as unverified. This session started Ollama up to close that gap — and found the real reason it had never been exercised was worse than "Ollama was down":

**Every LLM call site in the backend hardcoded `"llama3"` or `"mistral"` as the model name — neither is installed.** Only `qwen3.5:9b` and `qwen3-coder:latest` are pulled on this machine. So even with Ollama running, every live call failed instantly on `"model 'X' not found"`, which `planning_service.plan()`'s `generate_strict()` catches as a `ReasoningError` and silently routes to the offline fallback — indistinguishable from Ollama being down at all. Proven live: first test request returned `"Error from mistral: {'error': \"model 'mistral' not found\"}"` verbatim as the chat response, and the `experiences` row logged `tool_source: fallback` with 1.7ms latency (instant failure, not a real attempt).

**Fixed all 7 affected files** to use the two models actually installed (`qwen3.5:9b` for decisions/reasoning/extraction, `qwen3-coder:latest` for code generation): `routing.py`, `planning_service.py`, `plugin_manager.py` (3 call sites), `extraction.py` (2 call sites), `memory_extraction.py`, `services/steps/summarize_step.py`, plus the misleading `model="llama3"` defaults in `reasoning_service.py`/`ollama_service.py` (unreachable now that every caller passes an explicit model, but left as a landmine otherwise).

**Not fixed, flagged for cleanup**: `services/router.py` is a dead, zero-caller duplicate of `routing.py`'s old logic, with the same broken model names. Recommend deleting it — didn't do so unilaterally since it's a file removal, not a bug fix.

### Live verification, with real DB evidence (`experiences` table, 4 consecutive test requests)

| tool_source | success | latency_ms | what it shows |
|---|---|---|---|
| fallback | false | 1.7 | pre-fix baseline: instant "model not found" |
| fallback | false | 60068 | post-fix, but hit a wedged Ollama instance (stale process) |
| **llm** | false | 60062 | **decision call succeeded live** — the specific unverified claim, now proven |
| fallback | false | 60063 | same request again, decision call itself timed out this time |

The two `llm`/`fallback` results back-to-back on the identical request show the real finding: **the live-LLM decision path works, but was flaky against the original 60s timeout** — `qwen3.5:9b` (9.7B) on this machine's CPU measured 14s for a bare warm Ollama call, but the app's decision + reasoning calls (extra prompt overhead) were clocking 45–60s+ each, so two sequential LLM calls per request (decision, then answer generation) had a real chance of blowing a 60s-per-call budget. One test's user-facing response was literally `"Request to qwen3.5:9b timed out after 60s"`.

**Fix applied**: `REQUEST_TIMEOUT_SECONDS` in `ollama_service.py` raised from 60 to 150. **Re-verified live — result was genuinely mixed, and turned out to be a symptom, not the real fix (see below).**

## Resolved 2026-07-22 — the real root cause was `think` mode, not timeout or reload cost

The 150s timeout bump above bought exactly one successful full response and didn't fix the underlying flakiness (decision-call latency for the *same* prompt still ranged 45s–150s+ across repeated tests). That was the signal something structural was wrong, not just under-provisioned. Investigated properly instead of raising the number further:

`qwen3.5:9b` is a hybrid **thinking** model (confirmed via `ollama list`: `"capabilities":[...,"thinking"]`), and `ollama_service.py`'s request payload never set the API's `think` field. Proved directly with a controlled A/B — identical decision prompt, identical correct output (`"none"`):

| `think` | latency | hidden reasoning trace |
|---|---|---|
| unset (previous behavior) | 30.9s | 369 chars |
| `false` (explicit) | 0.8s | 0 chars |

**37x speedup, same correctness.** The 45–150s+ variance chased the day before was the model running an unbounded internal reasoning trace on every call — including one-line yes/no classification prompts that need zero reasoning — with no way to predict how long that trace would run. Not reload cost, not hardware limits, not something a bigger timeout could actually fix (proven — 150s still weren't always enough).

**Fix**: `ollama_service.generate_response()` now takes a `think: bool = False` parameter and passes it through to Ollama's API explicitly, defaulting off everywhere (no caller currently opts in). `REQUEST_TIMEOUT_SECONDS` restored to 60 — no longer needs padding now that the real problem is gone. **Re-verified live, 3 consecutive identical requests, all successful and fast**:

| tool_source | success | latency_ms |
|---|---|---|
| llm | true | 5095 |
| llm | true | 6121 |
| llm | true | 5361 |

No more flakiness, no more fallback-on-timeout, no more multi-minute waits. This closes both the original HANDOFF.md item (live-LLM decision path verified) and the latency-variance open question — with proof, not a bigger number papering over an unknown cause.

**Worth deciding later, not urgent**: thinking mode is now off everywhere, including the main reasoning `generate()` call for actual chat answers. That's the right default for latency, but means Aether never uses `qwen3.5:9b`'s reasoning capability even for genuinely hard questions. If answer quality on complex questions ever becomes a concern, consider making `think` an opt-in per-request flag (e.g. for `mode: "powerful"`) rather than a blanket off — but don't default it back on without the same kind of proof this fix required.

## What's already right — keep these

- **Registry-driven decision prompt** — this is the actual architectural upgrade E1 was supposed to deliver. Resist ever hardcoding tool/skill names back into a decision prompt; if a 4th capability needs special-casing in `planning_service.py`, something's wrong with that capability's `description`, not with the Planner.
- **Model selection vs. capability selection as two separate calls** — matches `ARCHITECTURE.md`'s actual service boundaries. Don't re-merge them for convenience.
- **Graceful multi-layer fallback (LLM → rule → reasoning)** — this is exactly what made the model-name bug survive undetected for as long as it did: the system degrades so cleanly that a total live-LLM failure looks identical to a healthy offline fallback in the response text alone. The `experiences` table's `tool_source` column is the only reliable signal — check it, don't trust response text alone, when verifying live-LLM behavior specifically.

## Known gaps

- Model name is currently a single hardcoded pair (`qwen3.5:9b` / `qwen3-coder:latest`) duplicated across 7 files rather than defined once. Worth centralizing into `routing.py`'s constants and importing everywhere, instead of each file choosing its own string — the exact bug just fixed was made possible by there being 7 places to get it wrong instead of one.
- `services/router.py` — dead file, same bug, not deleted. Low urgency (zero callers) but a landmine if anyone ever imports it by mistake.
- `think` is hardcoded off everywhere via a default parameter rather than being a considered per-request choice — fine for now, worth revisiting only if answer quality on hard questions becomes a real concern (see the `think`-mode writeup above).
- `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) the way `Step` now has via `ScriptMeta`. Not urgent until governance (Phase F+) needs it.

## Immediate next action

Commit the model-name + `think`-mode + timeout + E2-Validator fixes (all currently uncommitted). Then decide E2's next increment (empty-response check is trivial; LLM-based validation is a bigger, separate piece) vs moving to E3. See `HANDOFF.md` for the full session-transition brief.

## Resolved 2026-07-22 — E2, first pass: deterministic Validator, live-proven both ways

Scoped narrow deliberately (per ROADMAP.md: "start with deterministic checks... before adding LLM-based validation") and motivated by a real bug proven live earlier the same session, not speculative scope: a raw Ollama timeout string was delivered to the user as if it were a real answer.

Found the actual gap first: `main.py` already computed a `success` flag from a hardcoded list of failure-string prefixes for the experience log — but never used that knowledge to protect the `response` field actually sent to the user. The detection existed; nothing acted on it. Also found the same list was duplicated, slightly differently, in `reasoning_service.py` — the identical "one fact, N hardcoded copies" pattern that caused the model-name bug earlier this session.

**Built `services/validation_service.py`** as the single source of truth: `FAILURE_PREFIXES` (reasoning-layer + tool/skill-layer failure strings, previously two separate hand-maintained lists) and `validate_response()` (deterministic: empty output or known failure prefix → invalid). `reasoning_service.py` now imports the reasoning-only subset from there instead of keeping its own copy. `main.py`'s `/chat` endpoint calls `validate_response()` after generation; on failure, it now substitutes a clean user-facing message instead of delivering the raw internal string, and logs a new `response_validation_failed` event with the reason.

**A real bug in my own first attempt at this wiring was caught live**, not assumed clean: an import-rename left one usage site in `reasoning_service.py` referencing the old (now-undefined) name, which surfaced as a live HTTP 500 the moment I tested it. Fixed, re-verified modules import cleanly, then re-tested.

**Verified live, both the success and failure path, with DB evidence**:

| id | tool_source | success | latency_ms | scenario |
|---|---|---|---|---|
| 9 | llm | true | 9809 | normal request, Ollama up — passes validation, unchanged behavior |
| 10 | fallback | false | 0.7 | Ollama stopped mid-session — `generate()` returned `"Could not reach Ollama..."`, validator caught it (`reason: known_failure_prefix`), user received `"Something went wrong generating a response — please try again."` instead of the raw internal string |

Structured logs for row 10 show the full expected chain: `ollama_unreachable` → `plan_decided` (source: fallback) → `ollama_unreachable` (second call) → `response_validation_failed` → `request_finished` (still HTTP 200, by design — a validation failure is not a server error, it's a handled, logged, gracefully-degraded response).

**Scope boundary, explicit**: this is deterministic-only. LLM-based validation ("does this response actually answer the question") is out of scope for this pass, per the roadmap's own stated sequencing — add it as a second, separately-verified check once this one has run for a while, not bundled in from the start.

See git history of this file for full details (commits `e4720c2`, `57f3dd1`, `c299fbf`, `d9a8599`). Summary: pooled DB, sandboxed code execution, allowlisted file access, unified routing, upserted memory, formal Tool contract + registry, single Reasoning Service entry point, Experience log, Step/Skill abstraction with real `Script`/`Validation`/`Metrics` (`ScriptMeta`, `Step.validate()`, `step_metrics` table), `generate_strict()` fix applied to the code-gen/web-query paths.

## Resolved — E1: the Planner (committed as `eb874c7`)

Prudhvi asked for the architecture built "however you think is perfect" — this is the natural next piece now that 3 structurally distinct Skills exist (satisfying Phase E's own stated precondition).

1. **`services/planning_service.py`** — `plan(prompt, project_id) -> Plan`. The core design point, and what makes this a genuine improvement over the old `ai_decide_plugin()`: the LLM decision prompt is built **dynamically from `ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`**, not a hardcoded 3-option string. Adding a 4th Tool or Skill makes it selectable automatically — nothing in `planning_service.py` needs to change. This is literally what `ROADMAP.md`'s E1 meant by "based on a capability registry, not keyword matching."
2. **Graceful degradation chain**: registry-driven LLM decision → (if Ollama down) the old rule-based `decide_plugin()` as an offline fallback, Tool-only → (if that also finds nothing) raw reasoning. Verified live: with Ollama down, `9*9` still hit the free rule-based math path (no LLM call at all), and `"hello how are you"` correctly fell through the whole chain to `reasoning` with `source: "fallback"`.
3. **Model selection split out from capability selection**, correcting a real inconsistency from Phase B: `ARCHITECTURE.md` assigns "Model selection" to the *Reasoning* Service, not Planning, but Phase B's `routing.route()` bundled both into one call. `services/routing.py` now does model selection only (`select_model()`); `planning_service.py` does capability selection only. Two independent decisions, not one blurred one — `main.py` calls both explicitly.
4. **`services/extraction.py`** — pulled the query/filename/code-generation extraction logic out of `plugin_manager.py` into shared helpers, since the Planner needs the exact same extraction for building Skill input that `execute_plugin()` already did for Tool input. No prompt duplicated across two files.
5. **`main.py` rewritten** to call `plan()` then `execute_plan()` instead of the old `routing.route()` + `execute_plugin()` pair. `request_id` is now fetched at the top of the handler (via structlog contextvars) instead of after response generation, so it can be threaded into `Skill.run()` for step-metrics logging.

**A second real bug was found and fixed while verifying this**, not introduced by E1 but exposed by re-reading old E0-era `experiences` rows: the *old* success-detection heuristic in `main.py` didn't include `"Could not generate code"` as a failure prefix (that message didn't exist yet when the heuristic was first written), so an E0 test got logged as `success: true` despite genuinely failing. Fixed in the new `main.py`'s heuristic, which now also includes `"Couldn't complete this"` (the new Skill-failure message format).

**A connector outage happened mid-verification** (Desktop Commander stalled on 3 consecutive calls, including a trivial `get_config`). One edit (a missing `plan_decided` log line for the rule-based math path) was confirmed NOT to have landed by re-reading the file after reconnecting, rather than assumed either way — then reapplied and re-verified from a clean server restart.

**Verified live, full clean run after reconnecting, Ollama still down throughout**:
- `9*9` → rule-based math path, `plan_decided` logged correctly, `experiences` row shows `tool: code, tool_source: rule, success: 1`
- `"hello how are you"` → falls through the full chain to reasoning, `experiences` row shows `tool: null, tool_source: fallback, success: 0` (honestly reflecting Ollama being down)
- Existing project data (`GET /projects`) still reads correctly through the new `main.py`
- DB confirmed clean before and after: 3 memory rows, 25 chats, throughout

## What's already right — keep these

- **Registry-driven decision prompt** — this is the actual architectural upgrade E1 was supposed to deliver. Resist ever hardcoding tool/skill names back into a decision prompt; if a 4th capability needs special-casing in `planning_service.py`, something's wrong with that capability's `description`, not with the Planner.
- **Model selection vs. capability selection as two separate calls** — matches `ARCHITECTURE.md`'s actual service boundaries. Don't re-merge them for convenience.
- **Graceful multi-layer fallback (LLM → rule → reasoning)** — the system stays usable with the model provider fully down, proven repeatedly this session since Ollama was never once available.

## Known gaps, unchanged from before

- `Tool` and `Skill` objects still lack the AI Object Model's full metadata (`Identifier`/`Version`/`Owner`/`Trust Level`/`History`/`Permissions`) the way `Step` now has via `ScriptMeta`. Not urgent until governance (Phase F+) needs it.
- The Planner's LLM decision path itself has never been tested against a live Ollama response this entire session — only its fallback chain has real end-to-end verification. `_parse_decision()` and `_build_decision_prompt()` were unit-tested directly (proven correct against simulated inputs), but the full "ask Ollama, get back `skill:research_topic`, execute it" path is unverified against a real model. **Worth running once Ollama is available**, before trusting this in daily use.

## Immediate next action

Run one real end-to-end test with Ollama actually up, to close the one remaining unverified path (the live LLM decision, not just its fallback). Then decide: E2/E3 next, or expand the Skill/Tool set further first. See `HANDOFF.md` for the full session-transition brief.
