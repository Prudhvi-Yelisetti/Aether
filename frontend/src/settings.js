// Persisted user preferences, stored in the browser's localStorage.
// Added 2026-08-02 for the Settings panel (model override, default
// validate-on-send) — nothing before this needed to survive a reload,
// so there was no settings storage at all until now.
const STORAGE_KEY = "aether_settings";

const DEFAULTS = {
  // null = auto-route (services/routing.py's select_model()), same
  // behavior as before this setting existed. Set = always send this
  // model, unless an attached image forces VISION_MODEL server-side
  // regardless (see main.py's ChatRequest).
  model: null,
  // Whether the composer's "validate" toggle starts checked. The
  // toggle itself is still per-message from there — this only sets
  // where it starts.
  defaultValidate: false,
  // Added 2026-08-12 for memory consolidation (services/
  // consolidation_service.py). Off by default — same trust-building-
  // period reasoning as defaultValidate above, but for a stricter
  // reason: a bad consolidation writes a wrong fact into durable
  // semantic memory, not just a missed validation check on one
  // response. See main.py's ChatRequest.consolidate_memory.
  consolidateMemory: false,
};

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    // Corrupt or blocked storage shouldn't break the app — fall back
    // to defaults exactly as if nothing had ever been saved.
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    return true;
  } catch {
    return false;
  }
}
