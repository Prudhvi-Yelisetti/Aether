// The signature element: makes the Planner/Validator/Decision pipeline
// (E1-E3) visible for every response, instead of just showing text with
// no indication of how it was produced. Reads left to right in the
// order the backend actually processes a request.

function capabilityLabel(type, name) {
  if (type === "reasoning") return "reasoning";
  if (type === "tool") return `tool:${name}`;
  if (type === "skill") return `skill:${name}`;
  return type || "unknown";
}

export default function CapabilityTrace({
  capabilityType,
  capabilityName,
  capabilitySource,
  model,
  attempts,
  escalated,
  llmValidation,
}) {
  if (!capabilityType) return null;

  const outcomeClass = escalated
    ? "trace-chip trace-outcome-escalated"
    : attempts > 1
    ? "trace-chip trace-outcome-retried"
    : "trace-chip trace-outcome-ok";

  const outcomeLabel = escalated
    ? "escalated"
    : attempts > 1
    ? `retried ×${attempts - 1}`
    : "ok";

  return (
    <div className="capability-trace" title="How this response was produced">
      <span className="trace-chip trace-source">plan·{capabilitySource}</span>
      <span className="trace-arrow">→</span>
      <span className="trace-chip trace-capability">
        {capabilityLabel(capabilityType, capabilityName)}
      </span>
      {model && (
        <>
          <span className="trace-arrow">→</span>
          <span className="trace-chip trace-model">{model}</span>
        </>
      )}
      <span className="trace-arrow">→</span>
      <span className={outcomeClass}>{outcomeLabel}</span>
      {/* llm_validate is opt-in and observability-only (see
          validation_service.py) — only render this chip when it
          actually ran, not a static "not run" placeholder on every
          message, which would just be noise for the vast majority of
          requests that don't use it. */}
      {llmValidation && (
        <>
          <span className="trace-arrow">→</span>
          <span
            className={
              llmValidation === "valid"
                ? "trace-chip trace-outcome-ok"
                : "trace-chip trace-outcome-escalated"
            }
            title="Opt-in LLM-based validation (llm_validate) — observability-only, does not affect delivery"
          >
            llm·{llmValidation}
          </span>
        </>
      )}
    </div>
  );
}
