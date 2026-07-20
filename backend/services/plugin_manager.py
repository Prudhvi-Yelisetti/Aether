from services.reasoning_service import generate, generate_strict, ReasoningError
from services.tools.registry import registry
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

    decision = generate(decision_prompt, model="mistral").strip().lower()

    if "code" in decision:
        return "code"
    if "file" in decision:
        return "file"
    if "web" in decision:
        return "web"

    return None


# -------- MAIN EXECUTION FUNCTION --------
# Dispatches through the ToolRegistry (see services/tools/registry.py). The
# natural-language -> structured-input translation for each tool happens
# here (it's a reasoning step), while the Tool itself only does deterministic
# execution — see the module docstring in services/tools/base.py.
#
# generate() vs generate_strict(): the FINAL summaries shown directly to a
# human use generate() — if generation fails there, showing the friendly
# "Could not reach Ollama..." string as the answer is the correct, honest
# response. But intermediate LLM calls whose output feeds into something
# else (code about to be executed, a query about to be searched) use
# generate_strict() — see the ReasoningError catches below. Getting this
# backwards was a real bug found and fixed in Phase D's SummarizeStep (see
# ROADMAP.md's E0 / STATUS.md for the story); this is that same fix applied
# here.
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

        code_prompt = f"""
You are a Python code generator.

Convert the user's request into correct Python code.

Rules:
- Output ONLY Python code
- No explanation
- Ensure code runs correctly

Request: {prompt}
"""
        try:
            code = generate_strict(code_prompt, model="llama3")
        except ReasoningError as e:
            # Fails cleanly with a real message instead of feeding the
            # failure string into the sandbox as if it were Python.
            return f"Could not generate code: {e}"

        result = tool.execute(tool.InputModel(code=code))
        return result.output

    # -------- FILE TOOL --------
    elif plugin_name == "file":
        # Extracting a filename out of a natural-language prompt is a
        # reasoning-adjacent parsing step — it lives here, not in FileTool
        # or read_file(), which now only handle an already-known filename.
        candidate = next((p for p in prompt.split() if "." in p), None)
        if not candidate:
            return "No file specified"

        result = tool.execute(tool.InputModel(filename=candidate))
        if not result.success:
            return result.output

        summary = generate(
            f"Summarize this file content clearly:\n{result.output}",
            model="mistral"
        )
        return summary

    # -------- WEB TOOL --------
    elif plugin_name == "web":
        query_prompt = f"""
Extract the main search query from this user request.
Return ONLY the search query.

Request: {prompt}
"""
        try:
            clean_query = generate_strict(query_prompt, model="mistral").strip()
        except ReasoningError:
            # Fall back to the raw prompt as the query rather than
            # searching for the failure string itself.
            clean_query = prompt

        result = tool.execute(tool.InputModel(query=clean_query))
        if not result.success:
            return result.output

        summary = generate(
            f"Explain this simply:\n{result.output}",
            model="mistral"
        )
        return summary

    return None
