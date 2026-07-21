from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class WebSearchStep(Step):
    """Deterministic — wraps WebTool directly, no reasoning involved.
    Reads context['query']."""
    name = "web_search"
    description = "Searches the web for context['query'] using the web Tool."
    script = ScriptMeta(
        step_id="step.web_search",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, Phase D",),
    )

    def run(self, context: dict) -> StepResult:
        query = context.get("query")
        if not query:
            return StepResult(success=False, error="context['query'] is required")

        tool = registry.get("web")
        result = tool.execute(tool.InputModel(query=query))
        return StepResult(success=result.success, output=result.output, error=result.error)
