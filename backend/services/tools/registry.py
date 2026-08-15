"""
ToolRegistry: register tools, look them up by name, list what's available.

Adding a new tool means writing one Tool subclass and registering it
here — nothing in routing.py needs to change. describe_all() exists for
the Planning Service, which builds its decision prompt from this list
dynamically rather than a hardcoded one (services/planning_service.py).

Corrected 2026-08-14 (STATUS.md item 25): this docstring used to also
claim "nothing in plugin_manager.py needs to change" — false, and
contradicted by this project's own history. execute_plugin() still
needs its own dispatch branch per tool (see that function) to translate
a natural-language prompt into the tool's structured InputModel;
item 12 found and fixed exactly this gap for write_file/list_files,
which had been silently returning None with no useful error because
that translation step didn't exist yet for them.
"""

from services.tools.base import Tool
from services.tools.code_tool import CodeTool
from services.tools.file_tool import FileTool
from services.tools.web_tool import WebTool
from services.tools.write_file_tool import WriteFileTool
from services.tools.list_files_tool import ListFilesTool
from services.tools.append_file_tool import AppendFileTool


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


# Module-level singleton, registered once at import time. Add a new tool
# by instantiating it and calling .register() here, plus a dispatch
# branch in execute_plugin() (services/plugin_manager.py) — see this
# module's docstring above for why that second step is still needed.
registry = ToolRegistry()
registry.register(CodeTool())
registry.register(FileTool())
registry.register(WebTool())
registry.register(WriteFileTool())
registry.register(ListFilesTool())
registry.register(AppendFileTool())
