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
from db.database import SessionLocal
from db.orm_models import Project, Chat, Memory
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

logger = logging.getLogger("aether.storage")


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


def save_memory(project_id: str, key: str, value: str):
    """Upserts on (project_id, key) — see the unique constraint added in
    Alembic revision f33fab44be66. This is what stops memory from
    accumulating unbounded duplicate rows: a repeated fact updates the
    existing row's value (and timestamp) instead of inserting a new one."""
    db = SessionLocal()
    try:
        stmt = sqlite_insert(Memory).values(
            project_id=project_id, key=key, value=value
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "key"],
            set_={"value": value},
        )
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("save_memory failed for project_id=%r key=%r", project_id, key, exc_info=True)
        raise
    finally:
        db.close()


def get_memory(project_id: str):
    db = SessionLocal()
    try:
        rows = db.query(Memory.key, Memory.value).filter(Memory.project_id == project_id).all()
        return [(r[0], r[1]) for r in rows]
    finally:
        db.close()


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
