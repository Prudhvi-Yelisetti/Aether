"""
Deliberately a different shape from the other two Skills — 2 steps, not 3,
and doesn't touch memory at all. Also reuses SummarizeStep (its
"explain this simply" framing works just as well on code output as on
search results or file contents — no new prompt needed).

code -> run it (Tool, deterministic) -> explain the result (reasoning).
"""

from services.skills.base import Skill
from services.steps.run_code_step import RunCodeStep
from services.steps.summarize_step import SummarizeStep


class CalculateAndExplainSkill(Skill):
    name = "calculate_and_explain"
    description = "Runs Python code and explains the result in plain language."
    steps = [
        RunCodeStep(),
        SummarizeStep(source_key="run_code"),
    ]
