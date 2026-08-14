from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class WebSearchStep(Step):
    """Deterministic — wraps WebTool directly, no reasoning involved.
    Reads context['query']."""
    name = "web_search"
    description = "Searches the web for context['query'] using the web Tool."
    script = ScriptMeta(
        identifier="step.web_search",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, Phase D",
            "Note (no version bump -- plugins/web_search.py changed, this "
            "Step didn't): DuckDuckGo Instant Answer API's narrow exact-"
            "topic keying caused real live failures; fixed with tighter "
            "query extraction upstream and a Wikipedia OpenSearch fallback "
            "with a real second bug (missing User-Agent header, silently "
            "swallowed by a bare except) caught and fixed same day — see "
            "STATUS.md item 8.",
        ),
        permissions=("network:outbound",),
    )

    def run(self, context: dict) -> StepResult:
        query = context.get("query")
        if not query:
            return StepResult(success=False, error="context['query'] is required")

        tool = registry.get("web")
        result = tool.execute(tool.InputModel(query=query))
        return StepResult(success=result.success, output=result.output, error=result.error)
