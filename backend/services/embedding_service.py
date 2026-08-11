"""
Embedding generation for episodic-memory retrieval. Added 2026-08-10
alongside the semantic-similarity upgrade to get_relevant_episodic_memory()
(see storage/project_store.py) -- replaces the keyword-overlap heuristic
that item 20's memory-architecture rebuild shipped with, which was
explicitly documented there as a real, known limit (a prompt meaning the
same thing in different words wouldn't match). This closes that gap:
Letta/MemGPT, Mem0, and Zep -- the current reference points for agent
memory architecture -- all retrieve via dense embedding similarity, not
keyword matching (checked live via search before building this, not
assumed from training data).

Uses nomic-embed-text (274MB, pulled locally via `ollama pull
nomic-embed-text`) rather than reusing qwen3.5:9b for embeddings: it's a
dedicated embedding model, an order of magnitude smaller than the 9B
generator this machine already runs close to its limits (STATUS.md item
18 -- 4GB VRAM, most inference CPU-offloaded), and embedding models are
purpose-built to produce a fixed-size vector, unlike asking a generation
model to do the same job.
"""

import requests

EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"

EMBED_TIMEOUT_SECONDS = 15


def get_embedding(text: str, task: str = "search_document") -> list[float] | None:
    """Returns a 768-dim embedding vector for `text`, or None on any
    failure (Ollama down, model not pulled, request error) -- callers
    must treat None as "embedding unavailable, fall back gracefully",
    not raise. Memory retrieval degrading to "no episodic memories
    surfaced this request" is a far smaller problem than a chat request
    failing outright because the embedding model hiccuped.

    task: nomic-embed-text v1 requires a task-instruction prefix on the
    raw text to perform correctly -- confirmed via its own model card
    (huggingface.co/nomic-ai/nomic-embed-text-v1) before relying on it,
    not assumed. Use 'search_document' (default) when embedding stored
    content to be retrieved later, 'search_query' when embedding the
    thing doing the searching (the current prompt, in
    get_relevant_episodic_memory()). Skipping this isn't a cosmetic
    miss -- an initial calibration test run without it produced
    unrelated-topic scores (~0.32-0.42) close enough to related-topic
    scores (~0.54-0.71) that a real cutoff would risk false positives;
    see STATUS.md item 21 for the corrected numbers after adding this."""
    if not text or not text.strip():
        return None
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBEDDING_MODEL, "input": f"{task}: {text}"},
            timeout=EMBED_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            return None
        return embeddings[0]
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Standard cosine similarity, no numpy dependency -- vectors here
    are short-lived (computed per-request) and small in number (bounded
    by EPISODIC_KEEP per key, a handful of rows total per project), so
    plain Python is fast enough; no need for numpy/faiss/a vector index
    at this scale."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
