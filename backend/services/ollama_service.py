import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_response(prompt: str, model: str = "llama3", history=None):
    full_prompt = ""

    # -------- Add System Instruction --------
    full_prompt += "You are a helpful AI assistant. Remember important user details when relevant.\n\n"

    # -------- Add Chat History --------
    if history:
        for p, r in history:
            full_prompt += f"User: {p}\nAI: {r}\n"

    # -------- Add Current Prompt --------
    full_prompt += f"User: {prompt}\nAI:"

    # -------- Call Ollama --------
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

        # -------- Debug (optional but useful) --------
        print(f"[DEBUG] Model: {model}")
        # print(f"[DEBUG] Prompt Sent:\n{full_prompt}\n")
        # print(f"[DEBUG] Raw Response:\n{data}\n")

        # -------- Safe Handling --------
        if "response" not in data:
            return f"Error from {model}: {data}"

        return data["response"]

    except Exception as e:
        return f"Request failed: {str(e)}"