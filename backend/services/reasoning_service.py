"""
Single entry point for all LLM calls (ARCHITECTURE.md's Reasoning Service —
"the only component that directly communicates with language models").

Right now this just delegates to ollama_service, which only talks to Ollama.
The point of this seam is that every caller (plugin_manager, memory_extraction,
main.py) imports from HERE, not from ollama_service directly — so adding a
second provider later (e.g. an OpenAI-compatible API) means changing this one
module, not every call site.
"""

from services.ollama_service import generate_response as _ollama_generate
from services.validation_service import REASONING_FAILURE_PREFIXES as FAILURE_PREFIXES
from services.routing import FAST_MODEL

# ollama_service.py deliberately never raises for expected failure modes
# (unreachable, timeout, bad response) — it returns a human-readable string
# instead, which is the right behavior for a chat reply. But that same string
# looks like a normal successful result to automated callers (a Step
# checking success, not a human reading a chat bubble) — see
# services/steps/summarize_step.py, which found this the hard way: a
# "Could not reach Ollama" string got treated as a valid summary and nearly
# got saved to memory as one. generate_strict() below exists for exactly
# those callers.
#
# FAILURE_PREFIXES lives in validation_service.py now, not here — it's the
# same list E2's Validator uses to catch this exact failure class before
# delivery. One source of truth instead of two copies that can drift.


class ReasoningError(Exception):
    pass


def _is_failure_message(text: str) -> bool:
    return isinstance(text, str) and text.startswith(FAILURE_PREFIXES)


def generate(prompt: str, model: str = FAST_MODEL, history=None, memory=None, images=None) -> str:
    """Graceful variant — returns a human-readable string even on failure.
    Use this for anything a user will read directly (chat responses).

    images (added 2026-08-02): list of base64-encoded strings, no
    data:image/... prefix — see main.py's ChatRequest.images and
    routing.py's VISION_MODEL. Only the reasoning path accepts images;
    generate_strict() below deliberately does not, since every caller of
    generate_strict() is an internal Step/pipeline call that never has
    an attached image to begin with."""
    # Provider selection would branch here once a second provider exists —
    # e.g. by model name prefix, or a config flag. Only one provider today.
    return _ollama_generate(prompt, model=model, history=history, memory=memory, images=images)


def generate_strict(prompt: str, model: str = FAST_MODEL, history=None, memory=None) -> str:
    """Strict variant — raises ReasoningError on failure instead of
    returning a friendly string. Use this for automated callers (Steps,
    pipelines) that check success programmatically rather than displaying
    the result to a human."""
    result = _ollama_generate(prompt, model=model, history=history, memory=memory)
    if _is_failure_message(result):
        raise ReasoningError(result)
    return result
