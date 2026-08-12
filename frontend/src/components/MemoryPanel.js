import { useEffect, useState } from "react";
import { fetchProjectMemory } from "../api";

// Shows exactly what GET /project/{id}/memory returns. Restructured
// 2026-08-10 (a91c3d5e7f02's structural memory fix — see
// storage/project_store.py's module comment for the full rationale)
// from one flat list into the two kinds of memory the backend now
// actually distinguishes:
//   - semantic: durable facts about the user, always included in
//     every reasoning-path prompt. May carry a `provenance` string if
//     Aether wrote it itself via memory consolidation (see
//     services/consolidation_service.py) rather than a direct
//     statement — shown as a badge below, not hidden, since a
//     consolidated fact deserves a visibly different trust level than
//     one the user stated directly.
//   - episodic: specific past skill-run results, only injected into a
//     prompt when they're similar to it by embedding cosine similarity
//     (get_relevant_episodic_memory(), upgraded from keyword overlap
//     in STATUS.md item 21) — up to 3 kept per key, oldest pruned
//     automatically.
// The old single-list version (2026-07-31, STATUS.md item 13) existed
// so a person could see the same thing the model sees; this keeps
// that goal but reflects what's actually true now instead of a single
// undifferentiated dump with a caveat that everything might be
// ignored.
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

  const semantic = memory ? memory.filter((r) => r.memory_type !== "episodic") : null;
  const episodic = memory ? memory.filter((r) => r.memory_type === "episodic") : null;

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2>Memory</h2>
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {error && <p className="panel-error">{error}</p>}

        {memory && memory.length === 0 && (
          <p className="capability-section-note">Nothing stored yet.</p>
        )}

        {semantic && semantic.length > 0 && (
          <>
            <h3 className="memory-section-heading">What Aether knows about you</h3>
            <p className="capability-section-note">
              Durable facts — included in every reasoning prompt for this project.
            </p>
            <div className="capability-section">
              {semantic.map((row) => (
                <div className="capability-item" key={row.key}>
                  <span className="capability-item-name">{row.key}</span>
                  <span className="capability-item-desc memory-value">{row.value}</span>
                  {row.provenance && (
                    <span className="memory-provenance-badge" title={row.provenance}>
                      🤖 consolidated by Aether
                    </span>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {episodic && episodic.length > 0 && (
          <>
            <h3 className="memory-section-heading">Recent skill results</h3>
            <p className="capability-section-note">
              Up to 3 kept per type, oldest dropped automatically. Only pulled
              into a prompt when it's relevant to what you're asking — most
              won't show up in most conversations.
            </p>
            <div className="capability-section">
              {episodic.map((row, i) => (
                <div className="capability-item" key={`${row.key}-${i}`}>
                  <span className="capability-item-name">{row.key}</span>
                  <span className="capability-item-desc memory-value">{row.value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
