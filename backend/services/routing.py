"""
Model selection only.

Phase B's routing.py originally bundled model selection AND tool decision
into one route() call. That tool-decision half is now superseded by
services/planning_service.py (Phase E1), which makes a strictly better
decision — grounded in the live Tool/Skill registries rather than a
hardcoded 3-way choice, and able to select a Skill, not just a bare Tool.

What's left here is just model selection, which — per ARCHITECTURE.md —
belongs to the Reasoning Service's responsibilities, not Planning's
("Reasoning Service: Model selection, Prompt construction..."). It stays
in its own small function rather than moving into reasoning_service.py
outright; that consolidation is a reasonable future cleanup, not required
for E1 to be correct.
"""

from services.logging_config import get_logger

logger = get_logger("aether.routing")


# Live 2026-07-21: hardcoded "llama3"/"mistral" never existed on this
# machine's Ollama install (only qwen3.5:9b and qwen3-coder:latest are
# pulled) — verified this was silently broken for every non-math request
# even with Ollama running, not just while it was down. See STATUS.md.
STRONG_MODEL = "qwen3-coder:latest"
FAST_MODEL = "qwen3.5:9b"


def route_model(prompt: str) -> str:
    prompt_lower = prompt.lower()

    # coding → strong model
    if any(word in prompt_lower for word in ["code", "program", "c++", "python", "java"]):
        return STRONG_MODEL

    # complex explanation → strong model
    elif any(word in prompt_lower for word in ["explain", "detail", "theory", "how", "why"]):
        return STRONG_MODEL

    # long input → strong model
    elif len(prompt) > 300:
        return STRONG_MODEL

    # simple chat → fast model
    elif len(prompt) < 50:
        return FAST_MODEL

    # default
    return FAST_MODEL


def select_model(prompt: str, mode: str) -> str:
    if mode == "fast":
        return FAST_MODEL
    if mode == "powerful":
        return STRONG_MODEL
    return route_model(prompt)
