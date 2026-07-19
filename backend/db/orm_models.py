from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
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

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    key = Column(String, nullable=False)
    value = Column(String)
    timestamp = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Phase B (see ROADMAP.md) will add upsert semantics keyed on
    # (project_id, key) to stop unbounded duplicate memory rows. This
    # constraint is deliberately NOT added yet — it needs to ship together
    # with the upsert logic, not before it, or existing duplicate rows will
    # break migration.
