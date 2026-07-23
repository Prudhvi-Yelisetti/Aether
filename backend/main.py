import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from services.logging_config import configure_logging, get_logger
from services.reasoning_service import generate
from services.routing import select_model
from services.planning_service import plan, execute_plan
from services.decision_service import decide
from services.validation_service import validate_response_llm
from storage.project_store import (
    create_project,
    get_projects,
    add_chat,
    get_chat_history,
    get_memory,
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


class ProjectRequest(BaseModel):
    name: str


# -------------------- ROUTES --------------------

@app.get("/")
def home():
    return {"message": "Aether backend running 🚀"}


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
    model = select_model(prompt, mode)

    # -------- Fetch Context --------
    history = None
    memory = None

    if project_id:
        history = get_chat_history(project_id, chat_id)
        memory = get_memory(project_id)

    # -------- Planning (Tool / Skill / raw reasoning — see planning_service.py) --------
    the_plan = plan(prompt, project_id)

    # -------- Generate Response, with Validation + bounded Retry/Escalate --------
    # Phase E2 (validation_service.py) + E3 (decision_service.py): decide()
    # runs one attempt, validates it, retries once if the failure looks
    # transient, and escalates to a clear, honest message instead of ever
    # delivering an internal error string — the exact bug this closes is
    # documented in validation_service.py's module docstring.
    def _attempt() -> str:
        if the_plan.capability_type == "reasoning":
            return generate(prompt, model, history, memory)
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
    if request.llm_validate and decision.valid:
        llm_validation = validate_response_llm(prompt, response)
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
            save_memory(project_id, key, value)

    # -------- Store Chat --------
    if project_id:
        chat_data = {
            "prompt": prompt,
            "response": response,
            "model": model
        }
        add_chat(project_id, chat_id, chat_data)

    return {
        "mode": mode,
        "model_used": model,
        "chat_id": chat_id,
        "response": response
    }
