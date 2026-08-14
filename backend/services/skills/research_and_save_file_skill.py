"""
This session's Tool/Skill expansion. Composes two EXISTING Steps
(WebSearchStep, SummarizeStep — both already built for ResearchTopicSkill)
with one new one (WriteFileStep) — the actual point of the Skill/Step
split per ARCHITECTURE.md: "compose existing steps into higher-level
abilities" rather than duplicating implementations. Distinct from
ResearchTopicSkill in exactly one place: where the result ends up (a
file in the workspace, not project memory) — everything upstream of that
is identical and reused, not copied.
"""

from services.skills.base import Skill
from services.steps.web_search_step import WebSearchStep
from services.steps.summarize_step import SummarizeStep
from services.steps.write_file_step import WriteFileStep
from services.object_meta import ObjectMeta


class ResearchAndSaveFileSkill(Skill):
    name = "research_and_save_file"
    description = "Searches the web for a topic, summarizes it, and saves the summary to a file in the workspace (as opposed to project memory — see research_topic)."
    steps = [
        WebSearchStep(),
        SummarizeStep(source_key="web_search"),
        WriteFileStep(source_key="summarize"),
    ]
    meta = ObjectMeta(
        identifier="skill.research_and_save_file",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation",
            "1.1.0: planning_service.py's _build_skill_input() for this "
            "Skill always called slugify_filename(query), ignoring any "
            "filename the user actually typed -- \"...save a summary to "
            "eiffel_summary.txt\" silently saved as eiffel_tower.txt "
            "instead (found live via llm_validate eval traffic, "
            "STATUS.md). Fixed upstream in planning_service.py, listed "
            "here since it changed this Skill's real save-location "
            "behavior even though this file itself didn't change.",
        ),
    )
