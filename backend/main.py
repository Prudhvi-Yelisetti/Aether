import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from services.logging_config import configure_logging, get_logger
from services.ollama_service import generate_response
from services.router import route_model
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
from services.plugin_manager import ai_decide_plugin, decide_plugin, execute_plugin

configure_logging()
logger = get_logger("aether.main")

app = FastAPI()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Every request gets a short request_id, bound into structlog's
    contextvars so every log line emitted while handling it — from any
    module — is automatically tagged. This is what makes it possible to
    trace one /chat call across routing, plugin execution, and storage."""
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


class ProjectRequest(BaseModel):
    name: str


# -------------------- MEMORY EXTRACTION --------------------

def extract_memory(prompt: str):
    prompt_lower = prompt.lower()
    memory = []

    patterns = {
        "name": ["my name is", "i am called"],
        "preference": ["i like", "i love", "i prefer"],
        "skill": ["i know", "i am good at"],
        "goal": ["i want to", "i plan to"]
    }

    for key, keywords in patterns.items():
        for keyword in keywords:
            if keyword in prompt_lower:
                value = prompt_lower.split(keyword)[-1].strip()
                if value:
                    memory.append((key, value))

    return memory


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
    prompt = request.prompt
    mode = request.mode
    project_id = request.project_id
    chat_id = request.chat_id

    # -------- Validate Project --------
    if project_id and not project_exists(project_id):
        return {"error": f"Project {project_id} does not exist"}

    # -------- Create Chat if needed --------
    if project_id and not chat_id:
        chat_id = create_chat(project_id)

    # -------- Model Selection --------
    if mode == "fast":
        model = "mistral"
    elif mode == "powerful":
        model = "llama3"
    else:
        model = route_model(prompt)

    # -------- Fetch Context --------
    history = None
    memory = None

    if project_id:
        history = get_chat_history(project_id, chat_id)
        memory = get_memory(project_id)

    # -------- Generate Response --------
    # -------- Plugin Detection --------
    plugin = ai_decide_plugin(prompt)
    logger.info("chat_routed", model=model, plugin=plugin, project_id=project_id)

    if plugin:
        response = execute_plugin(plugin, prompt)
    else:
        response = generate_response(prompt, model, history, memory)

    # -------- Memory Extraction --------
    if project_id:
        extracted = extract_memory(prompt)

        for key, value in extracted:
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