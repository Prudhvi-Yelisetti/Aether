from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from plugins.web_search import web_search


class WebToolInput(BaseModel):
    query: str


class WebTool(Tool):
    name = "web"
    description = "Searches the web (DuckDuckGo) for a query and returns a text summary of results."
    InputModel = WebToolInput

    def execute(self, input: WebToolInput) -> ToolResult:
        raw = web_search(input.query)
        is_error = raw.startswith(("Search failed", "No useful results"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
