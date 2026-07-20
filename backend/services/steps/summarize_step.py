from services.steps.base import Step, StepResult
from services.reasoning_service import generate_strict, ReasoningError


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
    second Skill tries to use it.

    Uses generate_strict() rather than generate(): a Step's success/failure
    is checked programmatically by Skill.run(), so a graceful-but-wrong
    "Could not reach Ollama" string masquerading as a real summary would
    silently corrupt the Skill (see the ReasoningError docstring in
    reasoning_service.py for how this was found)."""
    name = "summarize"
    description = "Summarizes the content at context[source_key] into plain language."

    def __init__(self, source_key: str = "web_search"):
        self.source_key = source_key

    def run(self, context: dict) -> StepResult:
        raw_text = context.get(self.source_key)
        if not raw_text:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        try:
            summary = generate_strict(f"Explain this simply:\n{raw_text}", model="mistral")
            return StepResult(success=True, output=summary)
        except ReasoningError as e:
            return StepResult(success=False, error=str(e))
