import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_response(prompt: str, model: str = "llama3", history=None, memory=None):
    full_prompt = ""

    # -------- SYSTEM INSTRUCTIONS --------
    full_prompt += (
        "You are Aether, a highly intelligent AI assistant.\n"
        "Follow these rules strictly:\n"
        "1. Remember important user information.\n"
        "2. Be consistent with previous conversations.\n"
        "3. Use stored user data when relevant.\n\n"
    )

    # -------- MEMORY (Structured) --------
    if memory:
        full_prompt += "User profile:\n"

        grouped = {}
        for key, value in memory:
            grouped.setdefault(key, []).append(value)

        for key, values in grouped.items():
            full_prompt += f"{key}: {', '.join(values)}\n"

        full_prompt += "\n"

    # -------- CHAT HISTORY --------
    if history:
        full_prompt += "Recent conversation:\n"
        for p, r in history:
            full_prompt += f"User: {p}\nAI: {r}\n"
        full_prompt += "\n"

    # -------- CURRENT PROMPT --------
    full_prompt += f"User: {prompt}\nAI:"

    # -------- CALL OLLAMA --------
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False
            }
        )

        data = response.json()

        if "response" not in data:
            return f"Error from {model}: {data}"

        return data["response"]

    except Exception as e:
        return f"Request failed: {str(e)}"