from plugins.code_runner import run_code
from plugins.file_reader import read_file
from plugins.web_search import web_search
from services.ollama_service import generate_response
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
        return "python"

    if any(word in prompt_lower for word in [
        "calculate", "compute", "factorial", "+", "-", "*", "/"
    ]):
        return "python"

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
- python → calculations, code execution
- file → reading files
- web → internet search

Rules:
- Return ONLY one word:
    python
    file
    web
    none

Request: {prompt}
"""

    decision = generate_response(decision_prompt, model="mistral").strip().lower()

    if "python" in decision:
        return "python"
    if "file" in decision:
        return "file"
    if "web" in decision:
        return "web"

    return None


# -------- MAIN EXECUTION FUNCTION --------
def execute_plugin(plugin_name: str, prompt: str):

    # -------- PYTHON TOOL --------
    if plugin_name == "python":

        # Fast path: simple math (safe_eval_math never executes arbitrary code,
        # unlike eval() — it only walks a restricted arithmetic AST)
        if is_simple_math(prompt):
            try:
                result = safe_eval_math(prompt)
                return f"Output:\n{result}"
            except Exception:
                pass

        # AI-generated code
        code_prompt = f"""
You are a Python code generator.

Convert the user's request into correct Python code.

Rules:
- Output ONLY Python code
- No explanation
- Ensure code runs correctly

Request: {prompt}
"""
        code = generate_response(code_prompt, model="llama3")
        return run_code(code)

    # -------- FILE TOOL --------
    elif plugin_name == "file":
        content = read_file(prompt)

        summary = generate_response(
            f"Summarize this file content clearly:\n{content}",
            model="mistral"
        )

        return summary

    # -------- WEB TOOL --------
    elif plugin_name == "web":

        # Step 1: Extract clean query
        query_prompt = f"""
Extract the main search query from this user request.
Return ONLY the search query.

Request: {prompt}
"""
        clean_query = generate_response(query_prompt, model="mistral").strip()

        # Step 2: Search
        results = web_search(clean_query)

        # Step 3: Summarize
        summary = generate_response(
            f"Explain this simply:\n{results}",
            model="mistral"
        )

        return summary

    return None