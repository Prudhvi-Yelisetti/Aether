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
from services.object_meta import ObjectMeta


class CalculateAndExplainSkill(Skill):
    name = "calculate_and_explain"
    description = "Runs Python code and explains the result in plain language."
    steps = [
        RunCodeStep(),
        SummarizeStep(source_key="run_code"),
    ]
    meta = ObjectMeta(
        identifier="skill.calculate_and_explain",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation",
            "1.1.0: SummarizeStep bumped to 1.2.0 underneath this Skill "
            "unchanged -- context['question'] now grounds the explain "
            "prompt with the original request, fixing bare numeric "
            "output getting explained with no idea what it means "
            "(found live via llm_validate eval traffic, STATUS.md item "
            "13). Listed here since it changed this Skill's real "
            "behavior even though calculate_and_explain_skill.py itself "
            "didn't change.",
        ),
    )
