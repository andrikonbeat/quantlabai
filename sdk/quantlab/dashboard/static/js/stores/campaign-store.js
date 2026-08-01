/**
 * Campaign Store — pub/sub store with campaign-specific state.
 * createStore() returns { subscribe, notify, getState, setState }
 */
import { apiGet } from "../api/client.js";

function createStore() {
  const subscribers = {};
  const state = {
    campaigns: [],
    loading: true,
    error: null,
    search: "",
    statusFilter: "",
    marketFilter: "",
    // Detail page state
    currentCampaign: null,
    campaignLoading: true,
    campaignError: null,
  };

  return {
    /**
     * Subscribe to a key. Returns unsubscribe function.
     * @param {string} key
     * @param {Function} fn
     * @returns {Function} unsubscribe
     */
    subscribe(key, fn) {
      if (!subscribers[key]) subscribers[key] = [];
      subscribers[key].push(fn);
      return () => {
        subscribers[key] = (subscribers[key] || []).filter((s) => s !== fn);
      };
    },

    /**
     * Notify subscribers for a key with data.
     * @param {string} key
     * @param {any} data
     */
    notify(key, data) {
      (subscribers[key] || []).forEach((fn) => fn(data));
    },

    /**
     * Get current value for a key.
     * @param {string} key
     * @returns {any}
     */
    getState(key) {
      return state[key];
    },

    /**
     * Set state for a key and notify subscribers.
     * @param {string} key
     * @param {any} data
     */
    setState(key, data) {
      state[key] = data;
      this.notify(key, data);
    },

    /**
     * Load a single campaign by ID.
     * @param {string} id
     */
    async loadCampaign(id) {
      state.campaignLoading = true;
      state.campaignError = null;
      this.notify("campaignLoading", true);

      const result = await apiGet(`/api/campaigns/${encodeURIComponent(id)}`);
      if (!result.success) {
        state.campaignLoading = false;
        state.campaignError = result.error || "Failed to load campaign";
        this.notify("campaignLoading", false);
        this.notify("campaignError", state.campaignError);
        return;
      }

      state.campaignLoading = false;
      state.currentCampaign = result.data || null;
      this.notify("campaignLoading", false);
      this.notify("currentCampaign", state.currentCampaign);
    },

    /**
     * Set campaign data directly.
     * @param {object} data
     */
    setCampaign(data) {
      state.currentCampaign = data;
      state.campaignLoading = false;
      state.campaignError = null;
      this.notify("currentCampaign", data);
      this.notify("campaignLoading", false);
      this.notify("campaignError", null);
    },
  };
}

const store = createStore();
export default store;
