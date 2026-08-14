"""
Read-only, no-argument Tool — companion to FileTool/WriteFileTool. See
plugins/file_lister.py's docstring for why this exists.
"""

from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
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
    meta = ObjectMeta(
        identifier="tool.list_files",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, built to support FindFileStep's "
            "fuzzy filename matching (FindAndDigestFileSkill) -- \"File not "
            "found\" had been the most common permanent Tool/Skill failure "
            "before this existed, see STATUS.md.",
        ),
        # Lighter than FileTool's filesystem:read -- this only sees
        # filenames, never file contents.
        permissions=("filesystem:list",),
    )

    def execute(self, input: ListFilesToolInput) -> ToolResult:
        raw = list_files()
        return ToolResult(success=True, output=raw)
