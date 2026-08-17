"""
Deterministic directory listing, scoped to the same WORKSPACE_DIR
file_reader.py/file_writer.py already establish. Closes a real gap
observed repeatedly this session: read_file and write_file both require
already knowing an exact filename, and "File not found" has consistently
been the most common permanent (non-retryable) Tool/Skill failure — see
STATUS.md's validation taxonomy. Nothing before this could tell the
caller what files actually exist.
"""

from plugins.file_reader import WORKSPACE_DIR


def list_files() -> str:
    """No arguments — lists everything in the sandboxed workspace, not a
    caller-chosen path. Listing an arbitrary directory would need its own
    escape-check like resolve_safe_path(); scoping to WORKSPACE_DIR only
    sidesteps that risk entirely rather than reimplementing it here.

    Returns an empty string when the workspace has no files — NOT a
    human-friendly placeholder sentence. This function's output is
    structured data consumed by two different callers with different
    needs: FindFileStep (services/steps/find_file_step.py) treats it as
    a raw filename list to fuzzy-match against, and a placeholder
    sentence like "(workspace is empty...)" would get treated as a fake
    filename candidate there — a real gap flagged during item 26's
    Skill/Step composition audit (STATUS.md) and fixed here. Any
    human-facing framing for "the workspace is empty" belongs at the
    boundary that actually displays this to a person
    (services/plugin_manager.py's execute_plugin() "list_files" branch),
    not baked into the data itself."""
    entries = sorted(p.name for p in WORKSPACE_DIR.iterdir() if p.is_file())
    return "\n".join(entries)
