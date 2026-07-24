from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class WriteFileStep(Step):
    """Deterministic — wraps WriteFileTool directly.

    source_key is configurable, same reasoning as SummarizeStep/
    SaveMemoryStep: a hardcoded predecessor key only serves one Skill.
    Reads context['filename'] and context[source_key] as the content."""
    name = "write_file"
    description = "Writes context[source_key] to a file named context['filename'] in the workspace."
    script = ScriptMeta(
        step_id="step.write_file",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, built for ResearchAndSaveFileSkill",),
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

        tool = registry.get("write_file")
        result = tool.execute(tool.InputModel(filename=filename, content=str(content)))
        return StepResult(success=result.success, output=result.output, error=result.error)
