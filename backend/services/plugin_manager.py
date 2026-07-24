from services.reasoning_service import generate, generate_strict, ReasoningError
from services.extraction import extract_filename, extract_search_query, generate_code
from services.tools.registry import registry
from services.routing import FAST_MODEL
import ast
import operator
import re


# -------- SIMPLE MATH DETECTION --------
def is_simple_math(prompt: str):
    return re.fullmatch(r"[0-9+\-*/(). ]+", prompt.strip()) is not None


# -------- SAFE MATH EVALUATION (no eval()) --------
# Only literals and +, -, *, /, parentheses are supported. Anything else
# (names, calls, attribute access, imports) raises and is rejected below,
# unlike eval() which executes arbitrary Python.
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval_math(expr: str):
    """Evaluate a simple arithmetic expression without eval()."""

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed)


# -------- FALLBACK RULE-BASED DETECTION --------
def decide_plugin(prompt: str):
    prompt_lower = prompt.lower()

    if any(keyword in prompt_lower for keyword in [
        "run python",
        "execute python",
        "run code",
        "execute code"
    ]):
        return "code"

    if any(word in prompt_lower for word in [
        "calculate", "compute", "factorial", "+", "-", "*", "/"
    ]):
        return "code"

    if any(word in prompt_lower for word in [
        "read", ".txt", ".py", ".md"
    ]):
        return "file"

    if "search" in prompt_lower:
        return "web"

    return None


# -------- AI DECISION LAYER --------
def ai_decide_plugin(prompt: str):
    decision_prompt = f"""
You are an AI decision system.

Decide whether this user request needs a tool.

Available tools:
- code → calculations, code execution
- file → reading files
- web → internet search

Rules:
- Return ONLY one word:
    code
    file
    web
    none

Request: {prompt}
"""

    decision = generate(decision_prompt, model=FAST_MODEL).strip().lower()

    if "code" in decision:
        return "code"
    if "file" in decision:
        return "file"
    if "web" in decision:
        return "web"

    return None


# -------- MAIN EXECUTION FUNCTION --------
# Dispatches through the ToolRegistry (see services/tools/registry.py). The
# natural-language -> structured-input translation for each tool uses the
# shared helpers in services/extraction.py (also used by the Planner, so
# a Tool call and a Skill call extract queries/code/filenames identically
# rather than duplicating the same prompts) — while the Tool itself only
# does deterministic execution — see the module docstring in
# services/tools/base.py.
def execute_plugin(plugin_name: str, prompt: str) -> str:

    tool = registry.get(plugin_name)
    if tool is None:
        return None

    # -------- CODE TOOL --------
    if plugin_name == "code":
        # Fast path: simple math (safe_eval_math never executes arbitrary
        # code, unlike eval() — it only walks a restricted arithmetic AST)
        if is_simple_math(prompt):
            try:
                result = safe_eval_math(prompt)
                return f"Output:\n{result}"
            except Exception:
                pass

        try:
            code = generate_code(prompt)
        except ReasoningError as e:
            # Fails cleanly with a real message instead of feeding the
            # failure string into the sandbox as if it were Python.
            return f"Could not generate code: {e}"

        result = tool.execute(tool.InputModel(code=code))
        return result.output

    # -------- FILE TOOL --------
    elif plugin_name == "file":
        candidate = extract_filename(prompt)
        if not candidate:
            return "No file specified"

        result = tool.execute(tool.InputModel(filename=candidate))
        if not result.success:
            return result.output

        summary = generate(
            f"Summarize this file content clearly:\n{result.output}",
            model=FAST_MODEL
        )
        return summary

    # -------- WEB TOOL --------
    elif plugin_name == "web":
        clean_query = extract_search_query(prompt)

        result = tool.execute(tool.InputModel(query=clean_query))
        if not result.success:
            return result.output

        summary = generate(
            f"Explain this simply:\n{result.output}",
            model=FAST_MODEL
        )
        return summary

    return None
