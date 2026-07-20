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

- [x] B1. Unify `router.py` and `plugin_manager.py` into a single routing decision returning `{model, tool_or_none}` — done via new `services/routing.py`; verified live that a rule-matched tool request skips the LLM decision call entirely (`tool_source: "rule"` in logs)
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

- [x] D1. Define a Step: a reusable execution procedure with a contract, script, and validation — done via `services/steps/base.py`; unlike a Tool, a Step may call the Reasoning Service (documented explicitly as the exception to "tools never reason")
- [x] D2. Define a Skill: a named sequence of Steps sharing context — done via `services/skills/base.py`; `Skill.run()` stops at the first failed Step rather than continuing with a broken context
- [x] D3. Compose the existing 3 tools into at least one real multi-step Skill — done via `ResearchTopicSkill` (web search → summarize → save to memory), deliberately not wired into the live `/chat` path (that's Phase E's Planner's job)

**A real bug was found and fixed during this phase**, not just a clean build: `SummarizeStep` initially treated an Ollama-down failure as success (because `reasoning_service.generate()` returns a friendly string rather than raising, which is correct for chat UX but wrong for a Step checking success programmatically) — it nearly saved `"Could not reach Ollama..."` into memory as a real research summary. Fixed by adding `reasoning_service.generate_strict()`, which raises on the same failures. See `STATUS.md` for the full story — this distinction (`generate()` for humans, `generate_strict()` for automated callers) matters for every Step/Workflow/Evolution-check going forward.

See `STATUS.md` for verification details on each item.

## Phase E — Planning, Validation, Decision

Only start once there are enough Skills/Steps that a linear if/else chain in `main.py` genuinely can't route between them anymore.

- [x] E0. (carried over from Phase C/D) Apply the `generate_strict()` fix to `execute_plugin`'s code-gen path in `plugin_manager.py` — done; verified live with Ollama down: code-gen path now returns "Could not generate code: ..." instead of feeding the failure string into the sandbox as Python; web query-extraction now falls back to the raw prompt instead of searching for the literal error text
- [ ] E1. Introduce a minimal Planner that chooses between Tool / Skill / raw reasoning based on a capability registry, not keyword matching — **gated: see note below**
- [ ] E2. Add a Validator step between generation and delivery (start with deterministic checks — tests/lint — before adding LLM-based validation)
- [ ] E3. Add a Decision step: deliver / retry / escalate, instead of always delivering

**Note on E1 (July 20, 2026):** this phase's own header condition — "only start once there are enough Skills/Steps that a linear if/else chain genuinely can't route between them anymore" — isn't actually met yet. Phase D produced exactly one Skill (`ResearchTopicSkill`), unwired, as a proof of concept. Building a Planner now would mean designing capability-selection logic against a registry with one real entry, which risks over-fitting the Planner's shape to a single example rather than a genuine variety of capabilities. Before E1: either build 2-3 more real Skills first (so the Planner has something to actually discriminate between), or treat E1 as scaffolding-only for now and revisit once there's real variety. This is a product decision, not a technical one — flagged for Prudhvi rather than decided autonomously.

## Phase F+ — Governance, Evolution, Distillation, Intent Bus, Cost Engine

Deliberately not broken into tasks yet. These require:
- Versioned, immutable objects to govern (retrofit is expensive — see `ARCHITECTURE.md`)
- A real Experience log with enough volume to learn from
- A settled Intent Bus topology (ordering, delivery guarantees, backpressure) decided before any service depends on it

Revisit this phase only after Phase E is running in daily use.

## Rule for every phase

Before starting a new phase, re-run the review that produced `STATUS.md`: read the current code, confirm the previous phase's checklist is actually done (not just started), and update `STATUS.md` before touching new code.
