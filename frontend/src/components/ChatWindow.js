import CapabilityTrace from "./CapabilityTrace";

export default function ChatWindow({
  messages,
  input,
  setInput,
  onSend,
  loading,
  currentProject,
}) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="chat-area">
      {!currentProject && (
        <div className="empty-state">
          <p className="empty-state-title">Select or create a project</p>
          <p className="empty-state-body">
            Aether keeps memory and chat history scoped per project.
          </p>
        </div>
      )}

      {currentProject && (
        <>
          <div className="message-list">
            {messages.length === 0 && (
              <div className="empty-state">
                <p className="empty-state-body">
                  Ask something — Aether will plan, pick a Tool or Skill (or
                  reason directly), validate the result, and show you which.
                </p>
              </div>
            )}
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`message-row ${msg.role === "user" ? "message-row-user" : "message-row-ai"}`}
              >
                <div className={`message-bubble ${msg.role === "user" ? "bubble-user" : "bubble-ai"}`}>
                  {msg.text}
                </div>
                {msg.role === "ai" && msg.capabilityType && (
                  <CapabilityTrace
                    capabilityType={msg.capabilityType}
                    capabilityName={msg.capabilityName}
                    capabilitySource={msg.capabilitySource}
                    model={msg.model}
                    attempts={msg.attempts}
                    escalated={msg.escalated}
                  />
                )}
              </div>
            ))}
            {loading && (
              <div className="message-row message-row-ai">
                <div className="message-bubble bubble-ai bubble-pending">
                  <span className="pending-dot" />
                  <span className="pending-dot" />
                  <span className="pending-dot" />
                </div>
              </div>
            )}
          </div>

          <div className="composer">
            <textarea
              className="composer-input"
              rows="2"
              placeholder="Message Aether..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button className="composer-send" onClick={onSend} disabled={loading || !input.trim()}>
              {loading ? "..." : "Send"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
