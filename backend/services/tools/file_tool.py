from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from plugins.file_reader import read_file


class FileToolInput(BaseModel):
    filename: str


class FileTool(Tool):
    name = "file"
    description = "Reads a file's contents from the local workspace directory."
    InputModel = FileToolInput

    def execute(self, input: FileToolInput) -> ToolResult:
        raw = read_file(input.filename)
        is_error = raw.startswith(("Access denied", "File not found", "Not a file"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
