from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from services.ollama_service import generate_response
from services.router import route_model
from storage.project_store import (
    create_project,
    get_projects,
    add_chat,
    project_exists,
    get_chat_history
)

app = FastAPI()


# -------------------- MODELS --------------------

class ChatRequest(BaseModel):
    prompt: str
    mode: str = "smart"   # fast | smart | powerful
    project_id: Optional[str] = None


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
    return {
        "project_id": project_id,
        "name": request.name
    }


@app.get("/projects")
def list_projects():
    return get_projects()


# -------- Chat Route (WITH MEMORY) --------

@app.post("/chat")
def chat(request: ChatRequest):
    prompt = request.prompt
    mode = request.mode
    project_id = request.project_id

    # -------- Model Selection --------
    if mode == "fast":
        model = "mistral"
    elif mode == "powerful":
        model = "llama3"
    else:
        model = route_model(prompt)

    # -------- Validate Project --------
    if project_id and not project_exists(project_id):
        return {"error": f"Project {project_id} does not exist"}

    # -------- Fetch History --------
    history = None
    if project_id:
        history = get_chat_history(project_id)

    # -------- Generate Response --------
    response = generate_response(prompt, model, history)

    # -------- Store Chat --------
    chat_data = {
        "prompt": prompt,
        "response": response,
        "model": model
    }

    if project_id:
        add_chat(project_id, chat_data)

    return {
        "mode": mode,
        "model_used": model,
        "response": response
    }