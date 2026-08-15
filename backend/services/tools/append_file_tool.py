"""
Closes the gap file_writer.py's own docstring named explicitly (STATUS.md
item 25): WriteFileTool always overwrites, no way to maintain a running
file (a log, a journal, notes accumulated across messages) without
reading the whole thing back first just to re-write it with one line
added.
"""

from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
from plugins.file_appender import append_file


class AppendFileToolInput(BaseModel):
    filename: str
    content: str


class AppendFileTool(Tool):
    name = "append_file"
    description = "Adds text content to the end of a file in the local workspace directory, creating it first if it doesn't exist yet."
    InputModel = AppendFileToolInput
    meta = ObjectMeta(
        identifier="tool.append_file",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation -- WriteFileTool's own "
            "docstring named this gap explicitly (\"no append mode... a "
            "considered addition later\") since item 8. Same "
            "WORKSPACE_DIR allowlisting via resolve_safe_path(), same "
            "MAX_FILE_BYTES ceiling applied to the file's total size "
            "after appending, not just the new content -- see "
            "plugins/file_appender.py.",
        ),
        permissions=("filesystem:write",),
    )

    def execute(self, input: AppendFileToolInput) -> ToolResult:
        raw = append_file(input.filename, input.content)
        is_error = raw.startswith(("Access denied", "Append would grow"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
