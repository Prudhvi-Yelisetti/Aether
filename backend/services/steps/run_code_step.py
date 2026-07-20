from services.steps.base import Step, StepResult
from services.tools.registry import registry


class RunCodeStep(Step):
    """Deterministic — wraps CodeTool directly. Reads context['code']."""
    name = "run_code"
    description = "Executes Python code (sandboxed) using the code Tool."

    def run(self, context: dict) -> StepResult:
        code = context.get("code")
        if not code:
            return StepResult(success=False, error="context['code'] is required")

        tool = registry.get("code")
        result = tool.execute(tool.InputModel(code=code))
        return StepResult(success=result.success, output=result.output, error=result.error)
