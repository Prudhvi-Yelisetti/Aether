"""
Storage for the Experience log (see db/orm_models.py's Experience model and
ARCHITECTURE.md's Experience Service).
"""

import logging
from db.database import SessionLocal
from db.orm_models import Experience

logger = logging.getLogger("aether.storage")


def log_experience(
    project_id,
    request_id: str,
    prompt: str,
    tool: str | None,
    tool_source: str | None,
    model: str,
    success: bool,
    latency_ms: float,
):
    """Best-effort logging: a failure here should never break the request
    that's being logged. This is observational, not load-bearing."""
    db = SessionLocal()
    try:
        row = Experience(
            project_id=project_id,
            request_id=request_id,
            prompt=prompt,
            tool=tool,
            tool_source=tool_source,
            model=model,
            success=success,
            latency_ms=latency_ms,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("log_experience failed", exc_info=True)
    finally:
        db.close()
