"""
This session's second Tool/Skill addition. Composes THREE existing Steps
(ListFilesStep, ReadFileStep — reused unchanged, SummarizeStep — reused
with source_key reconfigured) with one new one (FindFileStep) — same
"compose, don't duplicate" pattern ResearchAndSaveFileSkill used.

Genuinely more robust than FileDigestSkill for the common real case: the
user doesn't know or state the exact filename. FileDigestSkill's
extract_filename() -> ReadFileStep chain fails outright on any mismatch
("File not found" — the single most common permanent Tool/Skill failure
this session, see STATUS.md). This Skill lists the workspace first, then
fuzzy-matches the extracted candidate against what's actually there,
surviving typos, missing extensions, and partial names.
"""

from services.skills.base import Skill
from services.steps.list_files_step import ListFilesStep
from services.steps.find_file_step import FindFileStep
from services.steps.read_file_step import ReadFileStep
from services.steps.summarize_step import SummarizeStep


class FindAndDigestFileSkill(Skill):
    name = "find_and_digest_file"
    description = "Finds a file in the workspace even from an imperfect or partial filename, reads it, and summarizes it."
    steps = [
        ListFilesStep(),
        FindFileStep(),
        ReadFileStep(),
        SummarizeStep(source_key="read_file"),
    ]
