from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class AppendFileStep(Step):
    """Deterministic — wraps AppendFileTool directly. Same shape as
    WriteFileStep, mirrored for the same reason AppendFileTool mirrors
    WriteFileTool (STATUS.md item 25): a Skill composing this in the
    future needs it available as a Step, not just directly plannable as
    a standalone Tool. No Skill uses it yet — added for parity with
    every other Tool having a matching Step, not because a specific
    Skill design needs it today.

    source_key is configurable, same reasoning as WriteFileStep/
    SummarizeStep/SaveMemoryStep: a hardcoded predecessor key only
    serves one Skill. Reads context['filename'] and context[source_key]
    as the content to append."""
    name = "append_file"
    description = "Appends context[source_key] to a file named context['filename'] in the workspace, creating it first if it doesn't exist."
    script = ScriptMeta(
        identifier="step.append_file",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, alongside AppendFileTool",),
        permissions=("filesystem:write",),
    )

    def __init__(self, source_key: str = "summarize"):
        self.source_key = source_key

    def run(self, context: dict) -> StepResult:
        filename = context.get("filename")
        content = context.get(self.source_key)

        if not filename:
            return StepResult(success=False, error="context['filename'] is required")
        if not content:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        tool = registry.get("append_file")
        result = tool.execute(tool.InputModel(filename=filename, content=str(content)))
        return StepResult(success=result.success, output=result.output, error=result.error)
