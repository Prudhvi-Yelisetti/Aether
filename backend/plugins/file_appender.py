"""
Real gap file_writer.py's own docstring named explicitly: "Overwrites an
existing file... no append mode... If accidental overwrites become a
real problem in practice, that's a considered addition later, not
assumed here." Built 2026-08-14 (STATUS.md item 25) -- the same
WORKSPACE_DIR allowlisting via resolve_safe_path(), same MAX_WRITE_BYTES
ceiling, applied to the file's TOTAL size after appending (not just the
new content) so this can't be used to grow a file past the same limit
write_file enforces one append at a time.

Symmetric counterpart to write_file: that Tool lets Aether create/
overwrite a file; this one lets it maintain a running file (a log, a
journal, notes accumulated across multiple messages) without reading
the whole thing back first just to re-write it with one line added.
"""

from plugins.file_reader import WORKSPACE_DIR, resolve_safe_path

MAX_FILE_BYTES = 20000


def append_file(filename: str, content: str) -> str:
    """Takes an already-decided filename and content — same division of
    responsibility as write_file(): deciding what to append is a
    reasoning-adjacent concern for the caller (see
    services/tools/append_file_tool.py), not this function."""
    safe_path = resolve_safe_path(filename)

    if safe_path is None:
        return (
            f"Access denied: files can only be appended to inside {WORKSPACE_DIR}. "
            f"'{filename}' resolves outside that directory."
        )

    existing_size = safe_path.stat().st_size if safe_path.exists() else 0
    new_content_size = len(content.encode("utf-8", errors="replace"))
    if existing_size + new_content_size > MAX_FILE_BYTES:
        return (
            f"Append would grow {filename} to {existing_size + new_content_size} bytes, "
            f"exceeding the {MAX_FILE_BYTES}-byte limit ({existing_size} already there)."
        )

    safe_path.parent.mkdir(parents=True, exist_ok=True)
    # "a" mode: creates the file if it doesn't exist yet (same as open("w")
    # would for write_file), appends if it does -- no separate
    # exists()-then-branch needed for that part, only for the size check
    # above.
    with open(safe_path, "a", errors="replace") as f:
        f.write(content)

    return f"Appended {new_content_size} bytes to {filename} (now {existing_size + new_content_size} bytes total)."
