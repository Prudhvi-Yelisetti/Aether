from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, UniqueConstraint, func
from db.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, nullable=False)
    prompt = Column(String)
    response = Column(String)
    model = Column(String)
    timestamp = Column(DateTime, server_default=func.now())


class Memory(Base):
    __tablename__ = "memory"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_memory_project_key"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    key = Column(String, nullable=False)
    value = Column(String)
    timestamp = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Experience(Base):
    """ARCHITECTURE.md's Experience Service, minimal version: a structured
    record of what happened on each execution (which tool/model handled it,
    whether it succeeded, how long it took). Purely additive — nothing reads
    from this yet. It exists so a future Evolution Service (see ROADMAP.md
    Phase F+) has real data to learn from instead of nothing, and so
    "why did this get slow / start failing" has an answer beyond guessing."""
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=True)
    request_id = Column(String, nullable=True)
    prompt = Column(String)
    tool = Column(String, nullable=True)  # null when handled by raw LLM generation
    tool_source = Column(String, nullable=True)  # "rule" | "llm" | "none"
    model = Column(String)
    success = Column(Boolean, default=True)
    latency_ms = Column(Float)
    timestamp = Column(DateTime, server_default=func.now())
