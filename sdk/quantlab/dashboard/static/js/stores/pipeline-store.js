/**
 * PipelineStore — Pub/sub store for pipeline monitor state.
 */

export default function createPipelineStore() {
  const subscribers = new Map();
  let state = {
    runs: [],
    loading: true,
    error: null,
    statusFilter: "",
    selectedRunId: null,
  };

  /**
   * Subscribe to state changes.
   * @param {string} key - state key to watch, or "*" for all
   * @param {Function} fn - callback receiving (data, key)
   * @returns {Function} unsubscribe function
   */
  function subscribe(key, fn) {
    if (!subscribers.has(key)) {
      subscribers.set(key, new Set());
    }
    subscribers.get(key).add(fn);

    // Immediately notify with current value
    if (key === "*") {
      fn(state, key);
    } else if (key in state) {
      fn(state[key], key);
    }

    return () => {
      const set = subscribers.get(key);
      if (set) {
        set.delete(fn);
        if (set.size === 0) subscribers.delete(key);
      }
    };
  }

  /**
   * Notify subscribers of state change.
   * @param {string} key
   * @param {*} value
   */
  function notify(key, value) {
    const prev = state;
    state = { ...prev, [key]: value };

    // Notify key-specific subscribers
    const keySubs = subscribers.get(key);
    if (keySubs) {
      for (const fn of keySubs) {
        fn(state[key], key);
      }
    }

    // Notify wildcard subscribers
    const allSubs = subscribers.get("*");
    if (allSubs) {
      for (const fn of allSubs) {
        fn(state, key);
      }
    }
  }

  /**
   * Get current state snapshot.
   * @returns {object}
   */
  function getState() {
    return { ...state };
  }

  // ── Actions ───────────────────────────────────────────────────────

  /**
   * Load pipeline runs (typically called by page module).
   * @param {Array} runs
   */
  function loadRuns(runs) {
    notify("runs", runs || []);
    notify("loading", false);
    notify("error", null);
  }

  /**
   * Set status filter.
   * @param {string} filter - status string or "" for all
   */
  function setFilter(filter) {
    notify("statusFilter", filter || "");
  }

  /**
   * Select a run for detail view.
   * @param {string|null} runId
   */
  function selectRun(runId) {
    notify("selectedRunId", runId);
  }

  return {
    subscribe,
    notify,
    getState,
    loadRuns,
    setFilter,
    selectRun,
  };
}
