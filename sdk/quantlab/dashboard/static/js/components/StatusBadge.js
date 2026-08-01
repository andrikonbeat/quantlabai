/**
 * StatusBadge — renders a status badge with icon + color mapping.
 * Returns HTML string (no DOM attachment).
 */
import { escapeHtml } from "../utils/helpers.js";

const STATUS_CONFIG = {
  running: {
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>`,
    color: "var(--color-primary)",
    cssClass: "status-badge--running",
  },
  completed: {
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>`,
    color: "var(--color-success)",
    cssClass: "status-badge--completed",
  },
  failed: {
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    color: "var(--color-danger)",
    cssClass: "status-badge--failed",
  },
  pending: {
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    color: "var(--color-text-muted)",
    cssClass: "status-badge--pending",
  },
  skipped: {
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="15 9 9 15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    color: "var(--color-warning)",
    cssClass: "status-badge--skipped",
  },
};

export default class StatusBadge {
  /**
   * Render a status badge.
   * @param {string} status - running | completed | failed | pending | skipped
   * @param {string} [label] - display label (defaults to status)
   * @returns {string} HTML string
   */
  render(status, label) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
    const displayLabel = label || status;
    const isRunning = status === "running";
    const pulseAttr = isRunning ? ' style="animation: status-pulse 2s ease-in-out infinite;"' : "";

    return `
      <span class="status-badge ${config.cssClass}" aria-label="Status: ${escapeHtml(status)}"${pulseAttr}>
        <span class="status-badge__icon">${config.icon}</span>
        <span class="status-badge__label">${escapeHtml(displayLabel)}</span>
      </span>
    `;
  }

  /**
   * Get the SVG icon for a status (for use in other contexts).
   * @param {string} status
   * @returns {string} SVG markup
   */
  getIcon(status) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
    return config.icon;
  }

  /**
   * Get the CSS color value for a status.
   * @param {string} status
   * @returns {string} CSS variable
   */
  getColor(status) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
    return config.color;
  }
}
