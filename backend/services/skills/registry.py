"""
SkillRegistry: mirrors ToolRegistry (services/tools/registry.py). Not the
Planner itself — just makes "what Skills exist" queryable, the way
"what Tools exist" already is. A future Planner (Phase E1) needs both
registries to choose between Tool / Skill / raw reasoning.

None of these Skills are wired into the live /chat path yet. Deciding
when to invoke a Skill vs. a Tool vs. raw reasoning is the Planner's job —
see ROADMAP.md's note on E1 for why that's deliberately not built yet.
"""

from services.skills.base import Skill
from services.skills.research_topic_skill import ResearchTopicSkill
from services.skills.file_digest_skill import FileDigestSkill
from services.skills.calculate_and_explain_skill import CalculateAndExplainSkill


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
