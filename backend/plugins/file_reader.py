from pathlib import Path

# Only files inside this directory can be read by the file plugin. Change
# this if you want the workspace elsewhere, but never remove the check below —
# it is what stops the plugin from reading arbitrary paths like /etc/passwd
# or the app's own database.
WORKSPACE_DIR = Path.home() / "aether-workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

MAX_READ_BYTES = 4000


def _resolve_safe_path(candidate: str) -> Path | None:
    """Resolve `candidate` against WORKSPACE_DIR and reject anything that
    escapes it (via .., symlinks, or an absolute path elsewhere)."""
    try:
        base = WORKSPACE_DIR.resolve()
        target = (base / candidate).resolve()
        target.relative_to(base)  # raises ValueError if target escapes base
        return target
    except (ValueError, OSError):
        return None


def read_file(prompt: str):
    try:
        # Extract a candidate filename (basic heuristic, unchanged from before —
        # what changed is that the result is now validated, not trusted)
        parts = prompt.split()
        candidate = None

        for p in parts:
            if "." in p:
                candidate = p
                break

        if not candidate:
            return "No file specified"

        safe_path = _resolve_safe_path(candidate)

        if safe_path is None:
            return (
                f"Access denied: files can only be read from {WORKSPACE_DIR}. "
                f"'{candidate}' resolves outside that directory."
            )

        if not safe_path.exists():
            return f"File not found in workspace: {candidate}"

        if not safe_path.is_file():
            return f"Not a file: {candidate}"

        with open(safe_path, "r", errors="replace") as f:
            content = f.read(MAX_READ_BYTES)

        return f"File content:\n{content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"
