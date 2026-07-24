"""
ToolRegistry: register tools, look them up by name, list what's available.

The point is that adding a new tool means writing one Tool subclass and
registering it here — nothing in routing.py or plugin_manager.py needs to
change to add a fourth tool. describe_all() exists for a future Planning
Service that needs to know what tools exist and their input schemas without
importing each tool's Python module directly.
"""

from services.tools.base import Tool
from services.tools.code_tool import CodeTool
from services.tools.file_tool import FileTool
from services.tools.web_tool import WebTool
from services.tools.write_file_tool import WriteFileTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def describe_all(self) -> list[dict]:
        return [tool.describe() for tool in self._tools.values()]


# Module-level singleton, registered once at import time. Add a new tool by
# instantiating it and calling .register() here — nothing else changes.
registry = ToolRegistry()
registry.register(CodeTool())
registry.register(FileTool())
registry.register(WebTool())
registry.register(WriteFileTool())
