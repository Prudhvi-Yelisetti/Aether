from pydantic import BaseModel

from services.tools.base import Tool, ToolResult
from services.object_meta import ObjectMeta
from plugins.code_runner import run_code


class CodeToolInput(BaseModel):
    code: str


class CodeTool(Tool):
    name = "code"
    description = "Executes Python code in a sandboxed environment and returns stdout/stderr."
    InputModel = CodeToolInput
    meta = ObjectMeta(
        identifier="tool.code",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: original implementation used a keyword blocklist "
            "(FORBIDDEN = [\"import os\", ...]) -- bypassable via importlib, "
            "__import__, attribute access, and any keyword not on the list. "
            "A blocklist on source text can never be complete.",
            "1.1.0: replaced with OS-level isolation via bubblewrap (bwrap) "
            "-- --unshare-all (no network, can't see/signal host processes), "
            "read-only host filesystem, fresh writable tmpfs. Phase A "
            "security fix, see plugins/code_runner.py.",
        ),
        permissions=("code:execute",),
    )

    def execute(self, input: CodeToolInput) -> ToolResult:
        raw = run_code(input.code)
        # run_code's string prefixes ("Output:", "Error", "Execution timed
        # out", "Execution blocked") are its existing return convention —
        # preserved here rather than changed, to avoid touching the sandbox
        # logic itself in the same change as this wrapper.
        is_error = raw.startswith(("Error", "Execution timed out", "Execution blocked"))
        return ToolResult(success=not is_error, output=raw, error=raw if is_error else None)
