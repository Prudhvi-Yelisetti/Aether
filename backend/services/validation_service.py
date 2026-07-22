"""
Phase E2 (ROADMAP.md): "Add a Validator step between generation and
delivery (start with deterministic checks... before adding LLM-based
validation)."

Distinct from Step.validate() (services/steps/*.py), which checks a single
Step's own output mid-Skill. This module validates the *final* response
about to be delivered to the user, regardless of whether it came from raw
reasoning, a Tool, or a Skill.

Scoped narrow deliberately, per the roadmap's own sequencing: deterministic
checks first. This first check exists because of a real, live-observed bug
(2026-07-21/22, see STATUS.md): a raw Ollama timeout string —
"Request to qwen3.5:9b timed out after 60s" — was delivered to the user as
if it were a legitimate chat answer, with HTTP 200. The response was never
wrong-looking enough to catch by accident; it read like a normal string
until you noticed the content. A deterministic prefix check catches this
class of failure for free — no LLM call, no added latency, no ambiguity.

The failure-prefix -> retryable mapping below is deliberately the single
source of truth for "does this string look like an internal failure
message" AND "is retrying likely to help" — both questions the Validator
already has to answer to classify a failure, so Phase E3's Decision step
(services/decision_service.py) asks this module rather than re-deciding
retryability itself. reasoning_service.generate_strict() and main.py's
/chat endpoint both used to keep their own separate, slightly-different
copies of the failure-string list — the same pattern (one fact, N
hardcoded copies) that caused the model-name bug this session fixed once
already. Not repeating it here.
"""

from dataclasses import dataclass

# Ollama/Reasoning Service failures (see reasoning_service.py's
# generate_response() error branches), mapped to whether a second attempt
# at the identical call is likely to produce a different result.
#   - "Could not reach Ollama" (connection refused) and "Request to ...
#     timed out" are classic transient conditions — a brief outage or a
#     slow response — worth one retry.
#   - "Request failed:" wraps any other requests-library exception; often
#     transient (DNS blip, reset connection) — worth one retry.
#   - "Error from {model}: {data}" means Ollama responded with a
#     structured error (bad model name, bad params) — the identical call
#     will fail identically. Not retryable.
_REASONING_RETRYABLE = {
    "Could not reach Ollama": True,
    "Request to": True,
    "Request failed:": True,
    "Error from": False,
}

# Tool/Skill failures (see services/tools/*.py, services/steps/*.py,
# planning_service.execute_plan()'s "Couldn't complete this: ..." wrapper),
# same mapping. Most of these are permanent for a given input — retrying
# the exact same tool call with the exact same arguments will fail the
# exact same way, so retry is only marked True where the underlying cause
# plausibly varies between attempts (timeouts, network calls).
_CAPABILITY_RETRYABLE = {
    "Execution timed out": True,
    "Execution blocked": False,
    "Access denied": False,
    "File not found": False,
    "Not a file": False,
    "Search failed": True,
    "No useful results": False,
    "Could not generate code": True,
    "Couldn't complete this": False,
}

_ALL_RETRYABLE = {**_REASONING_RETRYABLE, **_CAPABILITY_RETRYABLE}

# Public — reasoning_service.py imports this directly for its own narrower
# generate_strict() check, since it only ever sees reasoning-layer
# failures, never Tool/Skill ones.
REASONING_FAILURE_PREFIXES = tuple(_REASONING_RETRYABLE)
_CAPABILITY_FAILURE_PREFIXES = tuple(_CAPABILITY_RETRYABLE)

# The full set — used by validate_response() below, which checks a final
# response regardless of whether it came from reasoning, a Tool, or a Skill.
FAILURE_PREFIXES = REASONING_FAILURE_PREFIXES + _CAPABILITY_FAILURE_PREFIXES


@dataclass
class ValidationResult:
    valid: bool
    reason: str | None = None      # short machine-readable tag
    retryable: bool = False        # only meaningful when valid=False


def validate_response(response: str | None) -> ValidationResult:
    """Deterministic check only, by design (see module docstring). Returns
    valid=False for empty output or a known internal-failure string
    (with retryable set per the mapping above); otherwise valid=True.
    LLM-based validation (e.g. "does this actually answer the question")
    is deliberately out of scope for this first pass — add it as a second,
    opt-in check once this one is live and proven, not bundled in from
    the start."""
    if not response or not response.strip():
        # Empty output could be a one-off generation hiccup — worth a
        # single retry rather than assuming it's permanent.
        return ValidationResult(valid=False, reason="empty_response", retryable=True)

    for prefix, retryable in _ALL_RETRYABLE.items():
        if response.startswith(prefix):
            return ValidationResult(valid=False, reason="known_failure_prefix", retryable=retryable)

    return ValidationResult(valid=True)
