from services.steps.base import Step, StepResult
from storage.project_store import save_memory


class SaveMemoryStep(Step):
    """Deterministic — wraps storage.project_store.save_memory directly.

    source_key and memory_key are both configurable — same reasoning as
    SummarizeStep's source_key: a hardcoded predecessor/memory-key pair
    only serves one Skill, which isn't real reuse. Reads context[source_key]
    and context['project_id']."""
    name = "save_memory"
    description = "Upserts context[source_key] into memory under memory_key, scoped to context['project_id']."

    def __init__(self, source_key: str = "summarize", memory_key: str = "last_research"):
        self.source_key = source_key
        self.memory_key = memory_key

    def run(self, context: dict) -> StepResult:
        project_id = context.get("project_id")
        value = context.get(self.source_key)

        if not project_id:
            return StepResult(success=False, error="context['project_id'] is required")
        if not value:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        try:
            save_memory(project_id, self.memory_key, value)
            return StepResult(success=True, output={"key": self.memory_key, "value": value})
        except Exception as e:
            return StepResult(success=False, error=str(e))
