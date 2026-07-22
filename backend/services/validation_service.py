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

FAILURE_PREFIXES is deliberately the single source of truth for "does this
string look like an internal failure message rather than real content."
reasoning_service.generate_strict() and main.py's /chat endpoint both used
to keep their own separate, slightly-different copies of this list — the
same pattern (one fact, N hardcoded copies) that caused the model-name bug
this session already fixed once. Not repeating it here.
"""

from dataclasses import dataclass

# Ollama/Reasoning Service failures (see reasoning_service.py's
# generate_response() error branches). Public — reasoning_service.py
# imports this directly for its own narrower generate_strict() check,
# since it only ever sees reasoning-layer failures, never Tool/Skill ones.
REASONING_FAILURE_PREFIXES = (
    "Could not reach Ollama",
    "Request to",       # "Request to {model} timed out after ..."
    "Request failed:",
    "Error from",        # "Error from {model}: {data}"
)

# Tool/Skill failures (see services/tools/*.py, services/steps/*.py,
# planning_service.execute_plan()'s "Couldn't complete this: ..." wrapper).
_CAPABILITY_FAILURE_PREFIXES = (
    "Execution timed out",
    "Execution blocked",
    "Access denied",
    "File not found",
    "Not a file",
    "Search failed",
    "No useful results",
    "Could not generate code",
    "Couldn't complete this",
)

# The full set — used by validate_response() below, which checks a final
# response regardless of whether it came from reasoning, a Tool, or a Skill.
FAILURE_PREFIXES = REASONING_FAILURE_PREFIXES + _CAPABILITY_FAILURE_PREFIXES


@dataclass
class ValidationResult:
    valid: bool
    reason: str | None = None  # short machine-readable tag, e.g. "known_failure_prefix"


def validate_response(response: str | None) -> ValidationResult:
    """Deterministic check only, by design (see module docstring). Returns
    valid=False for empty output or a known internal-failure string;
    otherwise valid=True. LLM-based validation (e.g. "does this actually
    answer the question") is deliberately out of scope for this first pass
    — add it as a second, opt-in check once this one is live and proven,
    not bundled in from the start."""
    if not response or not response.strip():
        return ValidationResult(valid=False, reason="empty_response")

    if response.startswith(FAILURE_PREFIXES):
        return ValidationResult(valid=False, reason="known_failure_prefix")

    return ValidationResult(valid=True)
