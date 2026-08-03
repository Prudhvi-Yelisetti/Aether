// Centralized backend calls. API_URL is configurable via
// REACT_APP_API_URL (see run.sh / README "Running locally") so a local
// port conflict or a deployed backend doesn't require a source edit —
// defaults to the original hardcoded value for normal single-project use.
const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

export async function fetchProjects() {
  const res = await fetch(`${API_URL}/projects`);
  return res.json();
}

export async function createProject(name) {
  const res = await fetch(`${API_URL}/project`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function fetchProjectChats(projectId) {
  const res = await fetch(`${API_URL}/project/${projectId}/chats`);
  return res.json();
}

export async function fetchProjectMemory(projectId) {
  const res = await fetch(`${API_URL}/project/${projectId}/memory`);
  return res.json();
}

export async function fetchCapabilities() {
  const res = await fetch(`${API_URL}/capabilities`);
  return res.json();
}

export async function fetchModels() {
  const res = await fetch(`${API_URL}/models`);
  return res.json();
}

export async function sendChatMessage({ prompt, mode, projectId, chatId, llmValidate, model, images }) {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      mode: mode || "smart",
      project_id: projectId,
      chat_id: chatId,
      llm_validate: !!llmValidate,
      // model: undefined/null means "let the backend auto-route", same
      // as before this existed — only sent when the person picked one
      // in Settings. images: base64 strings, no data:image/... prefix
      // (stripped client-side, see ChatWindow.js) — see main.py's
      // ChatRequest for why an attached image overrides model anyway.
      model: model || null,
      images: images && images.length ? images : null,
    }),
  });
  return res.json();
}
