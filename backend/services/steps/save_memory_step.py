from services.steps.base import Step, StepResult
from storage.project_store import save_memory


class SaveMemoryStep(Step):
    """Deterministic — wraps storage.project_store.save_memory directly.
    Reads context['project_id'] and context['summarize'] (the latter by
    convention: Skill.run() writes each step's output to context[step.name],
    and this step runs after a step named "summarize" — see
    skills/research_topic_skill.py)."""
    name = "save_memory"
    description = "Upserts context['summarize'] into memory under a fixed key, scoped to context['project_id']."

    MEMORY_KEY = "last_research"

    def run(self, context: dict) -> StepResult:
        project_id = context.get("project_id")
        summary = context.get("summarize")

        if not project_id:
            return StepResult(success=False, error="context['project_id'] is required")
        if not summary:
            return StepResult(success=False, error="context['summarize'] is required")

        try:
            save_memory(project_id, self.MEMORY_KEY, summary)
            return StepResult(success=True, output={"key": self.MEMORY_KEY, "value": summary})
        except Exception as e:
            return StepResult(success=False, error=str(e))
