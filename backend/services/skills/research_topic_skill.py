"""
The original Skill built in Phase D (ROADMAP.md D3): query -> web search
(Tool, deterministic) -> summarize (reasoning) -> save to memory (Tool,
deterministic).

Wired into the live /chat request path via planning_service.py's
_build_skill_input() as of Phase E1 -- this docstring previously said
"deliberately NOT wired in yet," stale since that landed; corrected
2026-08-14 (STATUS.md item 24) while adding this Skill's meta below.
"""

from services.skills.base import Skill
from services.steps.web_search_step import WebSearchStep
from services.steps.summarize_step import SummarizeStep
from services.steps.save_memory_step import SaveMemoryStep
from services.object_meta import ObjectMeta


class ResearchTopicSkill(Skill):
    name = "research_topic"
    description = "Searches the web for a topic, summarizes it, and saves the summary to project memory."
    steps = [
        WebSearchStep(),
        SummarizeStep(source_key="web_search"),
        SaveMemoryStep(source_key="summarize", memory_key="last_research"),
    ]
    meta = ObjectMeta(
        identifier="skill.research_topic",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, Phase D -- the first Skill "
            "built, establishing the compose-existing-Steps pattern every "
            "later Skill reused instead of duplicating implementations.",
        ),
    )
