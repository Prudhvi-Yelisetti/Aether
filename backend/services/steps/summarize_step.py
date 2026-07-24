from services.steps.base import Step, StepResult, ValidationResult
from services.steps.script_meta import ScriptMeta
from services.reasoning_service import generate_strict, ReasoningError
from services.routing import FAST_MODEL

MIN_SUMMARY_LENGTH = 10


class SummarizeStep(Step):
    """Reasoning-based — this Step is explicitly allowed to call the
    Reasoning Service (unlike a Tool).

    source_key is configurable rather than hardcoded to "web_search" —
    that hardcoding was a real design mistake caught while building a
    second Skill (FileDigestSkill) that wanted to reuse this exact Step
    after a different predecessor. Per ARCHITECTURE.md, Skills are
    supposed to "compose existing steps... instead of storing duplicated
    implementations" — a Step that only works after one specific
    predecessor isn't actually reusable, it just looks like it is until a
    second Skill tries to use it. See script.history for when this changed.

    Uses generate_strict() rather than generate(): a Step's success/failure
    is checked programmatically by Skill.run(), so a graceful-but-wrong
    "Could not reach Ollama" string masquerading as a real summary would
    silently corrupt the Skill (see the ReasoningError docstring in
    reasoning_service.py for how this was found)."""
    name = "summarize"
    description = "Summarizes the content at context[source_key] into plain language."
    script = ScriptMeta(
        step_id="step.summarize",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, hardcoded to read context['web_search'], Phase D",
            "1.1.0: source_key made configurable so FileDigestSkill and "
            "CalculateAndExplainSkill could reuse this Step after a different "
            "predecessor, instead of duplicating it",
        ),
    )

    def __init__(self, source_key: str = "web_search"):
        self.source_key = source_key

    def run(self, context: dict) -> StepResult:
        raw_text = context.get(self.source_key)
        if not raw_text:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        try:
            summary = generate_strict(f"Explain this simply:\n{raw_text}", model=FAST_MODEL)
            return StepResult(success=True, output=summary)
        except ReasoningError as e:
            return StepResult(success=False, error=str(e))

    def validate(self, result: StepResult) -> ValidationResult:
        base = super().validate(result)
        if not base.valid:
            return base
        if len(result.output.strip()) < MIN_SUMMARY_LENGTH:
            return ValidationResult(valid=False, reason=f"summary shorter than {MIN_SUMMARY_LENGTH} chars, likely degenerate")
        return ValidationResult(valid=True)
