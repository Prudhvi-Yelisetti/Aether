import requests

from services.logging_config import get_logger

logger = get_logger("aether.ollama")

OLLAMA_URL = "http://localhost:11434/api/generate"
REQUEST_TIMEOUT_SECONDS = 60


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
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        data = response.json()

        if "response" not in data:
            logger.warning("ollama_response_missing_field", model=model, data=data)
            return f"Error from {model}: {data}"

        return data["response"]

    except requests.exceptions.ConnectionError:
        logger.error("ollama_unreachable", model=model, url=OLLAMA_URL)
        return (
            f"Could not reach Ollama at {OLLAMA_URL}. "
            "Is `ollama serve` running?"
        )
    except requests.exceptions.Timeout:
        logger.error("ollama_timeout", model=model, timeout=REQUEST_TIMEOUT_SECONDS)
        return f"Request to {model} timed out after {REQUEST_TIMEOUT_SECONDS}s"
    except Exception as e:
        logger.error("ollama_request_failed", model=model, exc_info=True)
        return f"Request failed: {str(e)}"
