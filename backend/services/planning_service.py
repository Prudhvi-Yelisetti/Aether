"""
The Planning Service (ARCHITECTURE.md): "Transforms user goals into
executable plans... Planning determines *what* should happen."

The key difference from the old decide_plugin()/ai_decide_plugin() in
plugin_manager.py (kept below as the offline fallback) is that this
Planner builds its LLM decision prompt FROM the live ToolRegistry and
SkillRegistry via describe_all() — not from a hardcoded list of 3 tool
names. Adding a 4th Tool or a 4th Skill makes it selectable automatically;
nothing in this file needs to change. This is what ROADMAP.md's E1 means
by "based on a capability registry, not keyword matching."

Model selection is deliberately NOT this module's job. ARCHITECTURE.md
assigns "Model selection" to the Reasoning Service, not Planning — this
Planner only decides WHAT should handle a request (a Tool, a Skill, or
raw reasoning), not WHICH model. See main.py: model choice and capability
choice are two independent decisions made side by side, not bundled into
one call the way Phase B's routing.route() did.

Tool-first priority (ARCHITECTURE.md: Primitive Actions > Tools > Steps >
Skills > Workflows > LLM Reasoning) is encoded in the decision prompt
itself ("prefer the SIMPLEST capability"), not as separate code — there
aren't yet enough capabilities for a more elaborate cost-based ordering to
be worth building.
"""

from dataclasses import dataclass, field

from services.reasoning_service import generate_strict, ReasoningError
from services.tools.registry import registry as tool_registry
from services.skills.registry import registry as skill_registry
from services.plugin_manager import decide_plugin, is_simple_math
from services.extraction import extract_filename, extract_search_query, generate_code, slugify_filename
from services.logging_config import get_logger
from services.routing import FAST_MODEL

logger = get_logger("aether.planning")


@dataclass
class Plan:
    capability_type: str  # "tool" | "skill" | "reasoning"
    capability_name: str | None
    input: dict = field(default_factory=dict)  # structured input; only used for skills
    source: str = "llm"  # "rule" | "llm" | "fallback"


def _build_decision_prompt(prompt: str) -> str:
    tools = tool_registry.describe_all()
    skills = skill_registry.describe_all()

    tool_lines = "\n".join(f"- tool:{t['name']} — {t['description']}" for t in tools)
    skill_lines = "\n".join(f"- skill:{s['name']} — {s['description']}" for s in skills)

    return f"""You are a planning system choosing which capability should handle a request.

Available capabilities:
{tool_lines}
{skill_lines}
- none — no tool or skill needed, answer directly

Rules:
- Return ONLY one line, exactly one of:
    tool:<name>
    skill:<name>
    none
- Prefer the SIMPLEST capability that satisfies the request. Only choose a
  skill if the request clearly needs its full sequence (e.g. saving a
  summary to memory), not just a single lookup.

Request: {prompt}
"""


def _parse_decision(raw: str) -> tuple[str, str | None]:
    line = raw.strip().lower().splitlines()[0] if raw.strip() else ""

    if line.startswith("tool:"):
        name = line.split(":", 1)[1].strip()
        if tool_registry.get(name):
            return "tool", name
    if line.startswith("skill:"):
        name = line.split(":", 1)[1].strip()
        if skill_registry.get(name):
            return "skill", name

    return "reasoning", None


def _build_skill_input(capability_name: str, prompt: str, project_id: str | None) -> dict | None:
    """Returns None if the input can't be built (missing project_id for a
    memory-writing Skill, no filename found, code generation failed) —
    plan() treats None as "fall back to reasoning" rather than crashing."""
    if capability_name == "research_topic":
        if not project_id:
            return None
        return {"query": extract_search_query(prompt), "project_id": project_id}

    if capability_name == "research_and_save_file":
        # No project_id needed — this Skill saves to a file in the
        # workspace, not project memory (see research_topic above for the
        # memory-writing equivalent). filename is deterministic
        # (slugify_filename), not another LLM call — matches
        # extract_filename()'s "this is parsing, not reasoning" rationale.
        query = extract_search_query(prompt)
        return {"query": query, "filename": slugify_filename(query)}

    if capability_name == "file_digest":
        if not project_id:
            return None
        filename = extract_filename(prompt)
        if not filename:
            return None
        return {"filename": filename, "project_id": project_id}

    if capability_name == "find_and_digest_file":
        # No project_id needed — unlike file_digest, this Skill doesn't
        # save to memory (see FindAndDigestFileSkill's docstring for why
        # it exists: file_digest fails outright on any filename mismatch,
        # this one fuzzy-matches). Deliberately more tolerant than
        # file_digest's own input-building here too: falls back to the
        # raw prompt as the fuzzy-match candidate when extract_filename()
        # finds no dotted word, instead of returning None and giving up
        # before FindFileStep even gets a chance to try.
        candidate = extract_filename(prompt) or prompt
        return {"candidate_filename": candidate}

    if capability_name == "calculate_and_explain":
        try:
            code = generate_code(prompt)
        except ReasoningError:
            return None
        return {"code": code}

    return None


def plan(prompt: str, project_id: str | None = None) -> Plan:
    # Cheap deterministic path: pure math never needs the Planner or an
    # LLM call at all.
    if is_simple_math(prompt):
        logger.info("plan_decided", capability_type="tool", capability_name="code", source="rule")
        return Plan(capability_type="tool", capability_name="code", source="rule")

    try:
        # FAST_MODEL (routing.py): fast, has "tools" capability. This
        # call was hardcoded "mistral" (not an installed model, verified
        # live 2026-07-21), which meant it always raised ReasoningError
        # and silently took the fallback path below, even with Ollama
        # running. See STATUS.md. Centralized 2026-07-24 to import the
        # constant from routing.py instead of its own hardcoded string —
        # that "one fact, N hardcoded copies" pattern is exactly what
        # caused the original bug.
        raw = generate_strict(_build_decision_prompt(prompt), model=FAST_MODEL)
        capability_type, capability_name = _parse_decision(raw)
    except ReasoningError:
        # Ollama down: degrade to the offline rule-based tool decision
        # rather than failing outright. No Skill can be chosen in this
        # fallback — Skill selection depends on the registry-driven LLM
        # decision above; the old rule-based decide_plugin only knows
        # about bare Tools.
        fallback_tool = decide_plugin(prompt)
        if fallback_tool:
            logger.info("plan_decided", capability_type="tool", capability_name=fallback_tool, source="fallback")
            return Plan(capability_type="tool", capability_name=fallback_tool, source="fallback")
        logger.info("plan_decided", capability_type="reasoning", capability_name=None, source="fallback")
        return Plan(capability_type="reasoning", capability_name=None, source="fallback")

    if capability_type != "skill":
        logger.info("plan_decided", capability_type=capability_type, capability_name=capability_name, source="llm")
        return Plan(capability_type=capability_type, capability_name=capability_name, source="llm")

    built_input = _build_skill_input(capability_name, prompt, project_id)
    if built_input is None:
        logger.warning(
            "plan_skill_input_unbuildable",
            capability_name=capability_name,
            project_id_present=bool(project_id),
        )
        return Plan(capability_type="reasoning", capability_name=None, source="llm")

    logger.info("plan_decided", capability_type="skill", capability_name=capability_name, source="llm")
    return Plan(capability_type="skill", capability_name=capability_name, input=built_input, source="llm")


def execute_plan(p: Plan, prompt: str, request_id: str | None = None) -> str | None:
    """Returns the human-facing response string for tool/skill plans, or
    None for a reasoning plan — the caller (main.py) handles reasoning
    itself via reasoning_service.generate(), since that call also needs
    conversation history/memory that this function deliberately has no
    reason to know about."""
    if p.capability_type == "tool":
        from services.plugin_manager import execute_plugin
        return execute_plugin(p.capability_name, prompt)

    if p.capability_type == "skill":
        skill = skill_registry.get(p.capability_name)
        result = skill.run(p.input, request_id=request_id)

        if result.success:
            last_step_name = skill.steps[-1].name
            return result.context.get(last_step_name, "Done.")

        return f"Couldn't complete this: {result.error}"

    return None
