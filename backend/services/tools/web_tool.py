from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
from plugins.web_search import web_search


class WebToolInput(BaseModel):
    query: str


class WebTool(Tool):
    name = "web"
    description = "Searches the web (DuckDuckGo) for a query and returns a text summary of results."
    InputModel = WebToolInput
    meta = ObjectMeta(
        identifier="tool.web",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, DuckDuckGo Instant Answer API only",
            "1.1.0: DDG's narrow exact-topic keying caused real live search "
            "failures (STATUS.md item 7/8) -- added a Wikipedia OpenSearch + "
            "summary fallback for when DDG returns nothing. Caught a real "
            "bug in that fallback's own first version: Wikipedia's API "
            "returns 403 without a User-Agent header, silently swallowed "
            "by a bare except -- fixed same day.",
        ),
        permissions=("network:outbound",),
    )

    def execute(self, input: WebToolInput) -> ToolResult:
        raw = web_search(input.query)
        is_error = raw.startswith(("Search failed", "No useful results"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
