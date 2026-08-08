import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import CapabilitiesPanel from "./components/CapabilitiesPanel";
import MemoryPanel from "./components/MemoryPanel";
import NewProjectModal from "./components/NewProjectModal";
import SettingsPanel from "./components/SettingsPanel";
import { loadSettings } from "./settings";
import {
  fetchProjects,
  createProject as apiCreateProject,
  fetchProjectChats,
  sendChatMessage,
} from "./api";
import "./App.css";

function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const [projects, setProjects] = useState({});
  const [currentProject, setCurrentProject] = useState(null);

  const [chatList, setChatList] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);

  const [showCapabilities, setShowCapabilities] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // settings.model/defaultValidate persist across reloads (settings.js,
  // localStorage) — llmValidate itself stays a live per-message toggle
  // from here on, just seeded from the persisted default on first load.
  const [settings, setSettings] = useState(loadSettings);
  const [llmValidate, setLlmValidate] = useState(() => loadSettings().defaultValidate);
  const [pendingImages, setPendingImages] = useState([]);
  const [pendingFiles, setPendingFiles] = useState([]);

  const refreshProjects = async () => {
    setProjects(await fetchProjects());
  };

  useEffect(() => {
    refreshProjects();
  }, []);

  // Returns the API result so NewProjectModal can show an inline error
  // (e.g. duplicate name) without closing — replaces the old
  // window.prompt() + alert() flow, see NewProjectModal.js.
  const handleCreateProject = async (name) => {
    const data = await apiCreateProject(name);
    if (!data.error) {
      refreshProjects();
    }
    return data;
  };

  const loadChat = async (projectId, chatId) => {
    setCurrentChat(chatId);
    const data = await fetchProjectChats(projectId);
    const chatData = data[chatId] || [];

    const formatted = [];
    chatData.forEach((msg) => {
      formatted.push({ role: "user", text: msg.prompt });
      // Historical capability trace — added 2026-07-31 (migration
      // 44f9e98b07f2). Rows written before that migration have these
      // as null, which CapabilityTrace already renders as "no trace,"
      // same as a fresh message with no capabilityType — no special
      // casing needed here for old vs. new rows.
      formatted.push({
        role: "ai",
        text: msg.response,
        model: msg.model || null,
        capabilityType: msg.capability_type || null,
        capabilityName: msg.capability_name || null,
        capabilitySource: msg.capability_source || null,
        attempts: msg.attempts || 1,
        escalated: !!msg.escalated,
        llmValidation: msg.llm_validation || null,
      });
    });
    setMessages(formatted);
  };

  const loadProject = async (projectId) => {
    setCurrentProject(projectId);

    const data = await fetchProjectChats(projectId);
    const chatIds = Object.keys(data);

    setChatList(chatIds);
    setCurrentChat(chatIds[0] || null);

    if (chatIds.length > 0) {
      loadChat(projectId, chatIds[0]);
    } else {
      setMessages([]);
    }
  };

  const handleNewChat = () => {
    setCurrentChat(null);
    setMessages([]);
  };

  const sendMessage = async () => {
    if (
      (!input.trim() && pendingImages.length === 0 && pendingFiles.length === 0) ||
      loading ||
      !currentProject
    )
      return;

    setLoading(true);
    const sentImages = pendingImages;
    const sentFiles = pendingFiles;
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: input,
        images: sentImages.map((img) => img.dataUrl),
        files: sentFiles.map((f) => ({ name: f.name })),
      },
    ]);
    const sentInput = input;
    setInput("");
    setPendingImages([]);
    setPendingFiles([]);

    try {
      const data = await sendChatMessage({
        prompt: sentInput,
        mode: "smart",
        projectId: currentProject,
        chatId: currentChat,
        llmValidate,
        model: settings.model,
        // Strip the data:image/...;base64, prefix — the backend (and
        // Ollama's API underneath it) wants raw base64 only. The full
        // data URL stays in the message above, since that's what the
        // <img> preview needs.
        images: sentImages.map((img) => img.dataUrl.split(",")[1]),
        // encoding: "base64" for PDF/DOCX (server-side extraction, see
        // main.py/document_extraction.py), "text" (the default the
        // backend assumes when omitted) for everything else — added
        // 2026-08-07, must be passed through here or a PDF/DOCX's raw
        // base64 bytes get treated as literal text server-side.
        files: sentFiles.map((f) => ({ name: f.name, content: f.content, encoding: f.encoding || "text" })),
      });

      if (!currentChat && data.chat_id) {
        setCurrentChat(data.chat_id);
        setChatList((prev) => [...prev, data.chat_id]);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          text: data.response || data.error || "No response",
          model: data.model_used || null,
          capabilityType: data.capability_type || null,
          capabilityName: data.capability_name || null,
          capabilitySource: data.capability_source || null,
          attempts: data.attempts || 1,
          escalated: !!data.escalated,
          llmValidation: data.llm_validation || null,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Error: couldn't reach the backend." },
      ]);
    }

    setLoading(false);
  };

  return (
    <div className="app-shell">
      <Sidebar
        projects={projects}
        currentProject={currentProject}
        onSelectProject={loadProject}
        onCreateProject={() => setShowNewProject(true)}
        chatList={chatList}
        currentChat={currentChat}
        onSelectChat={(id) => loadChat(currentProject, id)}
        onNewChat={handleNewChat}
        onOpenCapabilities={() => setShowCapabilities(true)}
        onOpenMemory={() => setShowMemory(true)}
        onOpenSettings={() => setShowSettings(true)}
      />

      <ChatWindow
        messages={messages}
        input={input}
        setInput={setInput}
        onSend={sendMessage}
        loading={loading}
        currentProject={currentProject}
        llmValidate={llmValidate}
        setLlmValidate={setLlmValidate}
        pendingImages={pendingImages}
        setPendingImages={setPendingImages}
        pendingFiles={pendingFiles}
        setPendingFiles={setPendingFiles}
      />

      {showCapabilities && (
        <CapabilitiesPanel onClose={() => setShowCapabilities(false)} />
      )}

      {showMemory && currentProject && (
        <MemoryPanel projectId={currentProject} onClose={() => setShowMemory(false)} />
      )}

      {showSettings && (
        <SettingsPanel
          onSettingsChange={setSettings}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showNewProject && (
        <NewProjectModal
          onCreate={handleCreateProject}
          onClose={() => setShowNewProject(false)}
        />
      )}
    </div>
  );
}

export default App;
