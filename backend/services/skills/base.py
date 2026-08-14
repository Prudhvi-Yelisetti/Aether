"""
The Skill contract (ARCHITECTURE.md's Skill Service: "a skill consists of
multiple reusable steps... compose existing steps into higher-level
abilities" instead of duplicating implementations).

A Skill is an ordered list of Steps sharing one context dict. Skill.run()
is where the interim validation gate lives for this phase: a Step must both
succeed AND pass its own validate() (see services/steps/base.py) or
execution stops immediately, rather than continuing with a broken context.
A real Validator/Decision Service (Phase E2/E3) will eventually own this
gating logic at a higher level; this is the minimal version.

Skill.run() also records per-Step metrics (services/storage/step_metrics_store.py)
after every Step call — latency, success, and validation outcome — so a
future Cost Engine or Evolution Service has real data instead of nothing.

Skill is a plain class (not a @dataclass) deliberately: subclasses set
`name`, `description`, `steps` as class attributes (same pattern as Tool in
services/tools/base.py). A dataclass's generated __init__ would overwrite
those class attributes with its own field defaults on every instantiation —
exactly the bug this comment is here to stop someone from reintroducing.
"""

import time
from dataclasses import dataclass

from services.steps.base import Step
from services.object_meta import ObjectMeta
from services.logging_config import get_logger
from storage.step_metrics_store import log_step_metric

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
    # AI Object Model metadata (STATUS.md item 24) — every concrete Skill
    # sets this. permissions is deliberately left at ObjectMeta's default
    # empty tuple here: a Skill's real blast radius is the union of its
    # Steps' own permissions, computed dynamically in
    # SkillRegistry.describe_all() rather than hand-duplicated per Skill
    # — see that method's comment for why.
    meta: ObjectMeta

    def run(self, initial_context: dict, request_id: str | None = None) -> SkillResult:
        context = dict(initial_context)

        for step in self.steps:
            start = time.monotonic()
            result = step.run(context)
            validation = step.validate(result)
            latency_ms = round((time.monotonic() - start) * 1000, 2)

            logger.info(
                "skill_step_ran",
                skill=self.name,
                step=step.name,
                success=result.success,
                valid=validation.valid,
            )

            log_step_metric(
                step_name=step.name,
                step_version=getattr(step.script, "version", None),
                skill_name=self.name,
                request_id=request_id,
                success=result.success,
                valid=validation.valid,
                validation_reason=validation.reason,
                latency_ms=latency_ms,
            )

            if not validation.valid:
                return SkillResult(
                    success=False,
                    context=context,
                    failed_step=step.name,
                    error=validation.reason or result.error,
                )

            context[step.name] = result.output

        return SkillResult(success=True, context=context)
