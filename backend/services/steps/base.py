"""
The Step contract (ARCHITECTURE.md's Step Service: "a reusable implementation
that can be shared across many skills").

A Step is one unit of work inside a Skill. Unlike a Tool, a Step is allowed
to call the Reasoning Service — the "tools never reason" rule (see
services/tools/base.py) applies specifically to Tools, which sit below Steps
in ARCHITECTURE.md's tool-first priority list. Steps sit above Tools and
below Skills/Workflows in that list precisely because gluing tool calls
together often does require some interpretation (e.g. summarizing a tool's
raw output). Prefer a Tool-only Step when no interpretation is needed
(SaveMemoryStep below is a good example); reach for a reasoning-based Step
only when the work genuinely needs it (SummarizeStep below).

Steps read from and write to a shared `context` dict as they run inside a
Skill — this is intentionally a plain dict, not a new persistence layer.
Each step:
  - declares what context key(s) it reads
  - writes its output to context[step.name]
so later steps in the same Skill can reference earlier ones.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class StepResult(BaseModel):
    success: bool
    output: Any = None
    error: str | None = None


class Step(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, context: dict) -> StepResult:
        """Reads whatever it needs from `context` (populated by earlier
        steps in the same Skill run) and returns a StepResult. Does NOT
        write to context itself — Skill.run() does that, keyed by
        self.name, so the writing behavior is uniform and visible in one
        place (see services/skills/base.py)."""
        ...
