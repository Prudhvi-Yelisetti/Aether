from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
from plugins.file_reader import read_file


class FileToolInput(BaseModel):
    filename: str


class FileTool(Tool):
    name = "file"
    description = "Reads a file's contents from the local workspace directory."
    InputModel = FileToolInput
    meta = ObjectMeta(
        identifier="tool.file",
        version="1.0.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, Phase A -- reads allowlisted "
            "to WORKSPACE_DIR only via resolve_safe_path(), which rejects "
            "any path (via .., symlinks, or an absolute path elsewhere) "
            "that would escape it. See plugins/file_reader.py.",
        ),
        permissions=("filesystem:read",),
    )

    def execute(self, input: FileToolInput) -> ToolResult:
        raw = read_file(input.filename)
        is_error = raw.startswith(("Access denied", "File not found", "Not a file"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
