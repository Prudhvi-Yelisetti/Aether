import { useEffect, useState } from "react";
import { fetchProjectMemory } from "../api";

// Shows exactly what GET /project/{id}/memory returns — the same rows
// ollama_service.py injects into every reasoning-path prompt for this
// project (see its "Stored context" section). Added 2026-07-31 so the
// memory bleed-through fix earlier this session (STATUS.md item 13) is
// something a person can actually see, not just a backend log line —
// and so it's obvious when a project's memory holds a prior skill
// artifact (last_file_digest, last_research) rather than a fact someone
// stated, which is exactly the distinction that bug was about.
export default function MemoryPanel({ projectId, onClose }) {
  const [memory, setMemory] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchProjectMemory(projectId)
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setMemory(data.memory || []);
        }
      })
      .catch(() => setError("Couldn't reach the backend."));
  }, [projectId]);

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2>Memory</h2>
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <p className="capability-section-note">
          What's stored for this project and included in every reasoning
          prompt below the current question — the model is told to ignore
          anything here that isn't directly relevant.
        </p>

        {error && <p className="panel-error">{error}</p>}

        {memory && memory.length === 0 && (
          <p className="capability-section-note">Nothing stored yet.</p>
        )}

        {memory && memory.length > 0 && (
          <div className="capability-section">
            {memory.map((row) => (
              <div className="capability-item" key={row.key}>
                <span className="capability-item-name">{row.key}</span>
                <span className="capability-item-desc memory-value">{row.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
