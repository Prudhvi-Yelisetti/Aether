import requests

WIKI_OPENSEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Wikipedia's API rejects unidentified clients with a 403 (see STATUS.md,
# 2026-07-23 — the first version of this fallback shipped without this
# header and every single call silently failed, caught by the bare
# except below; verifying live caught it, not just checking imports).
WIKI_HEADERS = {"User-Agent": "AetherAIOS/1.0 (local dev project; no public contact)"}


def _wikipedia_fallback(query: str) -> str | None:
    """Deterministic fallback when DuckDuckGo's Instant Answer API — exact
    topic-keyed, narrow, not general search — returns nothing (see
    STATUS.md, 2026-07-23). Wikipedia's OpenSearch does prefix/fuzzy
    matching, far more forgiving of imperfect phrasing than DDG's exact
    keying, so it can often find the right page even when the query isn't
    worded exactly like the title. Two calls: OpenSearch to find the
    best-matching title, then the REST summary endpoint for real
    paragraph content — OpenSearch's own descriptions are too short to be
    useful on their own (often one line). Returns None on any failure so
    the caller can fall through to its own "no results" message rather
    than surfacing a raw error for what's already a fallback path."""
    try:
        search_resp = requests.get(
            WIKI_OPENSEARCH_URL,
            params={
                "action": "opensearch",
                "search": query,
                "limit": 1,
                "namespace": 0,
                "format": "json",
            },
            headers=WIKI_HEADERS,
            timeout=10,
        ).json()

        titles = search_resp[1] if len(search_resp) > 1 else []
        if not titles:
            return None

        title = titles[0]
        summary_resp = requests.get(
            WIKI_SUMMARY_URL.format(title=title.replace(" ", "_")),
            headers=WIKI_HEADERS,
            timeout=10,
        ).json()

        extract = summary_resp.get("extract")
        if not extract:
            return None

        return f"{title}: {extract}"

    except Exception:
        return None


def web_search(query: str) -> str:
    """Deterministic web search — takes an already-extracted clean query.
    Extracting a query out of a natural-language prompt is a reasoning step
    and belongs to the caller (see services/tools/web_tool.py).

    Two data sources, tried in order: DuckDuckGo's Instant Answer API
    first (original behavior, unchanged), then a Wikipedia OpenSearch +
    summary fallback (added 2026-07-23) if DDG returns nothing. See
    _wikipedia_fallback()'s docstring for why DDG alone wasn't enough —
    its narrow exact-topic keying was rejecting queries a human would
    recognize as the same topic, independent of how well-extracted the
    query itself was."""
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

        if results:
            return "Results:\n" + "\n".join(results[:5])

        fallback = _wikipedia_fallback(query)
        if fallback:
            return "Results:\n" + fallback

        return "No useful results found. Try a more specific query."

    except Exception as e:
        return f"Search failed: {str(e)}"
