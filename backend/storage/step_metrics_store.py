"""
Storage for per-Step metrics (see db/orm_models.py's StepMetric and
services/steps/base.py's module docstring for how this fits the
Execution contract / Script / Validation / Metrics structure).
"""

import logging
from sqlalchemy import func

from db.database import SessionLocal
from db.orm_models import StepMetric

logger = logging.getLogger("aether.storage")


def log_step_metric(
    step_name: str,
    step_version: str | None,
    skill_name: str | None,
    request_id: str | None,
    success: bool,
    valid: bool,
    validation_reason: str | None,
    latency_ms: float,
):
    """Best-effort logging: a failure here should never break the Skill run
    that's being measured."""
    db = SessionLocal()
    try:
        row = StepMetric(
            step_name=step_name,
            step_version=step_version,
            skill_name=skill_name,
            request_id=request_id,
            success=success,
            valid=valid,
            validation_reason=validation_reason,
            latency_ms=latency_ms,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("log_step_metric failed", exc_info=True)
    finally:
        db.close()


def get_step_stats(step_name: str) -> dict:
    """Aggregated metrics for one Step — call count, success rate,
    validation-pass rate, average latency. This is the actual point of
    calling this "Metrics" rather than just a log: a future Cost Engine or
    Evolution Service (ROADMAP.md Phase F+) needs aggregates like these to
    decide whether a Step's implementation needs improving, not raw rows.

    SQLite has no portable native boolean-average across drivers, so
    success/validation rates are computed via explicit COUNT queries rather
    than AVG(CAST(bool)) — simpler and correct everywhere, at the cost of
    a few more round trips (fine at this data volume)."""
    db = SessionLocal()
    try:
        total = db.query(func.count(StepMetric.id)).filter(
            StepMetric.step_name == step_name
        ).scalar() or 0

        if total == 0:
            return {
                "step_name": step_name,
                "call_count": 0,
                "success_rate": None,
                "validation_pass_rate": None,
                "avg_latency_ms": None,
            }

        successes = db.query(func.count(StepMetric.id)).filter(
            StepMetric.step_name == step_name, StepMetric.success == True  # noqa: E712
        ).scalar() or 0
        valid_count = db.query(func.count(StepMetric.id)).filter(
            StepMetric.step_name == step_name, StepMetric.valid == True  # noqa: E712
        ).scalar() or 0
        avg_latency = db.query(func.avg(StepMetric.latency_ms)).filter(
            StepMetric.step_name == step_name
        ).scalar()

        return {
            "step_name": step_name,
            "call_count": total,
            "success_rate": successes / total,
            "validation_pass_rate": valid_count / total,
            "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
        }
    finally:
        db.close()
