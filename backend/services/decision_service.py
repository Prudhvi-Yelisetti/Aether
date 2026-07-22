"""
Phase E3 (ROADMAP.md): "Add a Decision step: deliver / retry / escalate,
instead of always delivering."

Sits after generation and validation (E2), before delivery. Given a
callable that produces one attempt at a response, decide():

  1. runs it once
  2. validates the result (services/validation_service.py)
  3. if invalid AND the failure looks transient (validation.retryable),
     retries — bounded to MAX_ATTEMPTS total, this is one extra try, not
     a retry loop
  4. if still invalid after that, escalates: returns a clear, honest
     failure message instead of ever delivering an internal error string
     (the exact bug E2 was built to close — see validation_service.py's
     docstring)
  5. if valid at any point, delivers that response as-is

Retryability is the Validator's call (validate_response() already owns
the failure-prefix taxonomy and knows which failures are transient vs
permanent), not re-decided here — Decision only acts on what Validation
already determined. Keeps the two layers doing one job each, matching how
Planning (capability selection) and the Reasoning Service (model
selection) were deliberately kept as two separate calls in E1.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from services.logging_config import get_logger
from services.validation_service import validate_response

logger = get_logger("aether.decision")

# One original attempt + one retry. Not configurable yet — deliberately
# small and fixed for this first pass; revisit only with live evidence
# that one retry isn't enough, the same discipline used for every other
# fix this session (see STATUS.md).
MAX_ATTEMPTS = 2


@dataclass
class DecisionResult:
    response: str
    valid: bool
    escalated: bool
    attempts: int
    reason: Optional[str] = None


def decide(attempt_fn: Callable[[], str]) -> DecisionResult:
    """attempt_fn() must produce one full response for one full attempt
    (e.g. one call to generate() or one execute_plan()) — decide() does
    not know or care what kind of attempt it is, only whether the result
    validates."""
    attempts = 0
    response = attempt_fn()
    attempts += 1
    validation = validate_response(response)

    while not validation.valid and validation.retryable and attempts < MAX_ATTEMPTS:
        logger.info(
            "decision_retry",
            reason=validation.reason,
            attempt_number=attempts + 1,
        )
        response = attempt_fn()
        attempts += 1
        validation = validate_response(response)

    if validation.valid:
        return DecisionResult(
            response=response,
            valid=True,
            escalated=False,
            attempts=attempts,
            reason=None,
        )

    logger.warning(
        "decision_escalated",
        reason=validation.reason,
        retryable=validation.retryable,
        attempts=attempts,
    )
    plural = "s" if attempts != 1 else ""
    escalated_response = (
        f"Something went wrong generating a response after {attempts} "
        f"attempt{plural} — please try again. (reason: {validation.reason})"
    )
    return DecisionResult(
        response=escalated_response,
        valid=False,
        escalated=True,
        attempts=attempts,
        reason=validation.reason,
    )
