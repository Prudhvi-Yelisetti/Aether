import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import CapabilitiesPanel from "./components/CapabilitiesPanel";
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

  const refreshProjects = async () => {
    setProjects(await fetchProjects());
  };

  useEffect(() => {
    refreshProjects();
  }, []);

  const handleCreateProject = async () => {
    const name = window.prompt("Project name:");
    if (!name) return;

    const data = await apiCreateProject(name);
    if (data.error) {
      alert(data.error);
      return;
    }
    refreshProjects();
  };

  const loadChat = async (projectId, chatId) => {
    setCurrentChat(chatId);
    const data = await fetchProjectChats(projectId);
    const chatData = data[chatId] || [];

    const formatted = [];
    chatData.forEach((msg) => {
      formatted.push({ role: "user", text: msg.prompt });
      formatted.push({ role: "ai", text: msg.response });
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
    if (!input.trim() || loading || !currentProject) return;

    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: input }]);
    const sentInput = input;
    setInput("");

    try {
      const data = await sendChatMessage({
        prompt: sentInput,
        mode: "smart",
        projectId: currentProject,
        chatId: currentChat,
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
        onCreateProject={handleCreateProject}
        chatList={chatList}
        currentChat={currentChat}
        onSelectChat={(id) => loadChat(currentProject, id)}
        onNewChat={handleNewChat}
        onOpenCapabilities={() => setShowCapabilities(true)}
      />

      <ChatWindow
        messages={messages}
        input={input}
        setInput={setInput}
        onSend={sendMessage}
        loading={loading}
        currentProject={currentProject}
      />

      {showCapabilities && (
        <CapabilitiesPanel onClose={() => setShowCapabilities(false)} />
      )}
    </div>
  );
}

export default App;
