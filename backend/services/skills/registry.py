"""
SkillRegistry: mirrors ToolRegistry (services/tools/registry.py). Not the
Planner itself — just makes "what Skills exist" queryable, the way
"what Tools exist" already is. services/planning_service.py (Phase E1)
uses both registries to choose between Tool / Skill / raw reasoning, and
is where a Skill's initial_context actually gets built from a live prompt
(see _build_skill_input() there) — every Skill registered here needs a
matching branch in that function to be reachable from /chat, not just
importable.
"""

from services.skills.base import Skill
from services.skills.research_topic_skill import ResearchTopicSkill
from services.skills.file_digest_skill import FileDigestSkill
from services.skills.calculate_and_explain_skill import CalculateAndExplainSkill
from services.skills.research_and_save_file_skill import ResearchAndSaveFileSkill


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills.keys())

    def describe_all(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "steps": [step.name for step in s.steps],
            }
            for s in self._skills.values()
        ]


registry = SkillRegistry()
registry.register(ResearchTopicSkill())
registry.register(FileDigestSkill())
registry.register(CalculateAndExplainSkill())
registry.register(ResearchAndSaveFileSkill())
