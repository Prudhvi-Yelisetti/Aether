import requests

from services.logging_config import get_logger
from services.routing import FAST_MODEL

logger = get_logger("aether.ollama")

OLLAMA_URL = "http://localhost:11434/api/generate"
# Live 2026-07-22: the 45s-150s+ latency variance chased on 2026-07-21
# was NOT reload cost or hardware limits — it was qwen3.5:9b's hybrid
# "thinking" mode running unbounded on every call because the API's
# `think` field was never set. Proven directly: identical decision
# prompt, identical correct output ("none") — 30.9s with `think` unset
# (369-char hidden reasoning trace) vs 0.8s with think=False explicit.
# Thinking is now off by default; REQUEST_TIMEOUT_SECONDS restored to a
# sane value since the real problem is fixed, not papered over with a
# bigger number. See STATUS.md for the full A/B test.
REQUEST_TIMEOUT_SECONDS = 60

# Real bug found live 2026-08-05 (see STATUS.md): a genuine, realistic
# user photo (~2MB PNG) consistently timed out at 60s on both the
# initial attempt and the retry -- not the "thinking mode left on"
# problem the comment above already fixed, a real difference in how
# long vision inference takes on a larger image versus a text-only
# call. Frontend now downscales images before sending (see
# ChatWindow.js's downscaleImage()), which should keep most requests
# well under 60s -- but vision decoding is inherently slower than text
# generation even on a modest image, so image-attached requests still
# get a longer ceiling as a safety net, not a substitute for the
# downscaling fix.
IMAGE_REQUEST_TIMEOUT_SECONDS = 180

# Real bug found live 2026-08-09, then corrected mid-investigation --
# see STATUS.md for the full trail. Original claim ("any moderately
# long prompt can silently return empty") was overstated: it came from
# a diagnostic probe that omitted `think: false`, reintroducing the
# exact unbounded-thinking bug the 2026-07-22 fix above already
# resolved -- a test artifact, not a real production bug, since
# generate_response() below always sets think=False.
#
# Redone correctly (think=False, matching production): the real,
# narrower bug is that Ollama's 4096-token default runtime context
# window (model's actual capacity is 262144, confirmed via /api/show)
# is already too tight for realistic near-budget file attachments.
# A 49,731-char prompt (just under main.py's 50k-char attachment
# budget) consumed prompt_eval_count=4095 of the 4096 default almost
# entirely on its own, leaving room for exactly 1 output token --
# response came back as the single truncated word "Based",
# done_reason="length". At num_ctx=16384 the same prompt completes
# normally with a full, coherent answer.
#
# 16384 chosen over the model's full 262144 capacity because this
# machine has a 4GB-VRAM GPU (RTX 3050 laptop, confirmed via
# nvidia-smi) with only ~985MB of a 6.7GB model actually resident on
# it -- most inference is CPU-offloaded at ~6.9 tokens/sec (confirmed
# via ollama's slot print_timing logs), so KV-cache memory is not
# free here. 16384 covers the realistic near-50k-char-budget case with
# room to spare, without the 16x memory jump straight to 262144 would
# cost. Not independently load-tested against this machine's ceiling
# under concurrent/heavier use -- if it proves insufficient, that's
# the next thing to measure.
NUM_CTX = 16384


def generate_response(prompt: str, model: str = FAST_MODEL, history=None, memory=None, think: bool = False, images=None):
    full_prompt = ""

    # -------- SYSTEM INSTRUCTIONS --------
    full_prompt += (
        "You are Aether, a highly intelligent AI assistant.\n"
        "Follow these rules strictly:\n"
        "1. Remember important user information.\n"
        "2. Be consistent with previous conversations.\n"
        "3. Only use the stored context below if it is directly relevant "
        "to the question you are answering right now -- otherwise ignore "
        "it completely and just answer what was asked.\n\n"
    )

    # -------- MEMORY (Structured) --------
    # Real bug found live 2026-07-31 via llm_validate eval traffic (see
    # STATUS.md item 13): this used to be labeled "User profile:" with
    # the system instructions saying to "use stored user data when
    # relevant" -- accurate for rows from extract_memory_facts() (name,
    # stated preferences), but the *same* Memory table also holds
    # SaveMemoryStep's fixed-key skill artifacts (last_file_digest,
    # last_research -- see save_memory_step.py), which are not user
    # facts at all, just "whatever that skill last produced in this
    # project." Labeling everything "User profile" plus "use it when
    # relevant" told the model to actively work irrelevant prior skill
    # output into unrelated answers (asked about the boiling point of
    # water, got an unprompted tangent about an earlier file digest).
    # Relabeled + instructed above to ignore anything not relevant,
    # rather than treating every stored row as a fact to surface.
    #
    # This is a prompt-level mitigation, not a structural fix -- the
    # underlying mixing of "durable user facts" and "skill run
    # artifacts" in one table with no relevance filtering is a real
    # design gap, flagged in STATUS.md for whoever builds out a proper
    # Memory Service later, not resolved here.
    if memory:
        full_prompt += (
            "Stored context (facts and prior results from this project -- "
            "may or may not be about the user, and may not be relevant to "
            "the current question):\n"
        )

        grouped = {}
        for key, value in memory:
            grouped.setdefault(key, []).append(value)

        for key, values in grouped.items():
            full_prompt += f"{key}: {', '.join(values)}\n"

        full_prompt += "\n"

    # -------- CHAT HISTORY --------
    if history:
        full_prompt += "Recent conversation:\n"
        for p, r in history:
            full_prompt += f"User: {p}\nAI: {r}\n"
        full_prompt += "\n"

    # -------- CURRENT PROMPT --------
    full_prompt += f"User: {prompt}\nAI:"

    # -------- CALL OLLAMA --------
    try:
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "think": think,
            "options": {"num_ctx": NUM_CTX},
        }
        # Added 2026-08-02 for multi-modal support (see routing.py's
        # VISION_MODEL, main.py's ChatRequest.images) — Ollama's
        # /api/generate accepts a top-level "images" field: a list of
        # base64-encoded strings (no data:image/... prefix — main.py
        # strips that from what the frontend sends before this call).
        # Only included when actually present, since sending an empty
        # list to a non-vision model is a needless payload difference
        # from before this change for the vast majority of requests
        # that don't attach an image.
        if images:
            payload["images"] = images

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=IMAGE_REQUEST_TIMEOUT_SECONDS if images else REQUEST_TIMEOUT_SECONDS,
        )

        data = response.json()

        if "response" not in data:
            logger.warning("ollama_response_missing_field", model=model, data=data)
            return f"Error from {model}: {data}"

        # Defense-in-depth for the bug NUM_CTX above fixes: if a
        # request still exhausts the context window despite the larger
        # ceiling (e.g. a file near/at the 50k-char attachment budget
        # plus a long conversation history), don't let it silently
        # degrade to a truncated/empty response the way it did at the
        # 4096 default -- surface it as an explicit, visible error.
        if not data["response"].strip() and data.get("done_reason") == "length":
            logger.warning(
                "ollama_empty_response_context_exhausted",
                model=model,
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
                num_ctx=NUM_CTX,
            )
            return (
                f"{model} ran out of context window (limit: {NUM_CTX} tokens) before "
                "producing a response -- try a shorter message or fewer/smaller attachments."
            )

        return data["response"]

    except requests.exceptions.ConnectionError:
        logger.error("ollama_unreachable", model=model, url=OLLAMA_URL)
        return (
            f"Could not reach Ollama at {OLLAMA_URL}. "
            "Is `ollama serve` running?"
        )
    except requests.exceptions.Timeout:
        actual_timeout = IMAGE_REQUEST_TIMEOUT_SECONDS if images else REQUEST_TIMEOUT_SECONDS
        logger.error("ollama_timeout", model=model, timeout=actual_timeout)
        return f"Request to {model} timed out after {actual_timeout}s"
    except Exception as e:
        logger.error("ollama_request_failed", model=model, exc_info=True)
        return f"Request failed: {str(e)}"
