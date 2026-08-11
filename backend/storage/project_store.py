"""
Data access layer for projects, chats, and memory.

Rewritten to use SQLAlchemy sessions (see db/database.py) instead of a single
shared sqlite3 cursor. Each function now opens its own short-lived session
via SessionLocal() rather than reusing a global connection — this is what
actually fixes the concurrency issue, not just the ORM swap by itself.

Function names and return shapes are kept identical to the previous version
so main.py does not need to change.
"""

import logging
import re
from db.database import SessionLocal
from db.orm_models import Project, Chat, Memory

logger = logging.getLogger("aether.storage")

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

# Cheap English stopword list for the keyword-overlap relevance filter
# in get_relevant_episodic_memory() below — without this, "the" or "is"
# appearing in both the prompt and a stored episode would count as a
# real match and defeat the point of filtering. Deliberately small and
# hand-picked, not a real NLP stopword library — this whole retrieval
# mechanism is an honestly-scoped keyword-overlap heuristic (see that
# function's docstring), not semantic search, and doesn't pretend
# otherwise by reaching for a heavier dependency than the approach
# actually warrants.
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


def save_memory(project_id: str, key: str, value: str, memory_type: str = "semantic"):
    """memory_type='semantic' (default): upserts on (project_id, key) —
    one current value per fact, same external behavior as before.
    memory_type='episodic': always inserts a new row (keeps history
    instead of overwriting it), then prunes back to EPISODIC_KEEP most
    recent rows for that (project_id, key). See the module-level
    comment above for the full rationale."""
    db = SessionLocal()
    try:
        if memory_type == "episodic":
            db.add(Memory(project_id=project_id, key=key, value=value, memory_type="episodic"))
            db.commit()

            keep_ids = [
                r[0] for r in (
                    db.query(Memory.id)
                    .filter(Memory.project_id == project_id, Memory.key == key, Memory.memory_type == "episodic")
                    .order_by(Memory.id.desc())
                    .limit(EPISODIC_KEEP)
                    .all()
                )
            ]
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
            else:
                db.add(Memory(project_id=project_id, key=key, value=value, memory_type="semantic"))
            db.commit()
    except Exception:
        db.rollback()
        logger.error(
            "save_memory failed for project_id=%r key=%r memory_type=%r",
            project_id, key, memory_type, exc_info=True,
        )
        raise
    finally:
        db.close()


def get_memory(project_id: str, memory_type: str = None):
    """memory_type=None (default): all rows, either type, newest first —
    used by the /memory endpoint so the UI can show everything. Pass
    'semantic' or 'episodic' to filter, as main.py's chat() does when
    building a prompt (see get_relevant_episodic_memory() below for the
    episodic side of that — this plain filter is also used directly by
    callers, like the /memory endpoint, that want the full episodic
    history rather than a relevance-gated subset)."""
    db = SessionLocal()
    try:
        q = db.query(Memory.key, Memory.value, Memory.memory_type).filter(Memory.project_id == project_id)
        if memory_type:
            q = q.filter(Memory.memory_type == memory_type)
        rows = q.order_by(Memory.id.desc()).all()
        return [(r[0], r[1], r[2]) for r in rows]
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

    This is a genuine but honestly-scoped heuristic: plain keyword
    overlap between the current prompt and each stored episode's key +
    value (via _tokenize()'s stopword-filtered word sets), not real
    semantic similarity — a prompt that means the same thing in
    different words won't match. That's a real, known limitation, not
    hidden here or in the prompt framing that consumes this (see
    ollama_service.py). Rows with zero shared meaningful words are
    dropped entirely — analogous to episodic recall simply failing to
    surface anything when there's no matching cue, rather than
    defaulting to "show it anyway, might be relevant." Matches are
    ranked by overlap count and capped at `limit`."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Memory.key, Memory.value)
            .filter(Memory.project_id == project_id, Memory.memory_type == "episodic")
            .order_by(Memory.id.desc())
            .all()
        )
    finally:
        db.close()

    if not rows:
        return []

    prompt_words = _tokenize(prompt)
    if not prompt_words:
        return []

    scored = []
    for key, value in rows:
        overlap = len(prompt_words & _tokenize(f"{key} {value}"))
        if overlap > 0:
            scored.append((overlap, key, value))

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
