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
    sidesteps that risk entirely rather than reimplementing it here."""
    entries = sorted(p.name for p in WORKSPACE_DIR.iterdir() if p.is_file())

    if not entries:
        return "(workspace is empty — no files yet)"

    return "\n".join(entries)
