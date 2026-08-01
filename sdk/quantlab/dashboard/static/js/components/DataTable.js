/**
 * DataTable Component — renders sortable, paginated table.
 */
import { escapeHtml } from "../utils/helpers.js";

const SORTABLE_COLUMNS = [
  { key: "name", label: "Campaign" },
  { key: "market", label: "Market" },
  { key: "timeframe", label: "Timeframe" },
  { key: "status", label: "Status" },
  { key: "sharpe", label: "Sharpe", number: true },
  { key: "profit_factor", label: "Profit Factor", number: true },
  { key: "win_rate", label: "Win Rate", number: true },
  { key: "total_return", label: "Total Return", number: true },
];

export default class DataTable {
  constructor(container) {
    this.container = container;
  }

  /**
   * Render table body with data.
   * @param {Array} campaigns
   * @param {{ column: string, dir: string }} sort
   * @param {number} page
   * @param {number} totalPages
   */
  render(campaigns, sort = { column: null, dir: null }, page = 1, totalPages = 1) {
    if (!this.container) return;

    if (campaigns.length === 0) {
      this.container.innerHTML = `
        <tr>
          <td colspan="9" class="data-table__empty">No campaigns match the current filters.</td>
        </tr>
      `;
      return;
    }

    let html = "";

    for (const c of campaigns) {
      const id = c.id || c.campaign_id || "";
      const totalReturn = c.total_return;
      const returnClass = totalReturn != null ? (totalReturn >= 0 ? "data-table__cell--positive" : "data-table__cell--negative") : "";

      html += `
        <tr class="data-table__row data-table__row--clickable" data-id="${escapeHtml(id)}">
          <td class="data-table__cell" data-label="Campaign">${escapeHtml(c.name || id)}</td>
          <td class="data-table__cell" data-label="Market">${escapeHtml(c.market || "—")}</td>
          <td class="data-table__cell" data-label="Timeframe">${escapeHtml(c.timeframe || "—")}</td>
          <td class="data-table__cell" data-label="Status">
            <span class="badge badge--${c.status || "pending"}">${escapeHtml(c.status || "—")}</span>
          </td>
          <td class="data-table__cell data-table__cell--number" data-label="Sharpe">${c.sharpe != null ? c.sharpe.toFixed(2) : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Profit Factor">${c.profit_factor != null ? c.profit_factor.toFixed(2) : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Win Rate">${c.win_rate != null ? (c.win_rate * 100).toFixed(1) + "%" : "—"}</td>
          <td class="data-table__cell data-table__cell--number ${returnClass}" data-label="Total Return">${totalReturn != null ? totalReturn.toFixed(2) : "—"}</td>
          <td class="data-table__cell" data-label="Actions">
            <button class="btn btn--sm btn--secondary view-detail-btn" data-id="${escapeHtml(id)}">View</button>
          </td>
        </tr>
      `;
    }

    this.container.innerHTML = html;

    // Row click navigation
    this.container.querySelectorAll(".data-table__row--clickable").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest(".view-detail-btn")) return;
        const id = row.dataset.id;
        if (id) window.location.href = `/campaigns/${encodeURIComponent(id)}`;
      });
    });

    // View button click
    this.container.querySelectorAll(".view-detail-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (id) window.location.href = `/campaigns/${encodeURIComponent(id)}`;
      });
    });
  }

  /**
   * Update sort column and direction.
   * @param {string} column
   * @param {string} dir - 'asc' | 'desc' | null
   */
  updateSort(column, dir) {
    this.currentSort = { column, dir };
  }

  /**
   * Update current page.
   * @param {number} page
   */
  updatePage(page) {
    this.currentPage = page;
  }
}
