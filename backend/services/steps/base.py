"""
The Step contract (ARCHITECTURE.md's Step Service: "a reusable implementation
that can be shared across many skills"). Each Step contains, per the doc:
Execution contract, Script, Validation, Metrics.

- Execution contract: the abstract run(context) -> StepResult signature below.
- Script: `script` (a ScriptMeta instance — see script_meta.py) — versioned
  identity for the Step's implementation.
- Validation: `validate(result)` below — a Step's own check of whether its
  result is actually good, distinct from whether it merely didn't raise.
  Defaults to "success and non-empty output"; override for stricter checks.
- Metrics: NOT stored on the Step object itself (metrics are per-invocation
  facts, not part of a Step's identity) — Skill.run() records them to the
  step_metrics table via storage/step_metrics_store.py after every run().

A Step is one unit of work inside a Skill. Unlike a Tool, a Step is allowed
to call the Reasoning Service — the "tools never reason" rule (see
services/tools/base.py) applies specifically to Tools, which sit below Steps
in ARCHITECTURE.md's tool-first priority list.

Steps read from and write to a shared `context` dict as they run inside a
Skill. Each step:
  - declares what context key(s) it reads
  - writes its output to context[step.name]
so later steps in the same Skill can reference earlier ones.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from services.steps.script_meta import ScriptMeta


class StepResult(BaseModel):
    success: bool
    output: Any = None
    error: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    reason: str | None = None


class Step(ABC):
    name: str
    description: str
    script: ScriptMeta

    @abstractmethod
    def run(self, context: dict) -> StepResult:
        """Reads whatever it needs from `context` (populated by earlier
        steps in the same Skill run) and returns a StepResult. Does NOT
        write to context itself — Skill.run() does that, keyed by
        self.name, so the writing behavior is uniform and visible in one
        place (see services/skills/base.py)."""
        ...

    def validate(self, result: StepResult) -> ValidationResult:
        """Default validation: the run succeeded and produced non-empty
        output. This is intentionally stricter than just checking
        result.success — a Step can succeed (no exception, no error) and
        still produce a useless result (empty string, empty list). Override
        for checks specific to a Step's own output shape (see
        RunCodeStep.validate() for an example: "ran with no error" isn't
        the same as "actually produced output")."""
        if not result.success:
            return ValidationResult(valid=False, reason=result.error or "step reported failure")
        if result.output in (None, "", [], {}):
            return ValidationResult(valid=False, reason="empty output")
        return ValidationResult(valid=True)
