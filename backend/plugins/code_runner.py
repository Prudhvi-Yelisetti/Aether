import subprocess
import tempfile

# ❌ Dangerous keywords
FORBIDDEN = ["import os", "import sys", "subprocess", "open(", "exec(", "eval("]


def is_safe(code: str):
    for keyword in FORBIDDEN:
        if keyword in code:
            return False
    return True


def run_code(code: str):
    try:
        # -------- Safety Check --------
        if not is_safe(code):
            return "Execution blocked: unsafe code detected"

        # -------- Run Code --------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as f:
            f.write(code.encode())
            file_path = f.name

        result = subprocess.run(
            ["python3", file_path],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.stdout:
            return f"Output:\n{result.stdout}"
        else:
            return f"Error:\n{result.stderr}"

    except Exception as e:
        return f"Execution failed: {str(e)}"