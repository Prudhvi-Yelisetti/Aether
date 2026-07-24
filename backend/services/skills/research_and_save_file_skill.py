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


class ResearchAndSaveFileSkill(Skill):
    name = "research_and_save_file"
    description = "Searches the web for a topic, summarizes it, and saves the summary to a file in the workspace (as opposed to project memory — see research_topic)."
    steps = [
        WebSearchStep(),
        SummarizeStep(source_key="web_search"),
        WriteFileStep(source_key="summarize"),
    ]
