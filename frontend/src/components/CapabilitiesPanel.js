import { useEffect, useState } from "react";
import { fetchCapabilities } from "../api";

// Directly reflects the same registries the Planner queries — not a
// hand-written feature list that can drift from what's actually
// registered (services/tools/registry.py, services/skills/registry.py).
export default function CapabilitiesPanel({ onClose }) {
  const [capabilities, setCapabilities] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCapabilities()
      .then(setCapabilities)
      .catch(() => setError("Couldn't reach the backend."));
  }, []);

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2>Capabilities</h2>
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {error && <p className="panel-error">{error}</p>}

        {capabilities && (
          <>
            <section className="capability-section">
              <h3>Tools</h3>
              <p className="capability-section-note">
                Single-step, deterministic actions the Planner can call directly.
              </p>
              {capabilities.tools.map((t) => (
                <div className="capability-item" key={t.name}>
                  <span className="capability-item-name">tool:{t.name}</span>
                  <span className="capability-item-desc">{t.description}</span>
                  {t.meta && (
                    <span className="capability-item-meta">
                      v{t.meta.version} · {t.meta.trust_level}
                      {t.meta.permissions.length > 0 && ` · ${t.meta.permissions.join(", ")}`}
                    </span>
                  )}
                </div>
              ))}
            </section>

            <section className="capability-section">
              <h3>Skills</h3>
              <p className="capability-section-note">
                Multi-step sequences composed from Tools and reasoning.
              </p>
              {capabilities.skills.map((s) => (
                <div className="capability-item" key={s.name}>
                  <span className="capability-item-name">skill:{s.name}</span>
                  <span className="capability-item-desc">{s.description}</span>
                  <span className="capability-item-steps">
                    {s.steps.join(" → ")}
                  </span>
                  {s.meta && (
                    <span className="capability-item-meta">
                      v{s.meta.version} · {s.meta.trust_level}
                      {s.meta.permissions.length > 0 && ` · ${s.meta.permissions.join(", ")}`}
                    </span>
                  )}
                </div>
              ))}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
