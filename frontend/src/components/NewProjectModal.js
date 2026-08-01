import { useState } from "react";

// Replaces window.prompt() (a native, unstyled browser dialog that
// couldn't show an inline error — a duplicate name just alert()'d
// separately, a jarring second popup on top of the first). Added
// 2026-07-31 as UI polish, per Prudhvi's direction — flagged as a known
// gap since the frontend rebuild (STATUS.md).
export default function NewProjectModal({ onCreate, onClose }) {
  const [name, setName] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    setError(null);

    const result = await onCreate(trimmed);
    if (result && result.error) {
      setError(result.error);
      setSubmitting(false);
      return;
    }

    // onClose is only reached on success — on error the modal stays
    // open with the message visible, so the person can just fix the
    // name and resubmit instead of the whole flow restarting.
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel panel-narrow" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2>New project</h2>
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <label className="field-label" htmlFor="new-project-name">
          Name
        </label>
        <input
          id="new-project-name"
          className="field-input"
          type="text"
          autoFocus
          placeholder="e.g. research-notes"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={submitting}
        />

        {error && <p className="field-error">{error}</p>}

        <div className="panel-actions">
          <button className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={!name.trim() || submitting}
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
