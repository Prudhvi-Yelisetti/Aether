"""
The original Skill built in Phase D (ROADMAP.md D3): query -> web search
(Tool, deterministic) -> summarize (reasoning) -> save to memory (Tool,
deterministic).

Deliberately NOT wired into the live /chat request path yet — see
services/skills/registry.py's module docstring for why.
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
        SummarizeStep(source_key="web_search"),
        SaveMemoryStep(source_key="summarize", memory_key="last_research"),
    ]
