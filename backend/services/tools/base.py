"""
The Tool contract (see ROADMAP.md Phase C, ARCHITECTURE.md's Tool Service).

Design principle carried over from ARCHITECTURE.md: "Tools never perform
reasoning." A Tool's execute() takes already-structured input (a filename,
a search query, a code string) and does deterministic work only. Turning a
natural-language prompt into that structured input is a reasoning step and
belongs to the caller (currently plugin_manager.py; later, a Planning
Service) — not to the tool itself.

Each concrete tool defines:
  - name / description: for a registry and, later, a planner to select from
  - InputModel: a pydantic model describing what execute() expects
  - execute(input): does the deterministic work, returns a ToolResult

Using pydantic here isn't ceremony — input_schema() below returns real JSON
Schema via InputModel.model_json_schema(), which is what a future Planning
Service needs to validate/construct tool calls without knowing each tool's
Python internals.
"""

from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    output: str
    error: str | None = None


class Tool(ABC):
    name: str
    description: str
    InputModel: Type[BaseModel]

    @abstractmethod
    def execute(self, input: BaseModel) -> ToolResult:
        ...

    def input_schema(self) -> dict:
        return self.InputModel.model_json_schema()

    def describe(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }
