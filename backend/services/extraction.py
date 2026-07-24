"""
Shared natural-language -> structured-input extraction helpers.

These were originally duplicated inline inside plugin_manager.py's
execute_plugin(). Pulled out here so the Planner (services/planning_service.py)
can build the same structured input for a Tool OR a Skill without copying
the same prompts a second time — a Skill like ResearchTopicSkill needs a
clean search query exactly the same way the bare "web" Tool path does.
"""

from services.reasoning_service import generate_strict, ReasoningError

MAX_SLUG_LENGTH = 60


def slugify_filename(text: str, extension: str = "txt") -> str:
    """Deterministic — no LLM call, matching extract_filename()'s own
    reasoning for why this doesn't need one. Turns free text (e.g. a
    search query) into a safe filename: lowercase, non-alphanumeric
    collapsed to underscores, truncated. Used by
    ResearchAndSaveFileSkill so it doesn't need to ask the user (or an
    LLM) to name the output file — the topic itself is a reasonable
    default name."""
    cleaned = "".join(c if c.isalnum() else "_" for c in text.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_") or "untitled"
    return f"{cleaned[:MAX_SLUG_LENGTH]}.{extension}"


def extract_filename(prompt: str) -> str | None:
    """Deterministic — no LLM call. A word containing '.' is assumed to be
    a filename. This is a parsing heuristic, not reasoning, so it doesn't
    need generate()/generate_strict() at all."""
    return next((p for p in prompt.split() if "." in p), None)


def extract_search_query(prompt: str) -> str:
    """Uses generate_strict() because the result feeds into a search call —
    an automated next step, not something a human reads directly. Falls
    back to the raw prompt (not the LLM's failure string) if extraction
    fails, so a search still runs instead of the whole path crashing."""
    query_prompt = f"""
Extract the main search query from this user request.
Return ONLY the search query.

Request: {prompt}
"""
    try:
        return generate_strict(query_prompt, model="qwen3.5:9b").strip()
    except ReasoningError:
        return prompt


def generate_code(prompt: str) -> str:
    """Uses generate_strict() and lets ReasoningError propagate — the
    caller must decide what to do (plugin_manager.py returns a clean error
    message; the Planner does the same). Feeding a failure string into the
    sandbox as if it were Python was a real bug fixed in Phase E0 — see
    ROADMAP.md."""
    code_prompt = f"""
You are a Python code generator.

Convert the user's request into correct Python code.

Rules:
- Output ONLY Python code
- No explanation
- Ensure code runs correctly

Request: {prompt}
"""
    return generate_strict(code_prompt, model="qwen3-coder:latest")
