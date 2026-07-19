from services.steps.base import Step, StepResult
from services.reasoning_service import generate_strict, ReasoningError


class SummarizeStep(Step):
    """Reasoning-based — this Step is explicitly allowed to call the
    Reasoning Service (unlike a Tool). Reads context['web_search'] (the
    previous step's output, by convention: context[step.name]).

    Uses generate_strict() rather than generate(): a Step's success/failure
    is checked programmatically by Skill.run(), so a graceful-but-wrong
    "Could not reach Ollama" string masquerading as a real summary would
    silently corrupt the Skill (see the ReasoningError docstring in
    reasoning_service.py for how this was found)."""
    name = "summarize"
    description = "Summarizes context['web_search'] into plain language."

    def run(self, context: dict) -> StepResult:
        raw_text = context.get("web_search")
        if not raw_text:
            return StepResult(success=False, error="context['web_search'] is required")

        try:
            summary = generate_strict(f"Explain this simply:\n{raw_text}", model="mistral")
            return StepResult(success=True, output=summary)
        except ReasoningError as e:
            return StepResult(success=False, error=str(e))
