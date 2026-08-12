"""
Memory consolidation -- Prudhvi's ask, following up on item 20's
semantic/episodic memory split and item 21's embeddings upgrade: is
there a brain-sleep equivalent (synthesizing repeated experience into
durable knowledge), and if so, should it be a fixed feature or a
toggle? Answered in conversation before this was built: toggle, opt-in,
off by default -- the same trust-building-period reasoning as
validate_response_llm() in validation_service.py, but for a stricter
reason: a bad LLM validation judgment just fails to catch one bad
response; a bad consolidation writes a WRONG fact into durable semantic
memory, which then gets included in full in every future prompt for
this project (see ollama_service.py) until someone notices and
corrects it by hand. That asymmetry is why this module fails closed
everywhere validate_response_llm() fails open (see that function's
docstring for its own "LLM judge is down -> assume valid" choice, and
compare to every except branch below, which all mean "don't write").

Prudhvi also asked specifically for citations grounding the summary
and a strict verifier checking those citations, precisely so
verification is tractable rather than "trust the LLM." Two LLM calls,
each simple yes/no or single-line-format prompts rather than JSON --
matching validation_service.py's own established pattern for this
codebase (a 9B local model reliably answering "yes" or "no" beats it
reliably producing well-formed JSON on every call).

Triggered from storage/project_store.py's save_memory() right before
an episodic key's oldest row(s) would be pruned past EPISODIC_KEEP --
the natural "about to actually lose this, sleep on it first" moment,
not a blind per-request or timer-based trigger. Ollama serializes all
inference through one GPU slot on this hardware (STATUS.md item 19),
so this only runs when it would otherwise be silent information loss,
not on every write.
"""

import re
from services.reasoning_service import generate_strict, ReasoningError
from services.logging_config import get_logger

logger = get_logger("aether.consolidation")

_SUMMARIZE_PROMPT = """Here are {n} recent results stored under the memory key "{key}":

{rows_block}

Write ONE concise sentence (max 30 words) that generalizes what these results have in common. Do not add any information, number, or claim that is not directly present in the results above -- if you're not certain something is true across all of them, leave it out.

Respond in EXACTLY this two-line format and nothing else -- no extra commentary before or after, no other labels, IDs written as plain numbers only:

SUMMARY: Revenue grew due to a new product launch.
CITES: 4, 5

Now write your own SUMMARY and CITES lines for the results above (use the real IDs shown above, not 4 or 5 -- those are just formatting examples):"""

_VERIFY_PROMPT = """You are strictly checking a summary against its cited sources. The summary must be fully supported by the source text below -- every claim in it must be directly verifiable from the sources, with nothing added, exaggerated, generalized beyond what's stated, or inferred.

Summary: {summary}

Cited sources:
{rows_block}

Is the summary fully and strictly supported by these sources, with no unsupported additions? Answer with exactly one word: yes or no."""


def _format_rows(rows: list[tuple[int, str]]) -> str:
    return "\n".join(f"[ID {rid}] {value}" for rid, value in rows)


def generate_consolidated_summary(key: str, rows: list[tuple[int, str]]) -> tuple[str, list[int]] | None:
    """rows: list of (memory_row_id, value) -- the episodic rows being
    consolidated. Returns (summary_text, cited_ids) on success, or None
    if the LLM call failed or the response didn't parse -- callers
    treat None as "don't consolidate," not "retry with a default."""
    prompt = _SUMMARIZE_PROMPT.format(n=len(rows), key=key, rows_block=_format_rows(rows))
    try:
        raw = generate_strict(prompt)
    except ReasoningError:
        logger.warning("consolidation_summarize_failed", key=key, reason="reasoning_error")
        return None

    # Real bug found live 2026-08-12 (see the CITES-parsing comment
    # below for the companion fix): the model didn't reliably put
    # SUMMARY and CITES on distinct lines and appeared to hallucinate a
    # trailing continuation past CITES ("...CITES: [ID 14, ID 15] AI:
    # Sure! Your third-quarter..."). The original `SUMMARY:\s*(.+)`
    # greedily captured everything up to end-of-line/string, which —
    # since there often wasn't a real newline before CITES — meant the
    # "summary" that got written to semantic memory included the CITES
    # marker and the hallucinated tail verbatim. Anchoring the capture
    # to stop right at the literal "CITES:" (non-greedy, DOTALL so it
    # also works if the model DOES use a real newline) fixes this
    # regardless of which formatting the model happens to produce.
    summary_match = re.search(r"SUMMARY:\s*(.+?)\s*CITES:", raw, re.DOTALL)
    cites_match = re.search(r"CITES:\s*(.+)", raw, re.DOTALL)
    if not summary_match or not cites_match:
        logger.warning("consolidation_summarize_unparseable", key=key, raw=raw[:200])
        return None

    summary = summary_match.group(1).strip()
    valid_ids = {rid for rid, _ in rows}
    # Real bug found live 2026-08-12: the original regex required the
    # CITES line to be *purely* digits/commas/whitespace
    # ([\d,\s]+) and captured whatever matched that character class --
    # when the model wrapped IDs as "[ID 16, ID 15]" instead of the
    # requested "16, 15", the class couldn't match the letters/brackets
    # at all, but \s* being optional let it degenerate into matching a
    # single blank space instead of failing outright, silently
    # producing zero citations rather than an unparseable-response
    # rejection. Fixed by capturing the whole rest of the line
    # regardless of wrapper text, then pulling out just the digit runs
    # -- robust to "[ID 16]", "#16", "ID: 16", etc., which a small
    # local model reliably drifts into despite being told the exact
    # format to use.
    cited_ids = [int(m) for m in re.findall(r"\d+", cites_match.group(1))]

    # Reject citations to IDs that weren't even in the source set --
    # a fabricated citation is worse than no citation, since it would
    # otherwise look verified when it isn't grounded in anything real.
    cited_ids = [cid for cid in cited_ids if cid in valid_ids]
    if not summary or not cited_ids:
        logger.warning("consolidation_no_valid_citations", key=key, raw=raw[:200])
        return None

    return summary, cited_ids


def verify_consolidation(summary: str, cited_rows: list[tuple[int, str]]) -> bool:
    """Strict entailment check: does the cited source text actually
    support the summary, with nothing added? Fails closed on every
    error path (ReasoningError, unparseable response, anything other
    than an explicit "yes") -- see this module's docstring for why
    that's the deliberate opposite of validate_response_llm()'s
    fail-open default."""
    prompt = _VERIFY_PROMPT.format(summary=summary, rows_block=_format_rows(cited_rows))
    try:
        raw = generate_strict(prompt).strip().lower()
    except ReasoningError:
        logger.warning("consolidation_verify_failed", reason="reasoning_error")
        return False

    return raw.startswith("yes")
