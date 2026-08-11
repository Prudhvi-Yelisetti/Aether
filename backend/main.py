import base64
import time
import uuid

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from services.document_extraction import extract_document_text, MAX_OCR_PAGES
from services.logging_config import configure_logging, get_logger
from services.reasoning_service import generate
from services.routing import select_model, VISION_MODEL
from services.planning_service import plan, execute_plan, Plan
from services.decision_service import decide
from services.validation_service import validate_response_llm
from services.tools.registry import registry as tool_registry
from services.skills.registry import registry as skill_registry
from storage.project_store import (
    create_project,
    get_projects,
    add_chat,
    get_chat_history,
    get_memory,
    get_relevant_episodic_memory,
    save_memory,
    project_exists,
    create_chat,
    get_project_full_data
)
from services.memory_extraction import extract_memory_facts
from storage.experience_store import log_experience

configure_logging()
logger = get_logger("aether.main")

app = FastAPI()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Every request gets a short request_id, bound into structlog's
    contextvars so every log line emitted while handling it — from any
    module — is automatically tagged. This is what makes it possible to
    trace one /chat call across planning, skill/tool execution, and storage."""
    import structlog

    request_id = str(uuid.uuid4())[:8]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.monotonic()
    logger.info("request_started", path=request.url.path, method=request.method)

    try:
        response = await call_next(request)
    except Exception:
        logger.error("request_failed", path=request.url.path, exc_info=True)
        raise

    duration_ms = round((time.monotonic() - start) * 1000, 1)
    logger.info(
        "request_finished",
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response

# -------- CORS --------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- MODELS --------------------

class FileAttachment(BaseModel):
    name: str
    content: str
    # Added 2026-08-06 for PDF/DOCX support (see
    # services/document_extraction.py). "text" (default) means content
    # is already plain text, extracted client-side (.txt/.md/.csv/etc,
    # see ChatWindow.js) — unchanged from before this field existed.
    # "base64" means content is the raw file bytes, base64-encoded, and
    # needs server-side extraction (PDF/DOCX can't be parsed into text
    # by just decoding UTF-8 the way a .txt file can).
    encoding: str = "text"


class ChatRequest(BaseModel):
    prompt: str
    mode: str = "smart"
    project_id: Optional[str] = None
    chat_id: Optional[int] = None
    # E2's LLM-based check (validation_service.validate_response_llm) —
    # opt-in and observability-only for this first pass, see that
    # function's docstring for why. Off by default: it's an extra LLM
    # call on top of the request's own generation, so it's not free, and
    # it hasn't been proven reliable enough to run on every request yet.
    llm_validate: bool = False
    # Added 2026-08-02 for the Settings panel's model override. None
    # (the default) means "auto-route via select_model(), same as
    # always" — this only takes over model choice when the person
    # explicitly picked one. Ignored outright if images is set (see
    # below): an attached image forces VISION_MODEL regardless, since
    # that's the only installed model that can actually see it.
    model: Optional[str] = None
    # Added 2026-08-02 for multi-modal support. List of base64-encoded
    # image strings — no data:image/...;base64, prefix; the frontend
    # strips that before sending (see api.js). When present, this
    # request skips Tool/Skill planning entirely and goes straight to
    # reasoning on VISION_MODEL — none of the current Tools/Skills know
    # what to do with an image, so routing one into, say,
    # calculate_and_explain would be nonsensical.
    images: Optional[List[str]] = None
    # Added 2026-08-06 after Prudhvi found the composer only accepted
    # images: plain-text document attachments (.txt/.md/.csv/.json/.log
    # etc.) — extracted to text client-side (FileReader.readAsText(),
    # see ChatWindow.js), no server-side parsing needed since it's
    # already plain text by the time it gets here. PDF/DOCX would need
    # a real extraction library and is deliberately out of scope for
    # this pass — see STATUS.md for why. Like images, this skips
    # Tool/Skill planning (none of them know what to do with inline
    # file content either) but does NOT force a model override the way
    # images force VISION_MODEL — any model can read text.
    files: Optional[List[FileAttachment]] = None



class ProjectRequest(BaseModel):
    name: str


# -------------------- ROUTES --------------------

@app.get("/")
def home():
    return {"message": "Aether backend running 🚀"}


@app.get("/capabilities")
def list_capabilities():
    """What Aether can actually do right now, straight from the same
    registries the Planner itself queries (services/tools/registry.py,
    services/skills/registry.py) — not a hand-maintained list that can
    drift from what's really registered."""
    return {
        "tools": tool_registry.describe_all(),
        "skills": skill_registry.describe_all(),
    }


@app.get("/models")
def list_models():
    """Installed Ollama models, straight from Ollama itself (not a
    hand-maintained list) — added 2026-08-02 for the Settings panel's
    model override. Same live-queried-not-hardcoded principle as
    /capabilities above. "vision" in a model's capabilities is what
    ChatRequest.images actually checks against at request time — this
    endpoint just surfaces that so the frontend can show it, e.g. to
    grey out or label non-vision models when an image is attached."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return {
            "models": [
                {
                    "name": m.get("name"),
                    "capabilities": m.get("capabilities", []),
                }
                for m in models
            ]
        }
    except requests.exceptions.RequestException:
        logger.warning("models_unreachable")
        return {"models": [], "error": "Could not reach Ollama."}


# -------- Project Routes --------

@app.post("/project")
def create_new_project(request: ProjectRequest):
    project_id = create_project(request.name)

    if not project_id:
        return {"error": "Project name already exists"}

    return {
        "project_id": project_id,
        "name": request.name
    }


@app.get("/projects")
def list_projects():
    return get_projects()


@app.get("/project/{project_id}/chats")
def get_project_chats_api(project_id: str):
    if not project_exists(project_id):
        return {"error": "Project not found"}

    return get_project_full_data(project_id)


@app.get("/project/{project_id}/memory")
def get_project_memory_api(project_id: str):
    """Everything stored for this project, both types. Semantic rows are
    injected into every reasoning-path prompt; episodic rows only when
    they match the current prompt by keyword overlap (see
    get_relevant_episodic_memory() in storage/project_store.py and
    ollama_service.py's "Stored context" section) — added 2026-07-31
    alongside the fix for memory bleeding into unrelated answers
    (STATUS.md item 13), extended in a91c3d5e7f02 to actually separate
    the two kinds of memory instead of just relabeling them, so the
    person using the UI can see the real distinction, not an invisible
    backend detail."""
    if not project_exists(project_id):
        return {"error": "Project not found"}

    return {"memory": [{"key": k, "value": v, "memory_type": t, "provenance": p} for k, v, t, p in get_memory(project_id)]}


# -------- Chat Route --------

@app.post("/chat")
def chat(request: ChatRequest):
    import structlog

    prompt = request.prompt
    mode = request.mode
    project_id = request.project_id
    chat_id = request.chat_id
    request_id = structlog.contextvars.get_contextvars().get("request_id")

    # -------- Validate Project --------
    if project_id and not project_exists(project_id):
        return {"error": f"Project {project_id} does not exist"}

    # -------- Create Chat if needed --------
    if project_id and not chat_id:
        chat_id = create_chat(project_id)

    # -------- Model Selection (Reasoning Service's concern, see routing.py) --------
    # Added 2026-08-02: an explicit request.model overrides auto-routing
    # (the Settings panel's model dropdown) — but an attached image wins
    # over even that override, since VISION_MODEL is the only installed
    # model that can actually see it. Silently forcing the model here
    # (rather than erroring on an incompatible model + image combo) is
    # deliberate: the person just wants their image looked at, not a
    # 400 explaining why their code-model pick doesn't have eyes.
    if request.images:
        model = VISION_MODEL
    elif request.model:
        model = request.model
    else:
        model = select_model(prompt, mode)

    # -------- File Attachments (text content, see FileAttachment above) --------
    # Added 2026-08-06. Builds a separate augmented_prompt rather than
    # mutating `prompt` itself — `prompt` stays exactly what the person
    # typed for chat storage/display (see add_chat() below); dumping the
    # full file content into the stored prompt would bloat every
    # history fetch and show the raw file text in the chat bubble
    # instead of what was actually typed. Capped at ~50k chars total
    # across all files, a guess at "enough for a real document without
    # blowing up a small model's context window" — not measured against
    # an actual context-length failure yet.
    #
    # encoding="base64" (PDF/DOCX, added 2026-08-06) needs server-side
    # extraction first — see services/document_extraction.py for why
    # that's libraries-first with vision-model OCR only as a fallback
    # for scanned PDFs, not a bundled OCR engine. Extraction failure
    # (corrupt file, password-protected PDF, etc.) becomes an inline
    # note in the prompt, not a 500 — the request should still get a
    # response, just one that's honest about the one file it couldn't
    # read.
    MAX_FILE_CONTEXT_CHARS = 50_000
    augmented_prompt = prompt
    # Surfaced 2026-08-09: both truncation paths below (context budget,
    # OCR page cap) already leave an inline note in the text sent to the
    # model, but that's invisible to the person attaching the file —
    # they'd only see it if the model happened to mention it back. This
    # collects the same events as short, human-readable strings and
    # returns them separately (see `attachment_notices` in the response
    # dict below) so the frontend can show a real UI indicator instead.
    attachment_notices: List[str] = []
    if request.files:
        parts = []
        budget = MAX_FILE_CONTEXT_CHARS
        for f in request.files:
            if budget <= 0:
                attachment_notices.append(
                    f"{f.name}: not included — the {MAX_FILE_CONTEXT_CHARS:,}-char attachment budget "
                    f"was already used up by earlier files"
                )
                continue

            if f.encoding == "base64":
                try:
                    raw_bytes = base64.b64decode(f.content)
                    extracted = extract_document_text(f.name, raw_bytes)
                except Exception as e:
                    logger.warning("document_extraction_failed", filename=f.name, error=str(e))
                    extracted = f"[Could not extract text from this file: {e}]"
            else:
                extracted = f.content

            # This substring is exactly what document_extraction.py's
            # OCR fallback inserts when a scanned PDF exceeds
            # MAX_OCR_PAGES — checked here rather than changing that
            # function's return type, since main.py is the one place
            # that needs to turn it into a UI-facing signal.
            if "more page(s) not transcribed" in extracted:
                attachment_notices.append(
                    f"{f.name}: scanned-PDF OCR is capped at {MAX_OCR_PAGES} pages — later pages weren't transcribed"
                )

            content = extracted[:budget]
            if len(extracted) > budget:
                content += "\n[...truncated, file continues...]"
                attachment_notices.append(
                    f"{f.name}: truncated to fit the {MAX_FILE_CONTEXT_CHARS:,}-char attachment budget"
                )
            parts.append(f"--- Attached file: {f.name} ---\n{content}")
            budget -= len(content)
        augmented_prompt = "\n\n".join(parts) + f"\n\n---\n\n{prompt}"

    # -------- Fetch Context --------
    history = None
    semantic_memory = None
    episodic_memory = None

    if project_id:
        history = get_chat_history(project_id, chat_id)
        # Semantic: always fetched in full (small, durable, always
        # relevant — the way you don't need a specific cue to recall
        # your own name). Episodic: cue-filtered by keyword overlap
        # with the actual prompt, not the augmented one (still just the
        # user's words, not file-attachment text/system framing) — see
        # get_relevant_episodic_memory()'s docstring and a91c3d5e7f02.
        semantic_memory = get_memory(project_id, memory_type="semantic")
        episodic_memory = get_relevant_episodic_memory(project_id, prompt)

    # -------- Planning (Tool / Skill / raw reasoning — see planning_service.py) --------
    # An attached image or file skips planning entirely, added
    # 2026-08-02 (images) / 2026-08-06 (files): none of the current
    # Tools/Skills know what to do with image bytes or inline file
    # content, so letting the LLM planner route an attachment-bearing
    # prompt into, say, calculate_and_explain would be nonsensical
    # rather than just wrong. Same shape as plan()'s own rule-based
    # short-circuits (e.g. is_simple_math) — Plan(capability_type=
    # "reasoning", ...) is exactly what a plain reasoning-path response
    # already looks like. Planning still runs on the original `prompt`,
    # not augmented_prompt, in the one case it does run (neither
    # attached) — moot otherwise since planning is skipped whenever
    # augmented_prompt would differ from prompt.
    if request.images or request.files:
        the_plan = Plan(capability_type="reasoning", capability_name=None, source="rule")
    else:
        the_plan = plan(prompt, project_id)

    # -------- Generate Response, with Validation + bounded Retry/Escalate --------
    # Phase E2 (validation_service.py) + E3 (decision_service.py): decide()
    # runs one attempt, validates it, retries once if the failure looks
    # transient, and escalates to a clear, honest message instead of ever
    # delivering an internal error string — the exact bug this closes is
    # documented in validation_service.py's module docstring.
    def _attempt() -> str:
        if the_plan.capability_type == "reasoning":
            return generate(augmented_prompt, model, history, semantic_memory, episodic_memory, images=request.images)
        return execute_plan(the_plan, prompt, request_id=request_id)

    start = time.monotonic()
    decision = decide(_attempt)
    latency_ms = round((time.monotonic() - start) * 1000, 1)
    response = decision.response

    # -------- Experience Log (see ARCHITECTURE.md's Experience Service) --------
    log_experience(
        project_id=project_id,
        request_id=request_id,
        prompt=prompt,
        tool=the_plan.capability_name,
        tool_source=the_plan.source,
        model=model,
        success=decision.valid,
        latency_ms=latency_ms,
    )

    # -------- LLM-based Validation (Phase E2, second check — opt-in, --------
    # -------- observability-only, see validation_service.py) -----------
    # Only worth asking an LLM to judge a response the deterministic check
    # already accepted — no point double-checking something already known
    # to be a failure string. Logged only; does not change what's
    # delivered or retried this pass — see validate_response_llm()'s
    # docstring for why that's deliberate right now.
    #
    # llm_validation_verdict is now also stored (see 44f9e98b07f2) and
    # returned in the response below — until 2026-07-31 this was
    # computed and logged, then thrown away, so the UI had no way to
    # show it even though the whole point of the eval session that found
    # this (STATUS.md item 13) was to make llm_validate's output visible.
    llm_validation_verdict = None
    if request.llm_validate and decision.valid:
        llm_validation = validate_response_llm(prompt, response)
        llm_validation_verdict = "valid" if llm_validation.valid else "flagged"
        if llm_validation.valid:
            logger.info("llm_validation_result", reason=llm_validation.reason)
        else:
            logger.warning(
                "llm_validation_flagged",
                reason=llm_validation.reason,
                capability_type=the_plan.capability_type,
                capability_name=the_plan.capability_name,
            )

    # -------- Memory Extraction (LLM-based, upserted — see memory_extraction.py) --------
    if project_id:
        facts = extract_memory_facts(prompt)

        for key, value in facts.items():
            save_memory(project_id, key, value, memory_type="semantic")

    # -------- Store Chat --------
    if project_id:
        chat_data = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "capability_type": the_plan.capability_type,
            "capability_name": the_plan.capability_name,
            "capability_source": the_plan.source,
            "attempts": decision.attempts,
            "escalated": decision.escalated,
            "llm_validation": llm_validation_verdict,
        }
        add_chat(project_id, chat_id, chat_data)

    return {
        "mode": mode,
        "model_used": model,
        "chat_id": chat_id,
        "response": response,
        # Exposed 2026-07-26: main.py always computed all of this
        # (the_plan, decision) but never returned it — the frontend had
        # no way to show which capability actually handled a request,
        # even though the Planner/Validator/Decision layers (E1-E3) are
        # the whole point of this project. See STATUS.md.
        "capability_type": the_plan.capability_type,
        "capability_name": the_plan.capability_name,
        "capability_source": the_plan.source,
        "attempts": decision.attempts,
        "escalated": decision.escalated,
        # Exposed 2026-07-31 alongside llm_validation_verdict above.
        "llm_validation": llm_validation_verdict,
        # Exposed 2026-08-09: see attachment_notices' comment above —
        # not persisted to chat_data/add_chat (history rows predating
        # this change have no equivalent), so only live in the response
        # of the request that triggered them, same as llm_validation
        # was before 44f9e98b07f2 added storage for it.
        "attachment_notices": attachment_notices,
    }
