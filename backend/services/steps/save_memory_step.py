from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta
from storage.project_store import save_memory


class SaveMemoryStep(Step):
    """Deterministic — wraps storage.project_store.save_memory directly.

    source_key and memory_key are both configurable — same reasoning as
    SummarizeStep's source_key: a hardcoded predecessor/memory-key pair
    only serves one Skill, which isn't real reuse. Reads context[source_key]
    and context['project_id']."""
    name = "save_memory"
    description = "Inserts context[source_key] as a new episodic memory row under memory_key, scoped to context['project_id']."
    script = ScriptMeta(
        step_id="step.save_memory",
        version="1.3.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, hardcoded source_key='summarize', "
            "memory_key='last_research', Phase D",
            "1.1.0: both made configurable so FileDigestSkill could reuse this "
            "Step with a different memory_key instead of duplicating it",
            "1.2.0: every SaveMemoryStep result is a specific past skill-run "
            "artifact, never a durable user fact -- always writes "
            "memory_type='episodic' now (a91c3d5e7f02's structural memory "
            "fix). Behavior change: save_memory() no longer overwrites the "
            "prior value for this key, it keeps a short bounded history "
            "(EPISODIC_KEEP most recent) instead.",
            "1.3.0: reads context['consolidate_memory'] (opt-in, defaults "
            "False -- see planning_service.py's _build_skill_input() for "
            "where it enters the context) and forwards it to save_memory(), "
            "which uses it to decide whether to run memory consolidation "
            "right before this key's oldest row would be pruned.",
        ),
    )

    def __init__(self, source_key: str = "summarize", memory_key: str = "last_research"):
        self.source_key = source_key
        self.memory_key = memory_key

    def run(self, context: dict) -> StepResult:
        project_id = context.get("project_id")
        value = context.get(self.source_key)
        consolidate_memory = context.get("consolidate_memory", False)

        if not project_id:
            return StepResult(success=False, error="context['project_id'] is required")
        if not value:
            return StepResult(success=False, error=f"context['{self.source_key}'] is required")

        try:
            save_memory(project_id, self.memory_key, value, memory_type="episodic", consolidate=consolidate_memory)
            return StepResult(success=True, output={"key": self.memory_key, "value": value})
        except Exception as e:
            return StepResult(success=False, error=str(e))
