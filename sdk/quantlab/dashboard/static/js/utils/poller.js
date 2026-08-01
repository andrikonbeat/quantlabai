/**
 * PollingService — interval-based polling with exponential backoff
 * and Page Visibility API integration.
 */
import { apiGet } from "../api/client.js";

const BACKOFF_SCHEDULE = [3000, 10000, 30000, 60000];

export default class PollingService {
  constructor() {
    this._timer = null;
    this._url = null;
    this._interval = null;
    this._callback = null;
    this._backoffIndex = -1;
    this._controller = null;
    this._paused = false;
    this._destroyed = false;

    this._onVisibilityChange = this._onVisibilityChange.bind(this);
  }

  /**
   * Start polling.
   * @param {string} url - API endpoint
   * @param {number} interval - interval in ms
   * @param {Function} callback - receives data on success
   */
  start(url, interval, callback) {
    this.stop();
    this._url = url;
    this._interval = interval;
    this._callback = callback;
    this._backoffIndex = -1;
    this._destroyed = false;

    document.addEventListener("visibilitychange", this._onVisibilityChange);

    this._poll();
  }

  stop() {
    this._destroyed = true;
    this._clearTimer();
    this._abortRequest();
    document.removeEventListener("visibilitychange", this._onVisibilityChange);
    this._url = null;
    this._callback = null;
  }

  pause() {
    this._paused = true;
    this._clearTimer();
    this._abortRequest();
  }

  resume() {
    if (!this._paused || !this._url) return;
    this._paused = false;
    this._backoffIndex = -1;
    this._poll();
  }

  // ── Internal ──────────────────────────────────────────────────────

  _clearTimer() {
    if (this._timer !== null) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  }

  _abortRequest() {
    if (this._controller) {
      this._controller.abort();
      this._controller = null;
    }
  }

  _onVisibilityChange() {
    if (document.hidden) {
      this.pause();
    } else {
      this.resume();
    }
  }

  async _poll() {
    if (this._destroyed || this._paused) return;

    this._controller = new AbortController();
    const result = await apiGet(this._url, { signal: this._controller.signal });

    if (this._destroyed) return;

    if (result.success) {
      this._backoffIndex = -1;
      if (this._callback) {
        this._callback(result.data);
      }
    } else if (result.error !== "Request timed out or was cancelled") {
      this._backoffIndex = Math.min(this._backoffIndex + 1, BACKOFF_SCHEDULE.length - 1);
    }

    this._scheduleNext();
  }

  _scheduleNext() {
    if (this._destroyed || this._paused) return;

    const delay = this._backoffIndex >= 0
      ? BACKOFF_SCHEDULE[this._backoffIndex]
      : this._interval;

    this._timer = setTimeout(() => this._poll(), delay);
  }
}
