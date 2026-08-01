/**
 * StatsStore — Pub/sub store for statistics dashboard state.
 */

export default function createStatsStore() {
  const subscribers = new Map();
  let state = {
    stats: null,
    loading: true,
    error: null,
    chartType: "sharpe",
    showBenchmark: false,
    filters: {
      market: "",
      timeframe: "",
      startDate: "",
      endDate: "",
    },
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
   * Load stats data (called by page module on fetch success).
   * @param {object} statsData
   */
  function loadStats(statsData) {
    notify("stats", statsData || null);
    notify("loading", false);
    notify("error", null);
  }

  /**
   * Set chart type for main chart.
   * @param {string} type - 'sharpe' | 'drawdown' | 'winrate' | 'return' | 'benchmark'
   */
  function setChartType(type) {
    notify("chartType", type || "sharpe");
  }

  /**
   * Toggle benchmark overlay on main chart.
   */
  function toggleBenchmark() {
    notify("showBenchmark", !state.showBenchmark);
  }

  /**
   * Set a filter value.
   * @param {string} key - 'market' | 'timeframe' | 'startDate' | 'endDate'
   * @param {string} value
   */
  function setFilter(key, value) {
    if (!(key in state.filters)) return;
    const filters = { ...state.filters, [key]: value };
    notify("filters", filters);
  }

  return {
    subscribe,
    notify,
    getState,
    loadStats,
    setChartType,
    toggleBenchmark,
    setFilter,
  };
}
