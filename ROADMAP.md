# Aether — Roadmap

Ordered by dependency, not by ambition. Each phase must be genuinely solid before the next begins — the AIOS services are interdependent, so building Governance before there's anything worth governing produces bureaucracy with no substance underneath it. Check items off in `STATUS.md` as they land, don't duplicate tracking here.

## Phase A — Security & Correctness (do this first, ~2 weeks)  ✅ COMPLETE

No new features until these are done. Every feature built on top of them inherits the vulnerability.

- [x] A1. Replace global SQLite connection in `db/database.py` with SQLAlchemy + a connection pool
- [x] A2. Remove `eval()` in `plugin_manager.py`; replaced with an AST-based safe math evaluator
- [x] A3. Replace the blocklist-based sandbox in `code_runner.py` with real isolation — done via `bwrap` (`--unshare-all`, read-only root, `ulimit` CPU/mem/proc caps), verified live: no network, no writable filesystem, timeout enforced
- [x] A4. Add path validation to `file_reader.py` — allowlisted to `~/aether-workspace/`, verified traversal attempts are rejected
- [x] A5. Add structured logging (`structlog`) with a request ID threaded through every call — verified one request_id spans routing → plugin → Ollama call in the logs
- [x] A6. Add Alembic for schema migrations — stamped at a baseline matching the existing schema, zero data loss (25 chats verified before/after)

See `STATUS.md` for verification details on each item.

## Phase B — Architecture Cleanup (~3–4 weeks)  ✅ COMPLETE

Makes the codebase coherent before it grows further.

- [x] B1. Unify `router.py` and `plugin_manager.py` into a single routing decision returning `{model, tool_or_none}` — done via new `services/routing.py`; verified live that a rule-matched tool request skips the LLM decision call entirely (`tool_source: "rule"` in logs). **Superseded in E1** — see below.
- [x] B2. Replace string-matching memory extraction (`extract_memory` in `main.py`) with an LLM-based extraction step — done via new `services/memory_extraction.py`
- [x] B3. Add upsert semantics to memory — one row per (project, key), updated not appended — done via a unique constraint (Alembic migration `f33fab44be66`) + `INSERT ... ON CONFLICT DO UPDATE`; verified two saves of the same key produce one row, not two
- [x] B4. Replace bare `except:` with typed exceptions and proper error responses — already covered by Phase A's structlog changes in the files this phase touched; nothing left bare
- [x] B5. Frontend cleanup pass: fixed the duplicate `fetchProjects()` call in `App.js`

See `STATUS.md` for verification details on each item.

## Phase C — Tool Service Formalization (~1–2 months)  ✅ COMPLETE

The first genuinely new AIOS-aligned capability, and the highest-leverage next investment because a real precursor already exists (`plugin_manager.py`).

- [x] C1. Define a Tool contract: `name`, `description`, `input_schema`, `output_schema`, `execute()` — done via `services/tools/base.py`; input schemas are real JSON Schema via pydantic
- [x] C2. Refactor `code_runner`, `file_reader`, `web_search` to implement the contract — done; per ARCHITECTURE.md's "Tools never perform reasoning," natural-language parsing moved out of the plugins and into `plugin_manager.py`, leaving the plugins purely deterministic
- [x] C3. Build a `ToolRegistry` — done via `services/tools/registry.py`; `plugin_manager.py` now dispatches through `registry.get(name)` instead of an if/elif chain
- [x] C4. Route all LLM calls through one Reasoning Service entry point — done via `services/reasoning_service.py`; it's now the only module importing `ollama_service` directly
- [x] C5. Add an `ExperienceLog` — done via the `experiences` table (Alembic `3d051fbf7d64`) + `storage/experience_store.py`; verified live with a matching `request_id` across structured logs and the DB row

See `STATUS.md` for verification details on each item.

## Phase D — Skill & Step Abstraction  ✅ COMPLETE

Only start once Phase C is stable and the Experience log has real data in it.

- [x] D1. Define a Step: a reusable execution procedure with a contract, script, and validation — **initially only the execution contract was actually built**; Script, Validation, and Metrics were retroactively added after Prudhvi asked directly whether Skills were properly split into scripts and steps per the architecture doc. See `STATUS.md`'s "closing the Step contract gap" entry for the full story. Now genuinely done: `ScriptMeta` (versioned identity, not executable data), `Step.validate()` (distinct from success, proven with `RunCodeStep`'s "ran but produced no output" case), and the `step_metrics` table (success rate vs. validation-pass rate tracked separately).
- [x] D2. Define a Skill: a named sequence of Steps sharing context — done via `services/skills/base.py`; `Skill.run()` now gates on each Step's `validate()`, not just `result.success`
- [x] D3. Compose the existing 3 tools into at least one real multi-step Skill — done via `ResearchTopicSkill` (web search → summarize → save to memory), plus `FileDigestSkill` and `CalculateAndExplainSkill` added since — 3 Skills with genuinely different shapes, all wired live via the Planner as of E1. **Expanded further, post-E3**: a 4th Tool (`WriteFileTool`/`write_file`, the first *write* capability — Aether could previously only read files) and a 4th Skill (`ResearchAndSaveFileSkill`) composing the existing `WebSearchStep`+`SummarizeStep` with the new `WriteFileStep` — live-verified the Planner selects it correctly from natural language (`source: "llm"`) and the full pipeline produces a real file on disk. Found, and same-day fixed, a real pre-existing fragility in `extract_search_query()` + the DuckDuckGo Instant Answer API shared by `research_topic` too: tightened the extraction prompt to preserve original topic wording, and added a Wikipedia OpenSearch+summary fallback to `web_search.py` for when DDG's narrow exact-topic keying still comes up empty. Live-verified end-to-end: the same prompt that failed 100% of the time before the fix now succeeds (real file, real content) — see `STATUS.md` for the full before/after evidence, including a real bug caught in the fallback's own first version (missing `User-Agent` header, silently swallowed by a bare `except`). **Expanded again**: a 5th Tool (`ListFilesTool`/`list_files`) and a 5th Skill (`FindAndDigestFileSkill`), composing `ListFilesStep` + the new `FindFileStep` (deterministic fuzzy filename matching) with the existing `ReadFileStep`+`SummarizeStep` — addresses "File not found," the single most common permanent Tool/Skill failure observed all session. Caught and fixed a real matching bug before shipping: the first version only matched whole strings and failed live, twice, on realistic natural-language prompts despite passing every unit test; fixed with a token-level fallback, re-verified both previously-failing prompts now succeed fully end-to-end.

**A real bug was found and fixed during this phase**, not just a clean build: `SummarizeStep` initially treated an Ollama-down failure as success (because `reasoning_service.generate()` returns a friendly string rather than raising, which is correct for chat UX but wrong for a Step checking success programmatically) — it nearly saved `"Could not reach Ollama..."` into memory as a real research summary. Fixed by adding `reasoning_service.generate_strict()`, which raises on the same failures. See `STATUS.md` for the full story — this distinction (`generate()` for humans, `generate_strict()` for automated callers) matters for every Step/Workflow/Evolution-check going forward.

See `STATUS.md` for verification details on each item.

## Phase E — Planning, Validation, Decision

- [x] E0. (carried over from Phase C/D) Apply the `generate_strict()` fix to `execute_plugin`'s code-gen path in `plugin_manager.py` — done; verified live with Ollama down: code-gen path now returns "Could not generate code: ..." instead of feeding the failure string into the sandbox as Python; web query-extraction now falls back to the raw prompt instead of searching for the literal error text
- [x] E1. Introduce a minimal Planner that chooses between Tool / Skill / raw reasoning based on a capability registry, not keyword matching — done via `services/planning_service.py`. The decision prompt is built dynamically from `ToolRegistry.describe_all()` + `SkillRegistry.describe_all()`, not hardcoded — the actual point of "capability registry, not keyword matching." Model selection was also split out of `routing.py` into its own concern (`select_model()`), correcting a Phase B inconsistency where it was bundled with tool selection despite `ARCHITECTURE.md` assigning model selection to the Reasoning Service. Wired live into `main.py`, replacing `routing.route()` + `execute_plugin()`. **Live-LLM path since verified** (a later session found and fixed a hardcoded-model-name bug plus a `think`-mode latency issue that had masked this — see `STATUS.md`): 3 consecutive identical requests, all `tool_source: "llm"`, all successful, 5–6s each.
- [x] E2. Add a Validator step between generation and delivery (start with deterministic checks — tests/lint — before adding LLM-based validation) — note: per-Step validation now exists (`Step.validate()`); E2 is about validating a Skill/request's *final* output before delivery, a different layer. **Both increments done** (`services/validation_service.py`): (1) deterministic — catches known internal-failure strings and empty output before either reaches the user, live-verified against a real forced failure; (2) LLM-based — `validate_response_llm()` asks a model whether the response actually addresses the prompt, live-verified on a good answer (accepted), a deliberately off-topic answer (correctly flagged), and a judge-unavailable case (fails open, doesn't penalize a good response for an unrelated Ollama outage). **Deliberately opt-in and observability-only** for this first pass (`ChatRequest.llm_validate`, default `False`) — logs a result but doesn't change what's delivered or retried yet, since an unreliable LLM judge silently rejecting good answers would be worse than not judging them. Promoting it to actually gate delivery is a deliberate future decision.
- [x] E3. Add a Decision step: deliver / retry / escalate, instead of always delivering. **First increment done** (`services/decision_service.py`): bounded retry (one extra attempt, now with a 2s delay before retrying) when `validate_response()` classifies a failure as transient, escalation to a clear honest message otherwise — no more always-deliver. Live-verified on all three paths (normal delivery, immediate escalation for a permanent failure, retry-then-escalate for a transient one still failing), plus a deterministic test proving the retry-with-backoff mechanism itself recovers a transient failure (a live real-world recovery attempt was tried first but the result turned out to be attributable to lucky timing, not the retry firing — corrected in `STATUS.md` rather than left standing). `RETRY_DELAY_SECONDS` is currently a guess (2.0s), not measured against a real outage's duration.
- [x] E-UI. Not a roadmap phase item originally, but a real gap: the frontend had no visibility into any of E1–E3 (which capability handled a request, whether it retried/escalated). `/chat` now returns `capability_type`/`capability_name`/`capability_source`/`attempts`/`escalated` (main.py always computed these, never returned them); new `GET /capabilities` exposes the Tool/Skill registries directly. Frontend rebuilt around a live trace of that pipeline as the signature UI element, plus a Capabilities panel. Found and fixed a real, previously-undiscovered bug through this new surface: `execute_plugin()` had no branches for `write_file`/`list_files` when selected as a standalone Tool (only worked when called via a Skill) — see `STATUS.md` item 12.

## Phase F+ — Governance, Evolution, Distillation, Intent Bus, Cost Engine

Deliberately not broken into tasks yet. These require:
- Versioned, immutable objects to govern (retrofit is expensive — see `ARCHITECTURE.md`) — **partially addressed for Steps** via `ScriptMeta`; Tools and Skills still lack this, see `STATUS.md`'s "known gaps"
- A real Experience log with enough volume to learn from — `experiences` (request-level) and `step_metrics` (step-level) both exist now, still low volume
- A settled Intent Bus topology (ordering, delivery guarantees, backpressure) decided before any service depends on it

Revisit this phase only after Phase E is running in daily use.

## Rule for every phase

Before starting a new phase, re-run the review that produced `STATUS.md`: read the current code, confirm the previous phase's checklist is actually done (not just started), and update `STATUS.md` before touching new code.
