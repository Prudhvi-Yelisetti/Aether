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

## Phase C — Tool Service Formalization (~1–2 months)

The first genuinely new AIOS-aligned capability, and the highest-leverage next investment because a real precursor already exists (`plugin_manager.py`).

- [ ] C1. Define a Tool contract: `name`, `description`, `input_schema`, `output_schema`, `execute()`
- [ ] C2. Refactor `code_runner`, `file_reader`, `web_search` to implement the contract
- [ ] C3. Build a `ToolRegistry` — register tools, query by capability, add new tools without touching routing logic
- [ ] C4. Route all LLM calls through one Reasoning Service entry point (wrap `ollama_service`) so a second model provider can be added later without touching every caller
- [ ] C5. Add an `ExperienceLog` — every execution writes `{prompt, tool, result, model, latency, timestamp}` to its own table

## Phase D — Skill & Step Abstraction

Only start once Phase C is stable and the Experience log has real data in it.

- [ ] D1. Define a Step: a reusable execution procedure with a contract, script, and validation
- [ ] D2. Define a Skill: a named sequence of Steps sharing context
- [ ] D3. Compose the existing 3 tools into at least one real multi-step Skill (proves the abstraction before generalizing it)

## Phase E — Planning, Validation, Decision

Only start once there are enough Skills/Steps that a linear if/else chain in `main.py` genuinely can't route between them anymore.

- [ ] E1. Introduce a minimal Planner that chooses between Tool / Skill / raw reasoning based on a capability registry, not keyword matching
- [ ] E2. Add a Validator step between generation and delivery (start with deterministic checks — tests/lint — before adding LLM-based validation)
- [ ] E3. Add a Decision step: deliver / retry / escalate, instead of always delivering

## Phase F+ — Governance, Evolution, Distillation, Intent Bus, Cost Engine

Deliberately not broken into tasks yet. These require:
- Versioned, immutable objects to govern (retrofit is expensive — see `ARCHITECTURE.md`)
- A real Experience log with enough volume to learn from
- A settled Intent Bus topology (ordering, delivery guarantees, backpressure) decided before any service depends on it

Revisit this phase only after Phase E is running in daily use.

## Rule for every phase

Before starting a new phase, re-run the review that produced `STATUS.md`: read the current code, confirm the previous phase's checklist is actually done (not just started), and update `STATUS.md` before touching new code.
