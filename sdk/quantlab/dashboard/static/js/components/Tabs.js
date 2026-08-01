/**
 * Tabs — full ARIA-compliant tab interface with keyboard navigation.
 */
import { escapeHtml } from "../utils/helpers.js";

export default class Tabs {
  /**
   * @param {string|Element} container - container selector or element
   * @param {object} [options]
   * @param {string} [options.activeTab] - initially active tab name
   * @param {Function} [options.onSwitch] - callback when tab switches
   */
  constructor(container, options = {}) {
    this.container = typeof container === "string"
      ? document.querySelector(container)
      : container;
    this.options = options;
    this._tabButtons = [];
    this._tabPanels = [];
    this._activeTab = options.activeTab || null;
    this._handlers = [];
  }

  /**
   * Initialize tabs — scan DOM for tab buttons and panels.
   */
  init() {
    if (!this.container) return;

    // Find tablist
    const tablist = this.container.querySelector('[role="tablist"]')
      || this.container.querySelector(".tabs__list")
      || this.container;

    this._tabButtons = Array.from(
      tablist.querySelectorAll('[role="tab"], .tabs__tab')
    );
    this._tabPanels = Array.from(
      this.container.querySelectorAll('[role="tabpanel"], .tabs__panel')
    );

    if (this._tabButtons.length === 0) return;

    // Set initial active tab
    if (!this._activeTab) {
      const activeBtn = this._tabButtons.find(
        (b) => b.classList.contains("tabs__tab--active") || b.getAttribute("aria-selected") === "true"
      );
      if (activeBtn) {
        this._activeTab = activeBtn.dataset.tab || activeBtn.getAttribute("aria-controls") || "";
      } else {
        // Default to first tab
        this._activeTab = this._tabButtons[0].dataset.tab
          || this._tabButtons[0].getAttribute("aria-controls")
          || "";
      }
    }

    this._activateTab(this._activeTab);

    // Wire events
    this._tabButtons.forEach((btn) => {
      const handler = (e) => {
        const tabName = btn.dataset.tab || btn.getAttribute("aria-controls") || "";
        this.switchTab(tabName);
      };
      btn.addEventListener("click", handler);
      this._handlers.push({ el: btn, type: "click", fn: handler });
    });

    // Keyboard navigation on tablist
    const keyHandler = (e) => {
      this._handleKeydown(e);
    };
    tablist.addEventListener("keydown", keyHandler);
    this._handlers.push({ el: tablist, type: "keydown", fn: keyHandler });
  }

  /**
   * Switch to a tab by name.
   * @param {string} tabName - value of data-tab or aria-controls
   */
  switchTab(tabName) {
    this._activateTab(tabName);
  }

  /**
   * Clean up all event listeners.
   */
  destroy() {
    for (const { el, type, fn } of this._handlers) {
      el.removeEventListener(type, fn);
    }
    this._handlers = [];
    this._tabButtons = [];
    this._tabPanels = [];
  }

  // ── Internal ──────────────────────────────────────────────────────

  _activateTab(tabName) {
    if (!tabName) return;

    this._tabButtons.forEach((btn) => {
      const isActive = (btn.dataset.tab === tabName)
        || (btn.getAttribute("aria-controls") === tabName);
      btn.classList.toggle("tabs__tab--active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
      btn.tabIndex = isActive ? 0 : -1;
    });

    this._tabPanels.forEach((panel) => {
      const isActive = panel.id === tabName
        || panel.dataset.tab === tabName;
      panel.classList.toggle("tabs__panel--active", isActive);
      panel.hidden = !isActive;
    });

    this._activeTab = tabName;

    if (this.options.onSwitch) {
      this.options.onSwitch(tabName);
    }
  }

  _handleKeydown(e) {
    const current = this._tabButtons.find((b) => b.tabIndex === 0) || this._tabButtons[0];
    const currentIndex = this._tabButtons.indexOf(current);
    let newIndex = currentIndex;

    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        newIndex = (currentIndex + 1) % this._tabButtons.length;
        break;
      case "ArrowLeft":
        e.preventDefault();
        newIndex = (currentIndex - 1 + this._tabButtons.length) % this._tabButtons.length;
        break;
      case "Home":
        e.preventDefault();
        newIndex = 0;
        break;
      case "End":
        e.preventDefault();
        newIndex = this._tabButtons.length - 1;
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (current) current.click();
        return;
      default:
        return;
    }

    const nextBtn = this._tabButtons[newIndex];
    if (nextBtn) {
      nextBtn.focus();
      nextBtn.click();
    }
  }
}
