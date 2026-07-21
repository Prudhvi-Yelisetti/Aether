from services.steps.base import Step, StepResult, ValidationResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class RunCodeStep(Step):
    """Deterministic — wraps CodeTool directly. Reads context['code']."""
    name = "run_code"
    description = "Executes Python code (sandboxed) using the code Tool."
    script = ScriptMeta(
        step_id="step.run_code",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, built for CalculateAndExplainSkill",),
    )

    def run(self, context: dict) -> StepResult:
        code = context.get("code")
        if not code:
            return StepResult(success=False, error="context['code'] is required")

        tool = registry.get("code")
        result = tool.execute(tool.InputModel(code=code))
        return StepResult(success=result.success, output=result.output, error=result.error)

    def validate(self, result: StepResult) -> ValidationResult:
        base = super().validate(result)
        if not base.valid:
            return base
        # "ran without error" isn't the same as "actually produced output" —
        # a common LLM-codegen failure mode is code that executes cleanly
        # but forgets to print anything.
        if isinstance(result.output, str) and "(no output)" in result.output:
            return ValidationResult(valid=False, reason="code ran but produced no output")
        return ValidationResult(valid=True)
