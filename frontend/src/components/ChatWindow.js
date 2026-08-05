import { useRef, useState } from "react";
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
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  // Counts nested dragenter/dragleave pairs across the drop zone's own
  // children — a plain boolean flickers false the instant the pointer
  // crosses a child element's edge, since dragleave fires on the child
  // before dragenter fires on the parent again.
  const dragDepth = useRef(0);

  // Real bug found live 2026-08-05 (see STATUS.md): a genuine ~2MB
  // photo consistently timed out on the backend, even after raising
  // its timeout (IMAGE_REQUEST_TIMEOUT_SECONDS in ollama_service.py) —
  // vision inference on a full-resolution image is just slow, and a
  // longer timeout alone doesn't make it a good experience. Most of
  // that resolution isn't needed to read text/colors/objects in an
  // image anyway, so it's downscaled client-side before it ever
  // becomes a data URL. 1280px on the longest side and JPEG quality
  // 0.85 are a starting guess, not measured against a quality
  // threshold — revisit if responses start missing fine detail.
  const MAX_DIMENSION = 1280;
  const JPEG_QUALITY = 0.85;

  const downscaleImage = (file) =>
    new Promise((resolve, reject) => {
      const img = new Image();
      const objectUrl = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(objectUrl);
        const scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height));
        // Already small enough — skip re-encoding entirely rather than
        // lose quality (or transparency, PNG->JPEG) for no size benefit.
        if (scale >= 1) {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(file);
          return;
        }
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", JPEG_QUALITY));
      };
      img.onerror = reject;
      img.src = objectUrl;
    });

  // Added 2026-08-02 for multi-modal support (see main.py's
  // ChatRequest.images). Stores full data:image/...;base64,xxx URLs
  // client-side — that's what an <img> tag needs to preview/render
  // them directly. App.js's sendMessage() strips the data-URL prefix
  // before sending to the backend, which only wants the raw base64.
  // Shared by both the file-picker input and drag-and-drop below.
  const addFiles = (fileList) => {
    Array.from(fileList || [])
      .filter((file) => file.type.startsWith("image/"))
      .forEach((file) => {
        downscaleImage(file)
          .then((dataUrl) => {
            setPendingImages((prev) => [...prev, { name: file.name, dataUrl }]);
          })
          .catch(() => {
            // Downscaling failed (corrupt file, unsupported format for
            // canvas decode, etc.) — fall back to the original bytes
            // rather than silently dropping the attachment.
            const reader = new FileReader();
            reader.onload = () => {
              setPendingImages((prev) => [...prev, { name: file.name, dataUrl: reader.result }]);
            };
            reader.readAsDataURL(file);
          });
      });
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleFilesSelected = (e) => {
    addFiles(e.target.files);
    e.target.value = ""; // allow re-selecting the same file
  };

  const removePendingImage = (index) => {
    setPendingImages((prev) => prev.filter((_, i) => i !== index));
  };

  // Drag-and-drop, added 2026-08-03 after Prudhvi hit a stale Chrome
  // file-picker cache (real ~/Downloads has 100+ files including many
  // images; the GTK dialog showed 6 unrelated files, all from months
  // earlier) — not an Aether bug, but drag-and-drop sidesteps that
  // native picker entirely, and is worth having regardless.
  const handleDragEnter = (e) => {
    e.preventDefault();
    dragDepth.current += 1;
    setIsDraggingFile(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault(); // required for onDrop to fire at all
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setIsDraggingFile(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    dragDepth.current = 0;
    setIsDraggingFile(false);
    addFiles(e.dataTransfer.files);
  };

  return (
    <div
      className={`chat-area ${isDraggingFile ? "chat-area-drag-active" : ""}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDraggingFile && (
        <div className="drop-overlay">
          <p>Drop image to attach</p>
        </div>
      )}
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
