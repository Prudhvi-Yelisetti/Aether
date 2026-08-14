from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from services.tools.registry import registry


class ListFilesStep(Step):
    """Deterministic — wraps ListFilesTool directly. No input needed;
    always lists the whole workspace. Skill.run() writes this Step's
    output to context['list_files'] automatically (context[step.name] —
    see services/skills/base.py), same as every other Step; there's no
    "write to a custom key" mechanism in this codebase, only the
    "read from a custom key" (source_key) pattern SummarizeStep/
    WriteFileStep use."""
    name = "list_files"
    description = "Lists every file in the workspace."
    script = ScriptMeta(
        identifier="step.list_files",
        version="1.0.0",
        owner="prudhvi",
        history=("1.0.0: initial implementation, built for FindAndDigestFileSkill",),
        # Lighter than read_file's "filesystem:read" -- this only sees
        # filenames (plugins/file_lister.py), never file contents.
        permissions=("filesystem:list",),
    )

    def run(self, context: dict) -> StepResult:
        tool = registry.get("list_files")
        result = tool.execute(tool.InputModel())
        return StepResult(success=result.success, output=result.output, error=result.error)
