from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from plugins.code_runner import run_code


class CodeToolInput(BaseModel):
    code: str


class CodeTool(Tool):
    name = "code"
    description = "Executes Python code in a sandboxed environment and returns stdout/stderr."
    InputModel = CodeToolInput

    def execute(self, input: CodeToolInput) -> ToolResult:
        raw = run_code(input.code)
        # run_code's string prefixes ("Output:", "Error", "Execution timed
        # out", "Execution blocked") are its existing return convention —
        # preserved here rather than changed, to avoid touching the sandbox
        # logic itself in the same change as this wrapper.
        is_error = raw.startswith(("Error", "Execution timed out", "Execution blocked"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
