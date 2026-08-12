import { useEffect, useState } from "react";
import { fetchModels } from "../api";
import { loadSettings, saveSettings } from "../settings";

// Added 2026-08-02, per Prudhvi's request. Two real, backend-wired
// settings, not filler: model override (GET /models, live-queried from
// Ollama — see main.py) and the composer's default "validate" state.
// Both persist across reloads via localStorage (settings.js) since
// nothing here needs to be shared across devices or people.
export default function SettingsPanel({ onClose, onSettingsChange }) {
  const [models, setModels] = useState(null);
  const [error, setError] = useState(null);
  const [settings, setSettings] = useState(loadSettings);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchModels()
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setModels(data.models || []);
        }
      })
      .catch(() => setError("Couldn't reach the backend."));
  }, []);

  const handleSave = () => {
    saveSettings(settings);
    onSettingsChange(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel panel-narrow" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2>Settings</h2>
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <label className="field-label" htmlFor="settings-model">
          Model
        </label>
        {error && <p className="field-error">{error}</p>}
        {!models && !error && <p className="capability-section-note">Loading models...</p>}
        {models && (
          <select
            id="settings-model"
            className="field-input"
            value={settings.model || ""}
            onChange={(e) => setSettings((s) => ({ ...s, model: e.target.value || null }))}
          >
            <option value="">Auto (let Aether choose)</option>
            {models.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name}
                {m.capabilities.includes("vision") ? " — vision" : ""}
              </option>
            ))}
          </select>
        )}
        <p className="field-hint">
          An attached image always uses the vision-capable model, regardless of this setting.
        </p>

        <label className="toggle-validate settings-toggle">
          <input
            type="checkbox"
            checked={settings.defaultValidate}
            onChange={(e) => setSettings((s) => ({ ...s, defaultValidate: e.target.checked }))}
          />
          Default "validate" to on for new messages
        </label>

        <label className="toggle-validate settings-toggle">
          <input
            type="checkbox"
            checked={settings.consolidateMemory}
            onChange={(e) => setSettings((s) => ({ ...s, consolidateMemory: e.target.checked }))}
          />
          Consolidate memory
        </label>
        <p className="field-hint">
          When a skill result is about to be dropped from memory, Aether summarizes
          it into a durable fact first (with a strict check against the source before
          it's saved). Off by default — see the Memory panel for anything it writes.
        </p>

        <div className="panel-actions">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSave}>
            {saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
