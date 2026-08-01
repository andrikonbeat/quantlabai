/**
 * ToastManager — Singleton notification system with stack queue.
 * Shows auto-dismissing toasts with a progress bar.
 */

const DEFAULT_DURATIONS = {
  success: 4000,
  info: 4000,
  warning: 8000,
  error: null, // No auto-dismiss — user must close
};

const MAX_VISIBLE = 5;

class ToastManager {
  constructor() {
    if (ToastManager._instance) return ToastManager._instance;
    this._toasts = new Map(); // id → { element, timer, duration, type }
    this._counter = 0;
    this._container = null;
    ToastManager._instance = this;
  }

  /**
   * Show a toast notification.
   * @param {{ type: string, message: string, duration?: number }} opts
   * @returns {string} toast id
   */
  show({ type = "info", message = "", duration } = {}) {
    if (!message) return;
    this._ensureContainer();

    const id = `toast-${++this._counter}`;
    const dismissDuration = duration || DEFAULT_DURATIONS[type] || null;
    const toastEl = this._createToastElement(id, type, message, dismissDuration);

    // Enforce max visible — dismiss oldest if at limit
    if (this._toasts.size >= MAX_VISIBLE) {
      const oldest = this._toasts.keys().next().value;
      if (oldest) this.dismiss(oldest);
    }

    this._container.appendChild(toastEl);
    this._toasts.set(id, { element: toastEl, type, dismissDuration });

    // Trigger layout for animation
    requestAnimationFrame(() => {
      toastEl.classList.add("toast--visible");
    });

    // Auto-dismiss timer
    if (dismissDuration !== null) {
      const timer = setTimeout(() => this.dismiss(id), dismissDuration);
      this._toasts.get(id).timer = timer;
    }

    return id;
  }

  /**
   * Dismiss a specific toast by ID.
   * @param {string} id
   */
  dismiss(id) {
    const entry = this._toasts.get(id);
    if (!entry) return;

    if (entry.timer) {
      clearTimeout(entry.timer);
      entry.timer = null;
    }

    const { element } = entry;
    element.classList.add("toast--dismissing");

    setTimeout(() => {
      if (element.parentNode) {
        element.parentNode.removeChild(element);
      }
      this._toasts.delete(id);
    }, 250);
  }

  /**
   * Dismiss all visible toasts immediately.
   */
  dismissAll() {
    const ids = Array.from(this._toasts.keys());
    for (const id of ids) {
      this.dismiss(id);
    }
  }

  // ── Internal ──────────────────────────────────────────────────────

  _ensureContainer() {
    if (!this._container) {
      this._container = document.createElement("div");
      this._container.className = "toast-container";
      this._container.setAttribute("aria-live", "polite");
      document.body.appendChild(this._container);
    }
  }

  _createToastElement(id, type, message, dismissDuration) {
    const div = document.createElement("div");
    div.className = `toast toast--${type}`;
    div.id = id;
    div.setAttribute("role", "alert");

    const iconSvg = this._getIcon(type);

    div.innerHTML = `
      <span class="toast__icon">${iconSvg}</span>
      <span class="toast__message">${this._escapeHtml(message)}</span>
      <button class="toast__close" aria-label="Dismiss notification">&times;</button>
      ${dismissDuration !== null ? '<span class="toast__progress"></span>' : ""}
    `;

    // Close button handler
    const closeBtn = div.querySelector(".toast__close");
    if (closeBtn) {
      closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.dismiss(id);
      });
    }

    // Set progress bar duration
    if (dismissDuration !== null) {
      const progress = div.querySelector(".toast__progress");
      if (progress) {
        progress.style.animationDuration = `${dismissDuration}ms`;
      }
    }

    return div;
  }

  _getIcon(type) {
    switch (type) {
      case "success":
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="18" height="18"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>`;
      case "error":
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
      case "warning":
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="18" height="18"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
      case "info":
      default:
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    }
  }

  _escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }
}

// Singleton instance
const toastManager = new ToastManager();
export default toastManager;
