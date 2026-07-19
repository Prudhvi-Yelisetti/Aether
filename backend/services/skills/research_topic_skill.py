"""
The proof-of-concept Skill for Phase D (ROADMAP.md D3): "compose the
existing 3 tools into at least one real multi-step Skill."

research_topic: query -> web search (Tool, deterministic) -> summarize
(reasoning) -> save to memory (Tool, deterministic). This is the same
sequence plugin_manager.py's "web" branch already does ad hoc inline —
here it's a formal, reusable, testable Skill instead of inline code.

Deliberately NOT wired into the live /chat request path yet. Deciding
*when* to invoke a Skill vs. a bare Tool vs. raw reasoning is a Planning
Service's job (Phase E), and main.py's routing is still a hardcoded
rule/LLM decision (see routing.py) — wiring a Skill in now would mean
guessing at Planning Service behavior ahead of actually building it.
"""

from services.skills.base import Skill
from services.steps.web_search_step import WebSearchStep
from services.steps.summarize_step import SummarizeStep
from services.steps.save_memory_step import SaveMemoryStep


class ResearchTopicSkill(Skill):
    name = "research_topic"
    description = "Searches the web for a topic, summarizes it, and saves the summary to project memory."
    steps = [
        WebSearchStep(),
        SummarizeStep(),
        SaveMemoryStep(),
    ]
