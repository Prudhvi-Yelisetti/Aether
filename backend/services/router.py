def route_model(prompt: str) -> str:
    prompt_lower = prompt.lower()

    # coding → strong model
    if any(word in prompt_lower for word in ["code", "program", "c++", "python", "java"]):
        return "llama3"

    # complex explanation → strong model
    elif any(word in prompt_lower for word in ["explain", "detail", "theory", "how", "why"]):
        return "llama3"

    # long input → strong model
    elif len(prompt) > 300:
        return "llama3"

    # simple chat → fast model
    elif len(prompt) < 50:
        return "mistral"

    # default
    return "mistral"