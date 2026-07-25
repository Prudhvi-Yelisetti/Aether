import difflib
import re

from services.steps.base import Step, StepResult
from services.steps.script_meta import ScriptMeta

# Common words in a request that aren't part of the topic/filename itself.
# Deliberately small and hand-picked, not a general stopword list — this
# only needs to strip the handful of words that actually show up in
# requests like "summarize my X file for me".
_STOPWORDS = {
    "a", "an", "the", "my", "for", "me", "to", "and", "of", "please",
    "can", "you", "find", "summarize", "summarise", "file", "files",
    "notes", "note", "that", "this", "about", "digest", "read",
}

MATCH_CUTOFF = 0.4


def _best_match(candidate: str, available: list[str]) -> str | None:
    """Two passes, cheaper/more-precise first:

    1. Whole-string match against the candidate as given — handles the
       case where the candidate already resembles a filename closely
       (e.g. "jazzmusic.txt", "great_wall_china").
    2. Token-level fallback — strips filler words, then compares each
       remaining word against each file's name (extension/underscores
       stripped) individually, keeping the single best-scoring pair.
       Needed because a whole natural-language sentence ("summarize my
       jazz file for me") rarely resembles a single filename by
       character-sequence similarity, even when a human would
       immediately see the connection — found live, 2026-07-25, see
       STATUS.md: the whole-string-only version failed on exactly this
       kind of realistic prompt, twice, despite the Planner and every
       other step in the chain working correctly."""
    direct = difflib.get_close_matches(candidate, available, n=1, cutoff=MATCH_CUTOFF)
    if direct:
        return direct[0]

    words = [w.lower() for w in re.findall(r"\w+", candidate)]
    words = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    if not words:
        return None

    best_name, best_score = None, 0.0
    for name in available:
        stem = name.rsplit(".", 1)[0].replace("_", " ").lower()
        for word in words:
            score = difflib.SequenceMatcher(None, word, stem).ratio()
            if word in stem:
                score = max(score, 0.6)  # literal substring is a strong signal
            if score > best_score:
                best_name, best_score = name, score

    return best_name if best_score >= MATCH_CUTOFF else None


class FindFileStep(Step):
    """Deterministic — no LLM call. Fuzzy-matches context[candidate_key]
    (a possibly-imperfect filename, or a whole natural-language request —
    see _best_match() above) against context[listing_key] (ListFilesStep's
    output), and writes the best real match.

    Named "filename" specifically so its output lands in
    context['filename'] via Skill.run()'s context[step.name] mechanism
    (see services/skills/base.py) — that's exactly what ReadFileStep
    already expects, so it's reused completely unchanged, no
    modification needed.

    Exists because "File not found" has been the most common permanent
    Tool/Skill failure observed this session (see STATUS.md) — usually
    because the requested name was close but not exact. This doesn't
    eliminate that failure mode (a genuinely unrelated candidate still
    won't match), but it survives near-misses: typos, missing
    extensions, partial names, and — after this revision — full
    natural-language requests that only mention the topic in passing."""
    name = "filename"
    description = "Fuzzy-matches a candidate filename (or a natural-language request mentioning one) against the real files in the workspace."
    script = ScriptMeta(
        step_id="step.find_file",
        version="1.1.0",
        owner="prudhvi",
        history=(
            "1.0.0: initial implementation, built for FindAndDigestFileSkill",
            "1.1.0: added token-level fallback matching — whole-string-only "
            "matching failed live on realistic natural-language prompts "
            "(e.g. \"summarize my jazz file for me\") despite every other "
            "part of the chain working correctly; see STATUS.md.",
        ),
    )

    def __init__(self, candidate_key: str = "candidate_filename", listing_key: str = "list_files"):
        self.candidate_key = candidate_key
        self.listing_key = listing_key

    def run(self, context: dict) -> StepResult:
        candidate = context.get(self.candidate_key)
        listing = context.get(self.listing_key)

        if not candidate:
            return StepResult(success=False, error=f"context['{self.candidate_key}'] is required")
        if not listing:
            return StepResult(success=False, error=f"context['{self.listing_key}'] is required")

        available = [line.strip() for line in listing.splitlines() if line.strip()]
        match = _best_match(candidate, available)

        if not match:
            return StepResult(success=False, error=f"No file in the workspace resembles '{candidate}'")

        return StepResult(success=True, output=match)
