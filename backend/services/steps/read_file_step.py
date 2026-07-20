from services.steps.base import Step, StepResult
from services.tools.registry import registry


class ReadFileStep(Step):
    """Deterministic — wraps FileTool directly. Reads context['filename']."""
    name = "read_file"
    description = "Reads a file from the workspace using the file Tool."

    def run(self, context: dict) -> StepResult:
        filename = context.get("filename")
        if not filename:
            return StepResult(success=False, error="context['filename'] is required")

        tool = registry.get("file")
        result = tool.execute(tool.InputModel(filename=filename))
        return StepResult(success=result.success, output=result.output, error=result.error)
