import requests


def web_search(query: str) -> str:
    """Deterministic web search — takes an already-extracted clean query.
    Extracting a query out of a natural-language prompt is a reasoning step
    and belongs to the caller (see services/tools/web_tool.py)."""
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json"
        response = requests.get(url, timeout=10).json()

        results = []

        if response.get("AbstractText"):
            results.append(response["AbstractText"])

        for item in response.get("RelatedTopics", []):
            if isinstance(item, dict):
                if "Text" in item:
                    results.append(item["Text"])
                if "Topics" in item:
                    for sub in item["Topics"]:
                        if "Text" in sub:
                            results.append(sub["Text"])

        if not results:
            return "No useful results found. Try a more specific query."

        return "Results:\n" + "\n".join(results[:5])

    except Exception as e:
        return f"Search failed: {str(e)}"
