# Aether — Architecture: Vision vs. Current Reality

This file maps the long-term AIOS vision onto what actually exists in this repo today, so every future contribution can be placed correctly on the map instead of guessed at.

## The vision (target state)

Aether AI Operating System (AIOS): intelligence lives in a kernel of reusable services, not inside any single agent or model. LLMs are replaceable reasoning engines. Core principles:

1. **Agent independence** — no subsystem depends on a specific agent framework
2. **Model independence** — swapping LLMs requires minimal architectural change
3. **Tool first** — prefer deterministic execution over reasoning whenever possible (Primitive Actions → Tools → Steps → Skills → Workflows → LLM Reasoning)
4. **Continuous learning** — the system improves from execution, not from storing raw conversations
5. **Governance before persistence** — nothing changes permanently without evidence, validation, approval, versioning, audit
6. **Artifact-driven intelligence** — structured, reusable artifacts instead of preserved conversations

Full kernel service list (target): Planning, Coordinator, Reasoning, Tool, Step, Skill, Workflow, Memory, Knowledge, Validator, Decision, Governance, Experience, Evolution, Distillation, Cost Engine, Project Brain — communicating via an Intent Bus, with everything represented as immutable versioned AI Objects.

## Current reality (this repo)

A single-process FastAPI chatbot with several real kernel services built and
live-verified (Tool, Skill, Planning, Validator, Decision, Experience — see
`STATUS.md` for the full history of how each landed, including bugs found
and fixed along the way). Still no Intent Bus, no Governance, no versioned
AI Objects for anything but Steps — every "service" is a Python module
communicating via direct function calls, not an independently addressable
kernel service.

## Mapping: target service → current equivalent → gap

| Target Service | Current Equivalent | Gap |
|---|---|---|
| **Tool Service** | `services/tools/` — formal contract (`base.py`: name, description, pydantic `InputModel`, `execute()`), `ToolRegistry`, 5 Tools (`code`, `file`, `write_file`, `list_files`, `web`) | Real sandboxing exists for code execution (`bwrap`) and file access (path allowlisting), but Tools still lack the AI Object Model's full metadata (Identifier/Version/Owner/Trust Level/History/Permissions) that Steps have via `ScriptMeta`. |
| **Reasoning Service** | `services/reasoning_service.py` — single entry point every caller goes through (`generate()`/`generate_strict()`) | Still single provider (Ollama), hardcoded. No model abstraction layer for swapping providers, no prompt compression, no structured output parsing beyond ad-hoc string parsing. |
| **Planning Service** | `services/planning_service.py` — a real Planner, registry-driven (`ToolRegistry.describe_all()` + `SkillRegistry.describe_all()` build the decision prompt dynamically, not hardcoded), with a graceful degradation chain (LLM decision → rule-based fallback → raw reasoning) | No multi-step planning yet — one request gets one capability selection, not a plan spanning multiple Tools/Skills. |
| **Coordinator** | `main.py`'s `/chat` route, delegating to Planning → Validation → Decision | Still one linear function call per request; no dependency management or multi-step execution graph. |
| **Memory Service** | `project_store.py` (`memory` table) + `services/memory_extraction.py` — LLM-based extraction with real upsert semantics (one row per key, not append-only) | Flat key/value, no typing, no distinction from Knowledge. |
| **Knowledge Service** | None | No distinction between "facts about the user" (Memory) and reusable general knowledge. |
| **Experience Service** | `experiences` table + `step_metrics` table — structured record of what happened (capability chosen, source, success, latency) per request and per Step | Still low volume; nothing yet consumes this data to change future behavior (that's Evolution/Distillation, not built). |
| **Validator Service** | `services/validation_service.py` — deterministic failure-string/empty-output checks (live, gates delivery) + `validate_response_llm()` (LLM-based, opt-in, observability-only pending a monitoring period) | LLM-based validation doesn't gate anything yet — deliberate, not an oversight. |
| **Decision Service** | `services/decision_service.py` — bounded retry (with backoff) or escalate to a clear message, based on the Validator's retryable/permanent classification | No replan (retrying the identical capability only); no escalation path beyond a clear message back to the user (no human-in-the-loop, no alerting). |
| **Governance Service** | None | Nothing is versioned except Steps (`ScriptMeta`); nothing requires approval. |
| **Evolution / Distillation** | None | The system does not improve itself from Experience data yet. |
| **Cost Engine** | Partial — `experiences.latency_ms` tracked | No token counting, no cost tracking, no success-rate-driven routing decisions. |
| **Project Brain** | Partial — `project_id` scoping on chats + memory | Only holds chats + flat memory, not Knowledge/Skills/Workflows/Experiences/Decisions per project. |
| **Intent Bus** | None | Subsystems call each other's functions directly (tight coupling), not via structured messages. |
| **AI Object Model (immutable, versioned)** | Partial — Steps have `ScriptMeta` (versioned identity, history) | Tools and Skills still lack this; everything else is mutable SQL rows with no object identity beyond DB primary keys. |

## Why this gap matters for how we build

- **Governance, the Intent Bus, Evolution, and Distillation are still correctly not built** — they have nothing meaningful to govern, route between, or learn from yet in enough volume. `experiences`/`step_metrics` exist and are accumulating real data, but nothing consumes it to change behavior; that's the actual prerequisite for Evolution, not just "having a table."
- **Planning → Validation → Decision (E1–E3) are the real, load-bearing addition since this doc was last accurate.** Every request now goes through a genuine capability-selection → validate → retry-or-escalate pipeline, live-verified end to end, including through the actual UI (see `STATUS.md`'s later entries) — not a stub or a plan, a working thing with real bugs found and fixed in it.
- **Model independence is still not designed in** — every Reasoning Service call still assumes Ollama specifically (model names, the `think` parameter, timeout handling are all Ollama-API-shaped). Worth doing before a second provider is ever actually needed, not preemptively.
- **Immutability and versioning remains a data-layer decision, not a later refactor.** Steps got this early and it's held up well (`ScriptMeta`); Tools and Skills still don't have it, and retrofitting it once there's real usage data referencing them will be more expensive than doing it now — a real, flagged known gap, not forgotten.

See `ROADMAP.md` for the phase-by-phase path from current reality to this target, and `STATUS.md` for the live-verified evidence behind every "done" claim above.
