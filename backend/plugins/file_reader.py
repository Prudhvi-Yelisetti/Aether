from pathlib import Path

# Only files inside this directory can be read. Change this if you want the
# workspace elsewhere, but never remove the check in resolve_safe_path() below —
# it is what stops arbitrary paths like /etc/passwd or the app's own database
# from being read.
WORKSPACE_DIR = Path.home() / "aether-workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

MAX_READ_BYTES = 4000


def resolve_safe_path(candidate: str) -> Path | None:
    """Resolve `candidate` against WORKSPACE_DIR and reject anything that
    escapes it (via .., symlinks, or an absolute path elsewhere)."""
    try:
        base = WORKSPACE_DIR.resolve()
        target = (base / candidate).resolve()
        target.relative_to(base)  # raises ValueError if target escapes base
        return target
    except (ValueError, OSError):
        return None


def read_file(filename: str) -> str:
    """Deterministic file read, scoped to WORKSPACE_DIR. Takes an already
    -extracted filename — parsing a filename out of a natural-language
    prompt is a reasoning-adjacent concern and belongs to the caller
    (see services/tools/file_tool.py), not to this function."""
    safe_path = resolve_safe_path(filename)

    if safe_path is None:
        return (
            f"Access denied: files can only be read from {WORKSPACE_DIR}. "
            f"'{filename}' resolves outside that directory."
        )

    if not safe_path.exists():
        return f"File not found in workspace: {filename}"

    if not safe_path.is_file():
        return f"Not a file: {filename}"

    with open(safe_path, "r", errors="replace") as f:
        return f.read(MAX_READ_BYTES)
