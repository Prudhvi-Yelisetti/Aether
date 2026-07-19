"""
Unified routing: one function decides both the model AND whether a tool is
needed, instead of the previous two disconnected systems (router.py's
route_model() feeding the final response, and plugin_manager.py's
ai_decide_plugin() feeding tool selection with no knowledge of the model
choice).

Also fixes a real cost bug: ai_decide_plugin() is an LLM call, and previously
ran on *every* request regardless of mode. decide_plugin() (free, rule-based)
already covers the common tool-trigger phrases ("run python", "search",
"read x.txt", "calculate") — this module tries that first and only falls
back to the LLM-based decision when the rules don't match anything, cutting
the extra Ollama round-trip for most tool-using requests.
"""

from dataclasses import dataclass
from typing import Optional

from services.logging_config import get_logger
from services.router import route_model
from services.plugin_manager import decide_plugin, ai_decide_plugin

logger = get_logger("aether.routing")


@dataclass
class RoutingDecision:
    model: str
    tool: Optional[str]
    tool_source: str  # "rule" | "llm" | "none" — for observability


def route(prompt: str, mode: str = "smart") -> RoutingDecision:
    # -------- Model selection (unchanged logic, just centralized here) --------
    if mode == "fast":
        model = "mistral"
    elif mode == "powerful":
        model = "llama3"
    else:
        model = route_model(prompt)

    # -------- Tool selection: free rules first, LLM fallback only if needed --------
    tool = decide_plugin(prompt)
    tool_source = "rule" if tool else "none"

    if tool is None:
        tool = ai_decide_plugin(prompt)
        tool_source = "llm" if tool else "none"

    decision = RoutingDecision(model=model, tool=tool, tool_source=tool_source)

    logger.info(
        "routing_decision",
        mode=mode,
        model=model,
        tool=tool,
        tool_source=tool_source,
    )

    return decision
