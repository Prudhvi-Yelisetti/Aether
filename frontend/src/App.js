import { useState, useEffect } from "react";

function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const [projects, setProjects] = useState({});
  const [currentProject, setCurrentProject] = useState(null);

  const [chatList, setChatList] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);

  // -------- Fetch Projects --------
  const fetchProjects = async () => {
    const res = await fetch("http://127.0.0.1:8000/projects");
    const data = await res.json();
    setProjects(data);
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // -------- Create Project --------
  const createProject = async () => {
    const name = window.prompt("Enter project name:");
    if (!name) return;

    const res = await fetch("http://127.0.0.1:8000/project", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ name })
    });

    const data = await res.json();

    if (data.error) {
      alert(data.error);
      return;
    }

    fetchProjects();
  };

  // -------- Load Project --------
  const loadProject = async (projectId) => {
    setCurrentProject(projectId);

    const res = await fetch(`http://127.0.0.1:8000/project/${projectId}/chats`);
    const data = await res.json();

    const chatIds = Object.keys(data);

    setChatList(chatIds);
    setCurrentChat(chatIds[0] || null);

    if (chatIds.length > 0) {
      loadChat(projectId, chatIds[0]);
    } else {
      setMessages([]);
    }
  };

  // -------- Load Chat --------
  const loadChat = async (projectId, chatId) => {
    setCurrentChat(chatId);

    const res = await fetch(`http://127.0.0.1:8000/project/${projectId}/chats`);
    const data = await res.json();

    const chatData = data[chatId] || [];

    const formatted = [];

    chatData.forEach(msg => {
      formatted.push({ role: "user", text: msg.prompt });
      formatted.push({ role: "ai", text: msg.response });
    });

    setMessages(formatted);
  };

  // -------- Send Message --------
  const sendMessage = async () => {
    if (!input.trim() || loading || !currentProject) return;

    setLoading(true);

    const userMessage = { role: "user", text: input };
    setMessages(prev => [...prev, userMessage]);

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          prompt: input,
          mode: "smart",
          project_id: currentProject,
          chat_id: currentChat
        })
      });

      const data = await res.json();

      // If new chat, register it
      if (!currentChat && data.chat_id) {
        setCurrentChat(data.chat_id);
        setChatList(prev => [...prev, data.chat_id]);
      }

      setMessages(prev => [
        ...prev,
        { role: "ai", text: data.response || data.error || "No response" }
      ]);

    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Error: Unable to fetch response" }
      ]);
    }

    setInput("");
    setLoading(false);
  };

  return (
    <div style={{ display: "flex", height: "100vh" }}>

      {/* -------- Sidebar -------- */}
      <div style={{
        width: "260px",
        borderRight: "1px solid #ccc",
        padding: "10px"
      }}>
        <h3>Projects</h3>

        <button onClick={createProject}>+ New Project</button>

        {Object.entries(projects).map(([id, proj]) => (
          <div key={id} style={{ marginTop: "10px" }}>

            {/* Project */}
            <div
              onClick={() => loadProject(id)}
              style={{
                padding: "8px",
                cursor: "pointer",
                fontWeight: "bold",
                backgroundColor: currentProject === id ? "#ddd" : "transparent"
              }}
            >
              📁 {proj.name}
            </div>

            {/* Chats under project */}
            {currentProject === id && (
              <div style={{ marginLeft: "10px" }}>

                <button
                  onClick={() => {
                    setCurrentChat(null);
                    setMessages([]);
                  }}
                >
                  + New Chat
                </button>

                {chatList.map(chatId => (
                  <div
                    key={chatId}
                    onClick={() => loadChat(id, chatId)}
                    style={{
                      padding: "5px",
                      cursor: "pointer",
                      backgroundColor: currentChat === chatId ? "#bbb" : "transparent"
                    }}
                  >
                    💬 Chat {chatId}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* -------- Chat Area -------- */}
      <div style={{ flex: 1, padding: "20px", maxWidth: "800px", margin: "auto" }}>
        <h1>Aether</h1>

        {!currentProject && (
          <p style={{ color: "gray" }}>
            Select or create a project to start chatting
          </p>
        )}

        {/* Messages */}
        <div style={{
          border: "1px solid #ccc",
          height: "400px",
          overflowY: "auto",
          padding: "10px",
          marginBottom: "10px"
        }}>
          {messages.map((msg, index) => (
            <div
              key={index}
              style={{
                textAlign: msg.role === "user" ? "right" : "left",
                margin: "10px 0"
              }}
            >
              <span style={{
                display: "inline-block",
                padding: "10px",
                borderRadius: "10px",
                backgroundColor: msg.role === "user" ? "#007bff" : "#e5e5ea",
                color: msg.role === "user" ? "white" : "black"
              }}>
                {msg.text}
              </span>
            </div>
          ))}
        </div>

        {/* Input */}
        <textarea
          rows="3"
          style={{ width: "100%" }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || !currentProject}
        />

        <br /><br />

        <button onClick={sendMessage} disabled={loading || !currentProject}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </div>

    </div>
  );
}

export default App;