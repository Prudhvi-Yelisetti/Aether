import CapabilityTrace from "./CapabilityTrace";

export default function ChatWindow({
  messages,
  input,
  setInput,
  onSend,
  loading,
  currentProject,
  llmValidate,
  setLlmValidate,
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
                    llmValidation={msg.llmValidation}
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
            <div className="composer-actions">
              {/* llm_validate is opt-in and observability-only (see
                  validation_service.py's docstring, STATUS.md item 13) —
                  off by default since it's an extra LLM call on top of
                  generation, and hasn't been proven reliable enough to
                  run on every request yet. Exposed here 2026-07-31. */}
              <label className="toggle-validate" title="Ask a second LLM call to judge whether the response actually addresses the question. Extra latency; logged only, doesn't change what's delivered.">
                <input
                  type="checkbox"
                  checked={llmValidate}
                  onChange={(e) => setLlmValidate(e.target.checked)}
                />
                validate
              </label>
              <button className="composer-send" onClick={onSend} disabled={loading || !input.trim()}>
                {loading ? "..." : "Send"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
