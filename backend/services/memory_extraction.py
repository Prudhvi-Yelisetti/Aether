"""
Memory extraction and storage.

Replaces the old string-matching extract_memory() in main.py, which had two
problems: low recall (only caught exact phrases like "i like", "i prefer")
and unbounded duplicate writes (every mention of a preference wrote a new
row, with no way to tell "I like Python" from "I like Python" said twice
vs. "I used to like Python, now I prefer Rust").

This version asks the LLM to extract structured facts, and upserts them —
one row per (project_id, key), value replaced on conflict — so memory stays
current instead of accumulating unbounded, potentially contradictory rows.
"""

import json

from services.logging_config import get_logger
from services.ollama_service import generate_response

logger = get_logger("aether.memory")

EXTRACTION_PROMPT = """Extract durable facts about the user from this message, if any.
Only extract things that would still be true later (name, stated preferences,
skills, goals) — not one-off requests or questions.

Return ONLY a JSON object mapping short keys to short values, nothing else.
If there is nothing durable to extract, return {{}}.

Examples:
"My name is Alex" -> {{"name": "Alex"}}
"I like hiking and Python" -> {{"preference_hiking": "hiking", "preference_python": "Python"}}
"What's the weather?" -> {{}}

Message: {prompt}
"""


def extract_memory_facts(prompt: str) -> dict:
    """Returns {key: value} facts extracted from the prompt, or {} on failure.
    Never raises — a bad LLM response should not break the chat request."""
    try:
        raw = generate_response(
            EXTRACTION_PROMPT.format(prompt=prompt),
            model="mistral",
        )
        # Models sometimes wrap JSON in prose or code fences; grab the
        # {...} span rather than requiring an exact-match response.
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end < start:
            return {}

        facts = json.loads(raw[start:end + 1])
        if not isinstance(facts, dict):
            return {}

        return {
            str(k): str(v) for k, v in facts.items()
            if isinstance(k, str) and v not in (None, "", [])
        }
    except Exception:
        logger.warning("memory_extraction_failed", exc_info=True)
        return {}
