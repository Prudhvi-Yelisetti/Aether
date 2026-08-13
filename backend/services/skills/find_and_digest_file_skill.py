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

Retired 2026-08-13 (STATUS.md item 23): FileDigestSkill is gone. The
planner reliably preferred this Skill over FileDigestSkill for typical
"digest this file" phrasing — fuzzy matching wins on the LLM's own
description comparison, not just on robustness — but only
FileDigestSkill ever wrote to memory (had SaveMemoryStep;
this one didn't). That meant episodic memory for file digests was
effectively never being written through normal use, and
FileDigestSkill's exact-match-only behavior added no real capability
this Skill's fallback-to-raw-prompt fuzzy match doesn't already cover.
Rather than keep two skills with overlapping purpose where only the
less-preferred one did the useful side effect, added SaveMemoryStep
here (same memory_key="last_file_digest" FileDigestSkill used, so
existing episodic rows and any consolidated_last_file_digest semantic
fact keep working unchanged) and deleted FileDigestSkill outright —
confirmed zero other references anywhere in the codebase before
removing it, same verify-then-delete precedent as services/router.py
(STATUS.md item 1).
"""

from services.skills.base import Skill
from services.steps.list_files_step import ListFilesStep
from services.steps.find_file_step import FindFileStep
from services.steps.read_file_step import ReadFileStep
from services.steps.summarize_step import SummarizeStep
from services.steps.save_memory_step import SaveMemoryStep


class FindAndDigestFileSkill(Skill):
    name = "find_and_digest_file"
    description = "Finds a file in the workspace even from an imperfect or partial filename, reads it, summarizes it, and saves the summary to project memory."
    steps = [
        ListFilesStep(),
        FindFileStep(),
        ReadFileStep(),
        SummarizeStep(source_key="read_file"),
        SaveMemoryStep(source_key="summarize", memory_key="last_file_digest"),
    ]
