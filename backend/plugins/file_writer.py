"""
Deterministic file write, scoped to the same WORKSPACE_DIR file_reader.py
already established and guarded by (Phase A's allowlisting). Reuses
resolve_safe_path() from file_reader.py rather than a second copy of the
same escape-check logic — one place to get that security-critical check
right, not two.

Overwrites an existing file at the given name (no append mode, no
versioning) — deliberately the simplest possible first version. If
accidental overwrites become a real problem in practice, that's a
considered addition later, not assumed here.
"""

from plugins.file_reader import WORKSPACE_DIR, resolve_safe_path

MAX_WRITE_BYTES = 20000


def write_file(filename: str, content: str) -> str:
    """Takes an already-decided filename and content — deciding what to
    name a file or what to write is a reasoning-adjacent concern for the
    caller (see services/tools/write_file_tool.py), not this function."""
    safe_path = resolve_safe_path(filename)

    if safe_path is None:
        return (
            f"Access denied: files can only be written inside {WORKSPACE_DIR}. "
            f"'{filename}' resolves outside that directory."
        )

    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) > MAX_WRITE_BYTES:
        return f"Content too large: {len(encoded)} bytes exceeds the {MAX_WRITE_BYTES}-byte limit."

    safe_path.parent.mkdir(parents=True, exist_ok=True)
    with open(safe_path, "w", errors="replace") as f:
        f.write(content)

    return f"Saved to {filename} ({len(encoded)} bytes)."
