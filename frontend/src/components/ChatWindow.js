import { useRef } from "react";
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
  pendingImages,
  setPendingImages,
}) {
  const fileInputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  // Added 2026-08-02 for multi-modal support (see main.py's
  // ChatRequest.images). Stores full data:image/...;base64,xxx URLs
  // client-side — that's what an <img> tag needs to preview/render
  // them directly. App.js's sendMessage() strips the data-URL prefix
  // before sending to the backend, which only wants the raw base64.
  const handleFilesSelected = (e) => {
    const files = Array.from(e.target.files || []);
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        setPendingImages((prev) => [...prev, { name: file.name, dataUrl: reader.result }]);
      };
      reader.readAsDataURL(file);
    });
    e.target.value = ""; // allow re-selecting the same file
  };

  const removePendingImage = (index) => {
    setPendingImages((prev) => prev.filter((_, i) => i !== index));
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
                  {msg.images && msg.images.length > 0 && (
                    <div className="message-images">
                      {msg.images.map((src, i) => (
                        <img key={i} src={src} alt="attached" className="message-image" />
                      ))}
                    </div>
                  )}
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
            <div className="composer-input-wrap">
              {pendingImages.length > 0 && (
                <div className="pending-images">
                  {pendingImages.map((img, i) => (
                    <div className="pending-image" key={i}>
                      <img src={img.dataUrl} alt={img.name} />
                      <button
                        className="pending-image-remove"
                        onClick={() => removePendingImage(i)}
                        aria-label={`Remove ${img.name}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <textarea
                className="composer-input"
                rows="2"
                placeholder="Message Aether..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
            </div>
            <div className="composer-actions">
              <input
                type="file"
                accept="image/*"
                multiple
                ref={fileInputRef}
                onChange={handleFilesSelected}
                style={{ display: "none" }}
              />
              {/* Attached images always route to the vision-capable
                  model server-side (see main.py) — this button doesn't
                  need to know or care which model that is. */}
              <button
                className="composer-attach"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                title="Attach an image"
                aria-label="Attach an image"
              >
                📎
              </button>
              {/* llm_validate is opt-in and observability-only (see
                  validation_service.py's docstring, STATUS.md item 13) —
                  off by default since it's an extra LLM call on top of
                  generation, and hasn't been proven reliable enough to
                  run on every request yet. Exposed here 2026-07-31;
                  default made configurable via Settings 2026-08-02. */}
              <label className="toggle-validate" title="Ask a second LLM call to judge whether the response actually addresses the question. Extra latency; logged only, doesn't change what's delivered.">
                <input
                  type="checkbox"
                  checked={llmValidate}
                  onChange={(e) => setLlmValidate(e.target.checked)}
                />
                validate
              </label>
              <button
                className="composer-send"
                onClick={onSend}
                disabled={loading || (!input.trim() && pendingImages.length === 0)}
              >
                {loading ? "..." : "Send"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
