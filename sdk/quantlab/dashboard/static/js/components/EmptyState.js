/**
 * EmptyState — renders empty state with illustration, title, text, action.
 */
import { escapeHtml } from "../utils/helpers.js";

export default class EmptyState {
  /**
   * Render empty state.
   * @param {{ title: string, text: string, actionLabel: string, actionUrl: string }} opts
   * @returns {string} HTML string
   */
  render({ title, text, actionLabel, actionUrl } = {}) {
    if (!this || !title) return "";

    return `
      <div class="empty-state">
        <div class="empty-state__illustration" aria-hidden="true">
          <svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="20" y="45" width="80" height="50" rx="8" stroke="currentColor" stroke-width="2" fill="none"/>
            <line x1="30" y1="60" x2="55" y2="60" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <line x1="30" y1="70" x2="45" y2="70" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="30" y1="78" x2="65" y2="78" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="75" cy="70" r="15" stroke="currentColor" stroke-width="2" fill="none"/>
            <line x1="85" y1="80" x2="92" y2="87" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <path d="M40 25 L60 20 L80 25" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="40" cy="25" r="3" fill="currentColor"/>
            <circle cx="60" cy="20" r="3" fill="currentColor"/>
            <circle cx="80" cy="25" r="3" fill="currentColor"/>
          </svg>
        </div>
        <h3 class="empty-state__title">${escapeHtml(title)}</h3>
        <p class="empty-state__text">${escapeHtml(text)}</p>
        ${actionUrl ? `
          <a href="${escapeHtml(actionUrl)}" class="btn btn--primary empty-state__action">${escapeHtml(actionLabel || "Get Started")}</a>
        ` : ""}
      </div>
    `;
  }
}
