"""
Runs LLM-generated Python inside a bubblewrap (bwrap) sandbox.

This replaces the old keyword-blocklist approach (`FORBIDDEN = ["import os", ...]`),
which was bypassable via importlib, __import__, attribute access, etc. A
blocklist on source text can never be complete; the actual security boundary
here is OS-level isolation via bwrap:

  - --unshare-all        : new network/pid/ipc/uts namespaces (no network access,
                            can't see or signal host processes)
  - --ro-bind / /        : host filesystem is mounted read-only
  - --tmpfs /tmp          : a fresh, empty, writable tmp — nothing from the host
                            filesystem is writable, and nothing written persists
  - --die-with-parent    : sandboxed process is killed if this process dies
  - --new-session        : detached from the controlling terminal
  - resource limits (CPU time, address space, file size, process count) via
    `prlimit`/preexec, and a wall-clock timeout as a final backstop

This is a meaningful improvement over the previous implementation but is still
namespace-based isolation, not a full VM (Firecracker/gVisor). Treat it as
"safe enough for a local single-user dev tool", not as a boundary for running
fully untrusted code from strangers on a multi-tenant server.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 5
MAX_CPU_SECONDS = 5
MAX_MEMORY_KB = 256 * 1024  # 256 MB, in KB for `ulimit -v`
MAX_OUTPUT_BYTES = 20_000

BWRAP_PATH = shutil.which("bwrap")

# Resource limits must be applied to the SANDBOXED process, not to bwrap
# itself — applying them via subprocess's preexec_fn would constrain bwrap's
# own namespace-setup step (which needs more headroom) and makes it fail
# with an unrelated "Resource temporarily unavailable" error. Instead we set
# them with `ulimit` inside a shell that then execs python3, all within the
# sandbox.
_LIMITED_SHELL_CMD = (
    f"ulimit -t {MAX_CPU_SECONDS}; "
    f"ulimit -v {MAX_MEMORY_KB}; "
    f"ulimit -f 10240; "
    f"ulimit -u 32; "
    f"exec python3 /tmp/script.py"
)


def run_code(code: str):
    if not BWRAP_PATH:
        return (
            "Execution blocked: bubblewrap (bwrap) is not installed, and running "
            "LLM-generated code without a real sandbox is not safe. Install bwrap "
            "(e.g. `sudo pacman -S bubblewrap`) to enable this feature."
        )

    try:
        with tempfile.TemporaryDirectory(prefix="aether-code-") as workdir:
            script_path = Path(workdir) / "script.py"
            script_path.write_text(code)

            cmd = [
                BWRAP_PATH,
                "--unshare-all",
                "--die-with-parent",
                "--new-session",
                "--ro-bind", "/usr", "/usr",
                "--ro-bind", "/lib", "/lib",
                "--ro-bind-try", "/lib64", "/lib64",
                "--ro-bind-try", "/bin", "/bin",
                "--ro-bind-try", "/sbin", "/sbin",
                "--proc", "/proc",
                "--dev", "/dev",
                "--tmpfs", "/tmp",
                "--ro-bind", str(script_path), "/tmp/script.py",
                "--chdir", "/tmp",
                "sh", "-c", _LIMITED_SHELL_CMD,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )

            stdout = (result.stdout or "")[:MAX_OUTPUT_BYTES]
            stderr = (result.stderr or "")[:MAX_OUTPUT_BYTES]

            if result.returncode == 0:
                return f"Output:\n{stdout}" if stdout else "Output: (no output)"
            return f"Error (exit {result.returncode}):\n{stderr or stdout}"

    except subprocess.TimeoutExpired:
        return f"Execution timed out after {TIMEOUT_SECONDS}s"
    except Exception as e:
        return f"Execution failed: {str(e)}"
