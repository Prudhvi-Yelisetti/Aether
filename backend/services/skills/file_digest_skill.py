"""
Proves Step reuse: this Skill uses the exact same SummarizeStep and
SaveMemoryStep classes as ResearchTopicSkill (services/skills/
research_topic_skill.py) — only the predecessor changes (a file read
instead of a web search) and the context keys passed to them differ. No
new "explain a file" or "save a file digest" implementation was written.

filename -> read file (Tool, deterministic) -> summarize (reasoning) ->
save to memory (Tool, deterministic).
"""

from services.skills.base import Skill
from services.steps.read_file_step import ReadFileStep
from services.steps.summarize_step import SummarizeStep
from services.steps.save_memory_step import SaveMemoryStep


class FileDigestSkill(Skill):
    name = "file_digest"
    description = "Reads a file, summarizes it, and saves the summary to project memory."
    steps = [
        ReadFileStep(),
        SummarizeStep(source_key="read_file"),
        SaveMemoryStep(source_key="summarize", memory_key="last_file_digest"),
    ]
