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

A single-process FastAPI chatbot. No bus, no planner, no governance, no versioned objects. Every "service" folder name in `backend/services/` is a Python module, not an independent, addressable kernel service.

## Mapping: target service → current equivalent → gap

| Target Service | Current Equivalent | Gap |
|---|---|---|
| **Tool Service** | `plugins/` (code_runner, file_reader, web_search) + `plugin_manager.py` | No formal tool contract (input/output schema). No sandboxing. Selection logic duplicated with the router. |
| **Reasoning Service** | `ollama_service.py` | Single provider (Ollama), hardcoded. No model abstraction layer, no prompt compression, no structured output parsing. |
| **Planning Service** | None | `main.py` hardcodes the execution path (route → maybe-plugin → generate). No planner decides *what* should happen — it's an if/else chain. |
| **Coordinator** | `main.py` route handler | No dependency management, no retry, no multi-step execution. Every request is one linear function call. |
| **Memory Service** | `project_store.py` (`memory` table) | Flat key/value, string-matched extraction, no dedup, no typing. |
| **Knowledge Service** | None | No distinction between "facts about the user" and "reusable general knowledge." |
| **Experience Service** | None | No structured record of what happened/why/what was learned per execution. |
| **Validator Service** | None | No validation step exists between generation and delivery. |
| **Decision Service** | None | Result is always delivered; no retry/replan/escalate logic. |
| **Governance Service** | None | Nothing is versioned; nothing requires approval. |
| **Evolution / Distillation** | None | The system does not improve itself from execution. |
| **Cost Engine** | None | No token/latency/success-rate tracking. |
| **Project Brain** | Partial — `project_id` scoping exists in the data model | Only holds chats + flat memory, not Knowledge/Skills/Workflows/Experiences/Decisions. |
| **Intent Bus** | None | Subsystems call each other's functions directly (tight coupling), not via structured messages. |
| **AI Object Model (immutable, versioned)** | None | All data is mutable SQL rows. No versioning, no object identity beyond DB primary keys. |

## Why this gap matters for how we build

- **Do not build Governance, Planning, or the Intent Bus yet.** They have nothing meaningful to govern, plan, or route between until Tool/Skill/Memory/Experience are solid. Building them now produces bureaucracy with no substance underneath.
- **The Tool Service is the correct next investment**, because it's the one target service with a genuine, working precursor already in the repo (`plugin_manager.py`). Formalizing it (contracts, registry, safe execution) is the highest-leverage next step.
- **Model independence should be designed in now**, even though only Ollama is used today — every direct call to `ollama_service.generate_response` should eventually go through one Reasoning Service entry point, so swapping or adding a provider later doesn't mean touching every caller.
- **Immutability and versioning are a data-layer decision, not a later refactor.** Retrofitting versioned objects onto live mutable SQL rows is expensive. Once Skills/Steps/Workflows are introduced (Phase 4+ in `ROADMAP.md`), those objects should be versioned from day one even while the rest of the system stays on plain SQL.

See `ROADMAP.md` for the phase-by-phase path from current reality to this target.
