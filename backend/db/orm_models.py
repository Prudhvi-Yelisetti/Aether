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
    # Added in 44f9e98b07f2 — see that migration's docstring. All
    # nullable: rows written before this migration have NULL here, and
    # the frontend treats a missing capability_type as "no trace to
    # show" rather than a broken one.
    capability_type = Column(String, nullable=True)
    capability_name = Column(String, nullable=True)
    capability_source = Column(String, nullable=True)
    attempts = Column(Integer, nullable=True)
    escalated = Column(Boolean, nullable=True)
    llm_validation = Column(String, nullable=True)  # "valid" | "flagged" | None (didn't run)


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


class StepMetric(Base):
    """The "Metrics" quarter of ARCHITECTURE.md's Step Service definition
    (Execution contract / Script / Validation / Metrics — see
    services/steps/base.py for the other three). One row per Step
    invocation inside a Skill run: which step, which skill, whether it
    succeeded, whether it passed its own validate(), how long it took.
    Distinct from `experiences` (Phase C), which logs at the whole-request
    level — this is per-Step, the finer grain a future Evolution/Cost
    Engine service would need to answer "which specific step in a Skill is
    slow or unreliable," not just "did the overall request succeed.\""""
    __tablename__ = "step_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_name = Column(String, nullable=False)
    step_version = Column(String, nullable=True)  # from ScriptMeta at call time
    skill_name = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    success = Column(Boolean, default=True)
    valid = Column(Boolean, default=True)  # result of Step.validate()
    validation_reason = Column(String, nullable=True)
    latency_ms = Column(Float)
    timestamp = Column(DateTime, server_default=func.now())
