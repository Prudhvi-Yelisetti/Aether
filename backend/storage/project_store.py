"""
Data access layer for projects, chats, and memory.

Rewritten to use SQLAlchemy sessions (see db/database.py) instead of a single
shared sqlite3 cursor. Each function now opens its own short-lived session
via SessionLocal() rather than reusing a global connection — this is what
actually fixes the concurrency issue, not just the ORM swap by itself.

Function names and return shapes are kept identical to the previous version
so main.py does not need to change.
"""

import json
import re
from db.database import SessionLocal
from db.orm_models import Project, Chat, Memory
from services.embedding_service import get_embedding, cosine_similarity
from services.logging_config import get_logger

logger = get_logger("aether.storage")

# Real bug fixed structurally in a91c3d5e7f02 (see that migration's
# docstring for the full brain-memory-systems rationale). Two kinds of
# memory, handled differently below:
#
# 'semantic' — durable, context-independent facts about the user (name,
# stated preferences). One current value per key, same as before —
# still upserted, just via an explicit query-then-write instead of the
# old sqlite_insert().on_conflict_do_update() (that relied on the
# now-dropped table-wide unique constraint to define "conflict"; without
# it, an atomic upsert has nothing to key off). Small accepted
# tradeoff: this has a race window under truly concurrent writers to
# the exact same key, which the old atomic upsert didn't. Not a real
# risk here — Aether is single-user local software, and both SQLite's
# own write serialization and Ollama's single inference slot (see
# STATUS.md item 19) already serialize what would trigger this in
# practice.
#
# 'episodic' — specific past skill-run results (last_research,
# last_file_digest). Always INSERTed as a new row, never overwritten,
# then pruned back to EPISODIC_KEEP most recent per (project_id, key).
# This is the deliberate brain-memory parallel: bounded-capacity, most-
# recent-favored retention (a short episodic buffer, roughly analogous
# to how only a handful of specific recent episodes stay easily
# recallable) rather than the old behavior of unboundedly overwriting
# a single row, which silently destroyed all history of prior runs on
# every new one — the wrong kind of forgetting.
EPISODIC_KEEP = 3

# Cosine-similarity cutoff for get_relevant_episodic_memory() below.
# Measured live against this project's own real test data (a stored
# episode about Q3 revenue/pricing-tier growth), using nomic-embed-text
# v1 with its required search_query/search_document task prefixes (see
# embedding_service.py's docstring — an initial run without those
# prefixes gave meaningfully worse separation and was discarded, not
# used to set this number):
#   direct reuse of a word from the episode ......... 0.719
#   genuine paraphrase, no shared words .............. 0.697
#   loosely related business topic .................... 0.613
#   -------------------------------------------------- (real cases end here)
#   clearly unrelated ("boiling point of water") ...... 0.516
#   clearly unrelated ("birthday poem") ................ 0.416
#   clearly unrelated ("pasta recipe") .................. 0.390
# 0.55 sits in the ~0.10 gap between the lowest related score (0.613)
# and the highest unrelated one (0.516). That gap is real but not huge
# — this model doesn't push unrelated-sentence similarity anywhere near
# zero the way some embedding models do, so there's real proximity to a
# false positive/negative right around this line. Calibrated on one
# stored document and six test prompts, not a rigorous study — revisit
# with more real usage data if either direction turns out wrong.
EPISODIC_SIMILARITY_THRESHOLD = 0.55

# Cheap English stopword list — kept as a fallback for _tokenize(),
# used only when embeddings are unavailable (Ollama down, embedding
# model not pulled) so retrieval degrades to the old keyword-overlap
# heuristic instead of returning nothing. See
# get_relevant_episodic_memory()'s docstring for when this path fires.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "to", "in", "on", "for", "with",
    "this", "that", "it", "as", "at", "by", "from", "what", "which",
    "who", "how", "do", "does", "did", "can", "could", "would", "will",
    "you", "your", "i", "me", "my", "we", "our", "about", "into", "up",
}


def _tokenize(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOPWORDS}


def create_project(name: str):
    db = SessionLocal()
    try:
        project = Project(name=name)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    except Exception:
        db.rollback()
        logger.warning("create_project failed for name=%r", name, exc_info=True)
        return None
    finally:
        db.close()


def get_projects():
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        result = {}

        for proj in projects:
            project_id = str(proj.id)
            result[project_id] = {"name": proj.name, "chats": []}

            chats = (
                db.query(Chat)
                .filter(Chat.project_id == proj.id)
                .all()
            )
            for chat in chats:
                result[project_id]["chats"].append({
                    "prompt": chat.prompt,
                    "response": chat.response,
                    "model": chat.model,
                })

        return result
    finally:
        db.close()


def get_project_chats(project_id: str):
    db = SessionLocal()
    try:
        rows = (
            db.query(Chat.chat_id)
            .filter(Chat.project_id == project_id)
            .distinct()
            .all()
        )
        return [row[0] for row in rows]
    finally:
        db.close()


def create_chat(project_id: str):
    db = SessionLocal()
    try:
        last = (
            db.query(Chat.chat_id)
            .filter(Chat.project_id == project_id)
            .order_by(Chat.chat_id.desc())
            .first()
        )
        return (last[0] + 1) if last else 1
    finally:
        db.close()


def add_chat(project_id: str, chat_id: int, chat: dict):
    db = SessionLocal()
    try:
        row = Chat(
            project_id=project_id,
            chat_id=chat_id,
            prompt=chat["prompt"],
            response=chat["response"],
            model=chat["model"],
            # Optional — see 44f9e98b07f2. main.py always passes these
            # now, but .get() keeps this function usable from anywhere
            # that only has the older three fields (tests, scripts).
            capability_type=chat.get("capability_type"),
            capability_name=chat.get("capability_name"),
            capability_source=chat.get("capability_source"),
            attempts=chat.get("attempts"),
            escalated=chat.get("escalated"),
            llm_validation=chat.get("llm_validation"),
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("add_chat failed for project_id=%r chat_id=%r", project_id, chat_id, exc_info=True)
        raise
    finally:
        db.close()


def project_exists(project_id: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(Project.id).filter(Project.id == project_id).first() is not None
    finally:
        db.close()


def save_memory(project_id: str, key: str, value: str, memory_type: str = "semantic", provenance: str = None, consolidate: bool = False):
    """memory_type='semantic' (default): upserts on (project_id, key) —
    one current value per fact, same external behavior as before.
    provenance (semantic only): set when this write came from
    consolidation (services/consolidation_service.py) rather than
    direct extraction/a user statement — see b47e91a3c6d4's docstring.
    memory_type='episodic': always inserts a new row (keeps history
    instead of overwriting it), computes and stores an embedding for
    it (services/embedding_service.py — used by
    get_relevant_episodic_memory() below), then prunes back to
    EPISODIC_KEEP most recent rows for that (project_id, key). See the
    module-level comment above for the full rationale.
    consolidate (episodic only, opt-in, default False — see
    consolidation_service.py's module docstring for the full design):
    when a new episodic write would push this key past EPISODIC_KEEP,
    generate a citation-grounded summary from ALL current rows for this
    key (the ones about to be kept AND the ones about to be pruned —
    grounded in the recent pattern, not just what's being discarded),
    verify it strictly, and if it passes, write it to semantic memory
    with provenance before pruning proceeds. Pruning happens either
    way, whether consolidation runs, succeeds, or fails — bounded
    episodic capacity is unconditional; consolidation is a side effect
    on top of it, never a reason to keep more episodic rows than the
    cap allows."""
    db = SessionLocal()
    try:
        if memory_type == "episodic":
            vec = get_embedding(f"{key} {value}", task="search_document")
            embedding_json = json.dumps(vec) if vec is not None else None
            db.add(Memory(project_id=project_id, key=key, value=value, memory_type="episodic", embedding=embedding_json))
            db.commit()

            all_rows = (
                db.query(Memory.id, Memory.value)
                .filter(Memory.project_id == project_id, Memory.key == key, Memory.memory_type == "episodic")
                .order_by(Memory.id.desc())
                .all()
            )
            keep_ids = [r[0] for r in all_rows[:EPISODIC_KEEP]]
            about_to_prune = len(all_rows) > EPISODIC_KEEP

            if consolidate and about_to_prune:
                _try_consolidate(project_id, key, [(r[0], r[1]) for r in all_rows])

            if keep_ids:
                (
                    db.query(Memory)
                    .filter(
                        Memory.project_id == project_id,
                        Memory.key == key,
                        Memory.memory_type == "episodic",
                        ~Memory.id.in_(keep_ids),
                    )
                    .delete(synchronize_session=False)
                )
                db.commit()
        else:
            existing = (
                db.query(Memory)
                .filter(Memory.project_id == project_id, Memory.key == key, Memory.memory_type == "semantic")
                .first()
            )
            if existing:
                existing.value = value
                existing.provenance = provenance
            else:
                db.add(Memory(project_id=project_id, key=key, value=value, memory_type="semantic", provenance=provenance))
            db.commit()
    except Exception:
        db.rollback()
        logger.error(
            "save_memory_failed",
            project_id=project_id, key=key, memory_type=memory_type, exc_info=True,
        )
        raise
    finally:
        db.close()


def _try_consolidate(project_id: str, key: str, rows: list[tuple[int, str]]):
    """Called from save_memory()'s episodic path right before a key's
    oldest row(s) would be pruned past EPISODIC_KEEP. Best-effort: any
    failure here (LLM down, verification rejects it, parsing fails)
    just means no consolidated fact gets written — pruning still
    proceeds regardless in the caller, so this never blocks or corrupts
    the episodic write itself. See consolidation_service.py's module
    docstring for the full design and why this fails closed rather
    than open."""
    from services.consolidation_service import generate_consolidated_summary, verify_consolidation
    import datetime

    result = generate_consolidated_summary(key, rows)
    if result is None:
        return

    summary, cited_ids = result
    rows_by_id = dict(rows)
    cited_rows = [(cid, rows_by_id[cid]) for cid in cited_ids if cid in rows_by_id]
    if not cited_rows:
        logger.warning("consolidation_no_valid_cited_rows", project_id=project_id, key=key)
        return

    if not verify_consolidation(summary, cited_rows):
        logger.warning("consolidation_rejected_by_verifier", project_id=project_id, key=key, summary=summary[:200])
        return

    provenance = (
        f"Consolidated from '{key}' (source memory IDs: {', '.join(str(c) for c in cited_ids)}) "
        f"on {datetime.date.today().isoformat()}"
    )
    save_memory(project_id, f"consolidated_{key}", summary, memory_type="semantic", provenance=provenance)
    logger.info("consolidation_written", project_id=project_id, key=key, cited_ids=cited_ids)


def get_memory(project_id: str, memory_type: str = None):
    """memory_type=None (default): all rows, either type, newest first —
    used by the /memory endpoint so the UI can show everything. Pass
    'semantic' or 'episodic' to filter, as main.py's chat() does when
    building a prompt (see get_relevant_episodic_memory() below for the
    episodic side of that — this plain filter is also used directly by
    callers, like the /memory endpoint, that want the full episodic
    history rather than a relevance-gated subset). Returns
    (key, value, memory_type, provenance) — provenance is None except
    for consolidated semantic rows (b47e91a3c6d4)."""
    db = SessionLocal()
    try:
        q = db.query(Memory.key, Memory.value, Memory.memory_type, Memory.provenance).filter(Memory.project_id == project_id)
        if memory_type:
            q = q.filter(Memory.memory_type == memory_type)
        rows = q.order_by(Memory.id.desc()).all()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
    finally:
        db.close()


def get_relevant_episodic_memory(project_id: str, prompt: str, limit: int = 3):
    """Cue-dependent retrieval for episodic memory — the retrieval-side
    half of the structural fix in a91c3d5e7f02 (see that migration's
    docstring). The old behavior injected every stored row into every
    prompt regardless of topic, mitigated only by telling the model to
    "ignore it if not relevant" (STATUS.md item 13) — real mitigation,
    not a fix, since the model still paid the token cost and still had
    to do the filtering itself, imperfectly.

    Upgraded 2026-08-10 (STATUS.md item 21) from plain keyword overlap
    to embedding-based cosine similarity (services/embedding_service.py,
    nomic-embed-text) — the keyword-overlap version's own docstring
    already flagged its real limit: a prompt meaning the same thing in
    different words wouldn't match. Checked live against how current
    agent-memory systems (Letta/MemGPT, Mem0, Zep) actually do this
    before building: all of them retrieve via dense embedding
    similarity, not keyword matching, so this brings Aether in line
    with that rather than reinventing something novel.

    Rows below EPISODIC_SIMILARITY_THRESHOLD are dropped entirely —
    same "cue fails to surface anything, rather than showing it anyway"
    principle as before, just measured continuously (cosine similarity)
    instead of binary (any shared word or not). Graceful fallback: if
    the embedding model is unavailable (Ollama down, not pulled) or a
    stored row predates the embedding upgrade and has no vector, this
    degrades to the original keyword-overlap heuristic for that
    request/row rather than silently returning nothing — a worse-
    quality match beats a request that can't recall anything at all
    because of an unrelated infrastructure hiccup."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Memory.key, Memory.value, Memory.embedding)
            .filter(Memory.project_id == project_id, Memory.memory_type == "episodic")
            .order_by(Memory.id.desc())
            .all()
        )
    finally:
        db.close()

    if not rows:
        return []

    prompt_vec = get_embedding(prompt, task="search_query")
    prompt_words = _tokenize(prompt) if prompt_vec is None else None

    scored = []
    for key, value, embedding_json in rows:
        row_vec = json.loads(embedding_json) if embedding_json else None
        if prompt_vec is not None and row_vec is not None:
            score = cosine_similarity(prompt_vec, row_vec)
            if score >= EPISODIC_SIMILARITY_THRESHOLD:
                scored.append((score, key, value))
        else:
            # Fallback path: either the embedding model is down for this
            # request, or this specific row predates the upgrade and has
            # no stored vector. Keyword overlap, scaled down so it never
            # outranks a real embedding match if both paths somehow mix
            # in the same result set.
            words = prompt_words if prompt_words is not None else _tokenize(prompt)
            overlap = len(words & _tokenize(f"{key} {value}"))
            if overlap > 0:
                scored.append((overlap / 100.0, key, value))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [(key, value) for _, key, value in scored[:limit]]


def get_project_full_data(project_id: str):
    db = SessionLocal()
    try:
        rows = (
            db.query(
                Chat.chat_id,
                Chat.prompt,
                Chat.response,
                Chat.model,
                Chat.capability_type,
                Chat.capability_name,
                Chat.capability_source,
                Chat.attempts,
                Chat.escalated,
                Chat.llm_validation,
            )
            .filter(Chat.project_id == project_id)
            .order_by(Chat.id.asc())
            .all()
        )

        chats = {}
        for (chat_id, prompt, response, model, capability_type,
             capability_name, capability_source, attempts, escalated,
             llm_validation) in rows:
            chats.setdefault(chat_id, []).append({
                "prompt": prompt,
                "response": response,
                "model": model,
                "capability_type": capability_type,
                "capability_name": capability_name,
                "capability_source": capability_source,
                "attempts": attempts,
                "escalated": escalated,
                "llm_validation": llm_validation,
            })

        return chats
    finally:
        db.close()


def get_chat_history(project_id: str, chat_id: int, limit: int = 10):
    db = SessionLocal()
    try:
        rows = (
            db.query(Chat.prompt, Chat.response)
            .filter(Chat.project_id == project_id, Chat.chat_id == chat_id)
            .order_by(Chat.id.desc())
            .limit(limit)
            .all()
        )
        return [(r[0], r[1]) for r in rows][::-1]
    finally:
        db.close()
