"""
Read-only, no-argument Tool — companion to FileTool/WriteFileTool. See
plugins/file_lister.py's docstring for why this exists.
"""

from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from plugins.file_lister import list_files


class ListFilesToolInput(BaseModel):
    """No fields — listing the workspace takes no arguments. An empty
    pydantic model is fine here; the Tool base contract (see
    services/tools/base.py) requires an InputModel for every tool, not
    that every tool actually needs input."""
    pass


class ListFilesTool(Tool):
    name = "list_files"
    description = "Lists the files currently in the local workspace directory."
    InputModel = ListFilesToolInput

    def execute(self, input: ListFilesToolInput) -> ToolResult:
        raw = list_files()
        return ToolResult(success=True, output=raw)
