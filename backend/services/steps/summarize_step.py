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
        identifier="step.summarize",
        version="1.2.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, hardcoded to read context['web_search'], Phase D",
            "1.1.0: source_key made configurable so FileDigestSkill and "
            "CalculateAndExplainSkill could reuse this Step after a different "
            "predecessor, instead of duplicating it",
            "1.2.0: optional context['question'] grounds the explain prompt "
            "with the original request -- fixes calculate_and_explain "
            "explaining bare numeric output with no idea what it means "
            "(found live via llm_validate eval traffic, STATUS.md item 13). "
            "No-op for any caller that doesn't set context['question'].",
        ),
        # Calls the Reasoning Service (Ollama, local) — no filesystem or
        # network access of its own beyond that. "reasoning:generate" is
        # its own category, not "network:outbound", since it never talks
        # to anything outside this machine (Ollama runs locally).
        permissions=("reasoning:generate",),
    )

    def __init__(self, source_key: str = "web_search"):
        self.source_key = source_key

    def run(self, context: dict) -> StepResult:
        raw_text = context.get(self.source_key)
        if not raw_text:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        # Bug found live 2026-07-31 via llm_validate eval traffic (see
        # STATUS.md item 13): calculate_and_explain's raw_text is bare
        # code output ("Output:\n36.0\n") with no indication of what
        # question it answers -- "Explain this simply: Output:\n36.0\n"
        # left the model with nothing to explain, so it asked the user
        # for context instead of just answering. research_topic's web
        # search results and file_digest's file content are both
        # self-describing text, so this never surfaced there.
        #
        # context['question'] is optional and unused by every existing
        # caller except CalculateAndExplainSkill (via
        # planning_service.py's _build_skill_input) -- when absent,
        # behavior is byte-for-byte the same prompt as before.
        question = context.get("question")
        if question:
            prompt = f"Question: {question}\n\nResult: {raw_text}\n\nExplain the result simply, in the context of the question."
        else:
            prompt = f"Explain this simply:\n{raw_text}"

        try:
            summary = generate_strict(prompt, model=FAST_MODEL)
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
