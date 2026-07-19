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


def generate(prompt: str, model: str = "llama3", history=None, memory=None) -> str:
    # Provider selection would branch here once a second provider exists —
    # e.g. by model name prefix, or a config flag. Only one provider today.
    return _ollama_generate(prompt, model=model, history=history, memory=memory)
