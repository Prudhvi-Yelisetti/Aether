"""
The Skill contract (ARCHITECTURE.md's Skill Service: "a skill consists of
multiple reusable steps... compose existing steps into higher-level
abilities" instead of duplicating implementations).

A Skill is an ordered list of Steps sharing one context dict. Skill.run()
is also where validation lives for this phase: if any Step fails, execution
stops immediately and the failure is reported, rather than continuing with
a broken context (a real Validator Service comes in Phase E — this is the
minimal version: "did each step succeed" as the gate).

Skill is a plain class (not a @dataclass) deliberately: subclasses set
`name`, `description`, `steps` as class attributes (same pattern as Tool in
services/tools/base.py). A dataclass's generated __init__ would overwrite
those class attributes with its own field defaults on every instantiation —
exactly the bug this comment is here to stop someone from reintroducing.
"""

from dataclasses import dataclass

from services.steps.base import Step
from services.logging_config import get_logger

logger = get_logger("aether.skills")


@dataclass
class SkillResult:
    success: bool
    context: dict
    failed_step: str | None = None
    error: str | None = None


class Skill:
    name: str
    description: str
    steps: list[Step] = []

    def run(self, initial_context: dict) -> SkillResult:
        context = dict(initial_context)

        for step in self.steps:
            result = step.run(context)

            logger.info(
                "skill_step_ran",
                skill=self.name,
                step=step.name,
                success=result.success,
            )

            if not result.success:
                return SkillResult(
                    success=False,
                    context=context,
                    failed_step=step.name,
                    error=result.error,
                )

            context[step.name] = result.output

        return SkillResult(success=True, context=context)
