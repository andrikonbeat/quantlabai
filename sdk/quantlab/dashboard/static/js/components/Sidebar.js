/**
 * Sidebar Component — renders campaign list sidebar with
 * collapsible sections by status.
 */
import { escapeHtml } from "../utils/helpers.js";

export default class Sidebar {
  constructor(container) {
    this.container = container;
  }

  /**
   * Render sidebar with campaigns grouped by status.
   * @param {Array} campaigns
   * @param {string} activeId - currently active campaign ID
   */
  render(campaigns, activeId) {
    if (!this.container) return;

    const grouped = {
      running: campaigns.filter((c) => c.status === "running"),
      completed: campaigns.filter((c) => c.status === "completed"),
      failed: campaigns.filter((c) => c.status === "failed"),
      pending: campaigns.filter((c) => c.status === "pending"),
    };

    const sectionOrder = ["running", "completed", "failed", "pending"];
    const sectionLabels = {
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      pending: "Pending",
    };

    let html = '<div class="sidebar">';

    html += `
      <div class="sidebar__header">
        <h2>Campaigns</h2>
      </div>
    `;

    for (const status of sectionOrder) {
      const items = grouped[status] || [];
      if (items.length === 0) continue;

      html += `
        <div class="sidebar__section" data-status="${status}">
          <div class="sidebar__section-title" role="button" tabindex="0" aria-expanded="true">
            <span class="chevron">▼</span>
            ${sectionLabels[status]}
            <span style="margin-left:auto;font-size:var(--text-xs);color:var(--color-text-muted)">${items.length}</span>
          </div>
          <div class="sidebar__section-items">
      `;

      for (const c of items) {
        const id = c.id || c.campaign_id || "";
        const isActive = activeId === id;

        html += `
          <div class="sidebar__item ${isActive ? "sidebar__item--active" : ""}" data-id="${escapeHtml(id)}" role="button" tabindex="0">
            <div class="sidebar__item-name">
              <span>${escapeHtml(c.name || id)}</span>
              <span class="sidebar__item-status sidebar__item-status--${c.status}">${escapeHtml(c.status || "")}</span>
            </div>
            <div class="sidebar__item-meta">
              <span>${escapeHtml(c.market || "—")}</span>
              <span>${escapeHtml(c.timeframe || "—")}</span>
            </div>
          </div>
        `;
      }

      html += `
          </div>
        </div>
      `;
    }

    html += "</div>";
    this.container.innerHTML = html;

    // ── Event wiring ────────────────────────────────────────────────

    // Section title click toggles collapse
    this.container.querySelectorAll(".sidebar__section-title").forEach((title) => {
      title.addEventListener("click", () => {
        const section = title.closest(".sidebar__section");
        if (section) {
          section.classList.toggle("sidebar__section--collapsed");
          const expanded = !section.classList.contains("sidebar__section--collapsed");
          title.setAttribute("aria-expanded", expanded);
        }
      });

      title.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          title.click();
        }
      });
    });

    // Item click navigates
    this.container.querySelectorAll(".sidebar__item").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.dataset.id;
        if (id) {
          window.location.href = `/campaigns/${encodeURIComponent(id)}`;
        }
      });

      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          item.click();
        }
      });
    });

    // Restore scroll position
    const savedScroll = sessionStorage.getItem("sidebar-scroll-campaigns");
    if (savedScroll) {
      this.container.scrollTop = parseInt(savedScroll, 10);
    }

    // Save scroll position on scroll
    this.container.addEventListener("scroll", () => {
      sessionStorage.setItem("sidebar-scroll-campaigns", this.container.scrollTop);
    });
  }

  /**
   * Update a filter value.
   * @param {string} key
   * @param {string} value
   */
  updateFilter(key, value) {
    const store = window.__STORE__;
    if (store && store.setState) {
      store.setState(key, value);
    }
  }
}
