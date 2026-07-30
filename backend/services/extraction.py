"""
Shared natural-language -> structured-input extraction helpers.

These were originally duplicated inline inside plugin_manager.py's
execute_plugin(). Pulled out here so the Planner (services/planning_service.py)
can build the same structured input for a Tool OR a Skill without copying
the same prompts a second time — a Skill like ResearchTopicSkill needs a
clean search query exactly the same way the bare "web" Tool path does.
"""

from services.reasoning_service import generate_strict, ReasoningError
from services.routing import FAST_MODEL, STRONG_MODEL

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
    fails, so a search still runs instead of the whole path crashing.

    Prompt tightened 2026-07-23 (see STATUS.md): the original wording let
    the model add filler ("research", "look up", "information about") and
    reorder the topic itself, e.g. "the Great Wall of China" ->
    "Great Wall of China research". That reordering alone was enough to
    make DuckDuckGo's Instant Answer API return nothing for a topic it
    otherwise recognizes fine — its keying is exact-topic-narrow, not
    fuzzy. Preserving the request's own wording gives that narrow API a
    real chance to match, on top of the Wikipedia fallback added to
    web_search.py for when it still doesn't."""
    query_prompt = f"""
Extract the core topic or entity this request is about — the way it
would appear as an encyclopedia article title, not a description of
what to do with it.

Preserve the exact wording and word order used for the topic in the
request itself. Do not add words like "research", "information about",
"details on", or "look up". Do not paraphrase or reorder the topic's
own words.

Return ONLY the topic, nothing else.

Request: {prompt}
"""
    try:
        return generate_strict(query_prompt, model=FAST_MODEL).strip()
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
    return generate_strict(code_prompt, model=STRONG_MODEL)


def extract_write_content(prompt: str) -> str:
    """Uses generate_strict() — same reasoning as extract_search_query():
    feeds an automated next step (WriteFileTool), not something a human
    reads directly.

    Added 2026-07-27: found live, via a real prompt through the actual
    UI ("List the files in the workspace"), that a directly-selected
    tool:write_file or tool:list_files (not routed through a Skill) fell
    through execute_plugin()'s hardcoded if/elif chain and silently
    returned None — that dispatcher predates both tools and was never
    updated for them. This function is part of that fix: gives
    execute_plugin()'s new write_file branch a way to pull the actual
    content to write out of the request, the same way it already pulls
    a search query or generated code."""
    content_prompt = f"""
Extract only the exact text content the user wants written to a file,
from this request. Do not include the filename, instructions, or any
commentary — only the content itself.

Return ONLY that content, nothing else.

Request: {prompt}
"""
    return generate_strict(content_prompt, model=FAST_MODEL).strip()
