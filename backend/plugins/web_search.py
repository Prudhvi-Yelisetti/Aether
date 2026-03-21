import requests


def web_search(prompt: str):
    try:
        query = prompt.replace("search", "").strip()

        url = f"https://api.duckduckgo.com/?q={query}&format=json"

        response = requests.get(url).json()

        results = []

        # -------- Abstract --------
        if response.get("AbstractText"):
            results.append(response["AbstractText"])

        # -------- Related Topics --------
        for item in response.get("RelatedTopics", []):
            if isinstance(item, dict):
                if "Text" in item:
                    results.append(item["Text"])

                # Nested topics
                if "Topics" in item:
                    for sub in item["Topics"]:
                        if "Text" in sub:
                            results.append(sub["Text"])

        # -------- Fallback --------
        if not results:
            return "No useful results found. Try a more specific query."

        return "Results:\n" + "\n".join(results[:5])

    except Exception as e:
        return f"Search failed: {str(e)}"