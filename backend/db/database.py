"""
SQLAlchemy engine + session management.

Replaces the old single global `sqlite3.connect(..., check_same_thread=False)`
connection, which was shared across every request. FastAPI handles requests
concurrently, so that one connection/cursor was a real data-corruption risk
under concurrent writes — check_same_thread=False silences the error without
fixing the underlying problem.

This module gives every request its own pooled connection via a session
factory. Table creation has moved to Alembic migrations (see alembic/ and
alembic.ini) — this module no longer creates tables itself.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///aether.db"

# check_same_thread=False is still needed for SQLite specifically (its C
# connections are bound to the thread that created them by default), but
# unlike the old code, each request now gets its OWN connection from the
# pool rather than sharing one — so this flag is no longer covering up a
# concurrency bug.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
