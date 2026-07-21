from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class ReadFileStep(Step):
    """Deterministic — wraps FileTool directly. Reads context['filename']."""
    name = "read_file"
    description = "Reads a file from the workspace using the file Tool."
    script = ScriptMeta(
        step_id="step.read_file",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, built for FileDigestSkill",),
    )

    def run(self, context: dict) -> StepResult:
        filename = context.get("filename")
        if not filename:
            return StepResult(success=False, error="context['filename'] is required")

        tool = registry.get("file")
        result = tool.execute(tool.InputModel(filename=filename))
        return StepResult(success=result.success, output=result.output, error=result.error)
