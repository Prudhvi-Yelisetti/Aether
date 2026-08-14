"""
Symmetric counterpart to FileTool (read-only, file_tool.py) — this session's
Tool/Skill expansion. Before this, Aether could read files but never create
or save one, which meant a Skill could summarize something but had nowhere
to persist that output except project memory (SaveMemoryStep). Real gap,
now closed.
"""

from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
from plugins.file_writer import write_file


class WriteFileToolInput(BaseModel):
    filename: str
    content: str


class WriteFileTool(Tool):
    name = "write_file"
    description = "Writes text content to a file in the local workspace directory, creating or overwriting it."
    InputModel = WriteFileToolInput
    meta = ObjectMeta(
        identifier="tool.write_file",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation -- symmetric counterpart to "
            "FileTool (read-only). Before this, Aether could read files "
            "but never create/save one, so a Skill could summarize "
            "something but had nowhere to persist it except project "
            "memory. Scoped to WORKSPACE_DIR, same allowlisting as "
            "FileTool -- see plugins/file_writer.py.",
        ),
        permissions=("filesystem:write",),
    )

    def execute(self, input: WriteFileToolInput) -> ToolResult:
        raw = write_file(input.filename, input.content)
        is_error = raw.startswith(("Access denied", "Content too large"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
