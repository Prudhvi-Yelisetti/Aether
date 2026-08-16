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


def _build_skill_input(capability_name: str, prompt: str, project_id: str | None, consolidate_memory: bool = False) -> dict | None:
    """Returns None if the input can't be built (missing project_id for a
    memory-writing Skill, no filename found, code generation failed) —
    plan() treats None as "fall back to reasoning" rather than crashing.

    consolidate_memory (added alongside the memory-consolidation feature
    — see storage/project_store.py's save_memory() and
    services/consolidation_service.py): opt-in, default off, only
    meaningful for the two memory-writing skills below (research_topic,
    find_and_digest_file) — threaded into their input dict so
    SaveMemoryStep's context has it. research_and_save_file doesn't
    write to project memory at all (it writes to a workspace file
    instead), so it's irrelevant there."""
    if capability_name == "research_topic":
        if not project_id:
            return None
        return {"query": extract_search_query(prompt), "project_id": project_id, "consolidate_memory": consolidate_memory}

    if capability_name == "research_and_save_file":
        # No project_id needed — this Skill saves to a file in the
        # workspace, not project memory (see research_topic above for the
        # memory-writing equivalent). filename is deterministic, not
        # another LLM call — matches extract_filename()'s "this is
        # parsing, not reasoning" rationale.
        #
        # Bug found live 2026-07-31 via llm_validate eval traffic (see
        # STATUS.md): this always called slugify_filename(query),
        # ignoring any filename the user actually typed — "research the
        # Eiffel Tower and save a summary to eiffel_summary.txt" silently
        # saved as eiffel_tower.txt instead. find_and_digest_file below
        # already calls extract_filename(prompt) first for exactly this
        # reason; this branch just never did. Same fix here: prefer an
        # explicit filename in the prompt, fall back to the slugified
        # query only when the user didn't name one.
        query = extract_search_query(prompt)
        filename = extract_filename(prompt) or slugify_filename(query)
        return {"query": query, "filename": filename}

    if capability_name == "find_and_digest_file":
        # project_id required as of 2026-08-13 (STATUS.md item 23) —
        # this Skill now writes episodic memory itself (SaveMemoryStep
        # added to FindAndDigestFileSkill), closing the overlap where
        # the planner reliably preferred this Skill over the retired
        # file_digest for typical phrasing, but only file_digest ever
        # wrote to memory. Same memory_key ("last_file_digest") as
        # file_digest used, so existing episodic rows/consolidated
        # facts under that key keep working unchanged regardless of
        # which Skill produced them.
        #
        # Deliberately more tolerant filename handling than a strict
        # exact-match would be: falls back to the raw prompt as the
        # fuzzy-match candidate when extract_filename() finds no dotted
        # word, instead of returning None and giving up before
        # FindFileStep even gets a chance to try.
        if not project_id:
            return None
        candidate = extract_filename(prompt) or prompt
        return {"candidate_filename": candidate, "project_id": project_id, "consolidate_memory": consolidate_memory}

    if capability_name == "calculate_and_explain":
        try:
            code = generate_code(prompt)
        except ReasoningError:
            return None
        # question grounds SummarizeStep's explain prompt with the
        # original request (see summarize_step.py 1.2.0) -- without it,
        # the explain step only sees bare code output like "Output:\n36.0\n"
        # with no idea what question it answers.
        return {"code": code, "question": prompt}

    return None


def plan(prompt: str, project_id: str | None = None, consolidate_memory: bool = False) -> Plan:
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

    built_input = _build_skill_input(capability_name, prompt, project_id, consolidate_memory)
    if built_input is None:
        logger.warning(
            "plan_skill_input_unbuildable",
            capability_name=capability_name,
            project_id_present=bool(project_id),
        )
        return Plan(capability_type="reasoning", capability_name=None, source="llm")

    logger.info("plan_decided", capability_type="skill", capability_name=capability_name, source="llm")
    return Plan(capability_type="skill", capability_name=capability_name, input=built_input, source="llm")


def _coerce_skill_output(output, content=None):
    # Crash found live 2026-07-31 via llm_validate eval traffic (see
    # STATUS.md): SaveMemoryStep's StepResult.output is a dict
    # (key/value pair) -- structured data for internal use, not
    # human-facing text like WriteFileStep's "Saved to X (Y bytes)."
    # string. Any Skill ending in SaveMemoryStep (file_digest,
    # research_topic) returned that raw dict as the chat response,
    # which crashed validate_response()'s response.strip() with an
    # AttributeError -- a 500 on every such request, not just a bad
    # answer. Step output shapes aren't uniformly human-facing text,
    # so this boundary -- not each Step, and not validate_response()
    # -- is the right place to bridge that: it is the one spot that
    # already knows both "this is a Skill's final output" and "this
    # has to become a string for the chat response."
    #
    # Real gap found live 2026-08-16 while auditing every Skill's
    # context-flow bridge, in two stages:
    #
    # Stage 1 -- SaveMemoryStep's dict case: this originally returned
    # ONLY the confirmation ("Saved to memory under 'last_research'.")
    # and discarded output["value"] -- the actual research/digest
    # content -- entirely. Confirmed live: a real "research the history
    # of jazz music" request correctly ran the full web_search ->
    # summarize -> save_memory pipeline and produced a real summary
    # internally, but the /chat response was just the terse save
    # confirmation -- the summary itself never reached the conversation.
    #
    # Stage 2 -- the same defect class, one level up: WriteFileStep has
    # the identical problem for a different reason. Its Tool
    # (WriteFileTool) returns its OWN operational confirmation string
    # ("Saved to X (Y bytes)."), not a dict -- so it never hit stage 1's
    # fix at all, and research_and_save_file (WebSearchStep ->
    # SummarizeStep -> WriteFileStep) had the exact same silent-content
    # bug confirmed live the same way: "research the history of the
    # samba and save a summary to samba_history.txt" produced only
    # "Saved to samba_history.txt (887 bytes)." as the response.
    #
    # Root cause common to both: execute_plan() below only ever reads
    # the LAST step's own output, but for every Skill that ends in a
    # side-effecting "sink" step (save/write, as opposed to summarize
    # itself), the actual substance lives in an EARLIER step
    # (context['summarize']), not the sink's own confirmation. `content`
    # is that earlier value, passed in by execute_plan() when the last
    # step isn't summarize itself -- this function now leads with it
    # whenever present, regardless of which sink produced the trailing
    # confirmation, instead of special-casing SaveMemoryStep's dict
    # shape as stage 1 did.
    if isinstance(output, dict):
        key = output.get("key", "memory")
        value = content or output.get("value")
        if value:
            return f"{value}\n\n(Saved to memory under '{key}'.)"
        return "Saved to memory under '" + str(key) + "'."
    if content:
        return f"{content}\n\n({output})" if output not in (None, content) else str(content)
    if output is None:
        return "Done."
    return str(output)


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
            output = result.context.get(last_step_name, "Done.")
            # See _coerce_skill_output's "Stage 2" comment: if the
            # terminal step is a side-effecting sink rather than
            # `summarize` itself, and an earlier summarize step
            # produced real content, that's the substance to show --
            # not the sink's own confirmation string.
            content = result.context.get("summarize") if last_step_name != "summarize" else None
            return _coerce_skill_output(output, content)

        return f"Couldn't complete this: {result.error}"

    return None
