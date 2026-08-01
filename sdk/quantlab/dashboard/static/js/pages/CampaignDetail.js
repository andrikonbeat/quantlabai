/**
 * Campaign Detail Page — orchestrates data fetching, metrics, chart, tabs,
 * trades table, stages timeline, and report generation.
 */
import { apiGet, apiPost } from "../api/client.js";
import store from "../stores/campaign-store.js";
import MetricCard from "../components/MetricCard.js";
import Tabs from "../components/Tabs.js";
import ChartContainer from "../components/ChartContainer.js";
import StatusBadge from "../components/StatusBadge.js";
import Sidebar from "../components/Sidebar.js";
import { escapeHtml } from "../utils/helpers.js";
import { formatDate } from "../utils/formatters.js";

export default function init() {
  // ── Get campaign ID from URL ──────────────────────────────────────
  const pathParts = window.location.pathname.split("/");
  const campaignId = pathParts[pathParts.length - 1];
  if (!campaignId || campaignId === "campaigns") return;

  // ── DOM refs ──────────────────────────────────────────────────────
  const campaignName = document.getElementById("campaign-name");
  const statusBadgeEl = document.getElementById("status-badge");
  const marketTag = document.getElementById("market-tag");
  const timeframeTag = document.getElementById("timeframe-tag");
  const dateRangeTag = document.getElementById("date-range-tag");
  const reportBtn = document.getElementById("generate-report-btn");
  const tradesTbody = document.getElementById("trades-table-body");
  const stagesList = document.getElementById("stages-list");
  const reportsList = document.getElementById("reports-list");
  const sidebarEl = document.getElementById("campaign-list");
  const metricsContainer = document.getElementById("metrics-cards");
  const errorContainer = document.getElementById("error-container");
  const detailHeader = document.getElementById("detail-header");
  const toastContainer = document.getElementById("toast-container");

  // ── Component instances ───────────────────────────────────────────
  const tabs = new Tabs("#detail-tabs", {
    onSwitch: (tabName) => {
      if (tabName === "trades") loadTrades();
      if (tabName === "stages") loadStages();
      if (tabName === "reports") loadReports();
    },
  });
  const chart = new ChartContainer("equity-chart", { responsive: true });
  const statusBadge = new StatusBadge();
  const sidebar = new Sidebar(sidebarEl);

  let metricCards = {};

  // ── Loading state ─────────────────────────────────────────────────
  function showLoading() {
    if (metricsContainer) {
      metricsContainer.innerHTML = `
        <div class="skeleton skeleton--metric"></div>
        <div class="skeleton skeleton--metric"></div>
        <div class="skeleton skeleton--metric"></div>
        <div class="skeleton skeleton--metric"></div>
      `;
    }
    if (errorContainer) errorContainer.style.display = "none";
    if (detailHeader) detailHeader.style.opacity = "0.5";
  }

  // ── Error state ───────────────────────────────────────────────────
  function showError(message) {
    if (metricsContainer) metricsContainer.style.display = "none";
    if (detailHeader) detailHeader.style.opacity = "1";
    if (errorContainer) {
      errorContainer.style.display = "";
      errorContainer.innerHTML = `
        <div class="detail-error">
          <p>${escapeHtml(message || "Failed to load campaign data.")}</p>
          <button class="btn btn--primary" id="retry-btn">Retry</button>
        </div>
      `;
      const retryBtn = document.getElementById("retry-btn");
      if (retryBtn) {
        retryBtn.addEventListener("click", () => {
          errorContainer.style.display = "none";
          loadCampaign();
        });
      }
    }
  }

  // ── Toast helper ──────────────────────────────────────────────────
  function showToast(message, type = "success") {
    if (!toastContainer) {
      // Fallback if no toast container — still use console, NOT alert()
      console.log(`[Toast: ${type}] ${message}`);
      return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "polite");
    toast.innerHTML = `<span class="toast__message">${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => {
      toast.classList.add("toast--dismissing");
      setTimeout(() => {
        if (toast.parentElement) toast.remove();
      }, 250);
    }, 4000);
  }

  // ── Load sidebar ──────────────────────────────────────────────────
  async function loadSidebar() {
    const result = await apiGet("/api/campaigns");
    if (result.success && result.data) {
      sidebar.render(result.data, campaignId);
    }
  }

  // ── Load campaign data ────────────────────────────────────────────
  async function loadCampaign() {
    showLoading();

    const result = await apiGet(`/api/campaigns/${encodeURIComponent(campaignId)}`);
    if (!result.success) {
      showError(result.error || "Failed to load campaign");
      return;
    }

    const campaign = result.data || {};

    // Update header
    if (campaignName) campaignName.textContent = campaign.name || campaign.id || "Unknown Campaign";
    if (statusBadgeEl) {
      statusBadgeEl.innerHTML = statusBadge.render(campaign.status || "pending");
    }
    if (marketTag) marketTag.textContent = `Market: ${campaign.market || "—"}`;
    if (timeframeTag) timeframeTag.textContent = `Timeframe: ${campaign.timeframe || "—"}`;
    if (dateRangeTag) {
      const from = campaign.date_from || "—";
      const to = campaign.date_to || "—";
      dateRangeTag.textContent = `Date Range: ${from} to ${to}`;
    }

    // Enable report button
    if (reportBtn) reportBtn.disabled = false;

    // Remove loading from header
    if (detailHeader) detailHeader.style.opacity = "1";

    // Hide error
    if (errorContainer) errorContainer.style.display = "none";

    // Show metrics
    if (metricsContainer) metricsContainer.style.display = "";

    // ── Render Metric Cards ─────────────────────────────────────────
    if (metricsContainer) {
      const metricsData = [
        { metricType: "sharpe", label: "Sharpe Ratio", value: campaign.sharpe, sparkline: campaign.sharpe_history, id: "metric-sharpe" },
        { metricType: "drawdown", label: "Max Drawdown", value: campaign.max_drawdown, sparkline: campaign.drawdown_history, id: "metric-maxdd" },
        { metricType: "winrate", label: "Win Rate", value: campaign.win_rate, sparkline: campaign.winrate_history, id: "metric-winrate" },
        { metricType: "return", label: "Total Return", value: campaign.total_return, sparkline: campaign.return_history, id: "metric-return" },
      ];

      metricsContainer.innerHTML = "";
      metricsContainer.style.display = "grid";

      for (const m of metricsData) {
        const el = document.createElement("div");
        el.id = m.id;
        metricsContainer.appendChild(el);

        metricCards[m.metricType] = new MetricCard(el, {
          metricType: m.metricType,
          label: m.label,
          value: m.value,
          sparkline: m.sparkline,
        });
        metricCards[m.metricType].render();
      }
    }

    // ── Render Equity Curve Chart ───────────────────────────────────
    if (campaign.equity_curve) {
      const trace = {
        x: campaign.equity_curve.map((p) => p.date || p.time || p.t),
        y: campaign.equity_curve.map((p) => p.equity || p.value || p.v),
        type: "scatter",
        mode: "lines",
        name: "Equity",
        line: { color: "#2563EB", width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(37, 99, 235, 0.08)",
      };
      chart.init([trace], {
        title: { text: "Equity Curve", font: { size: 14 } },
        yaxis: { title: "Equity" },
      });
    } else {
      chart.init([], { title: { text: "Equity Curve" } });
    }

    // ── Init Tabs ──────────────────────────────────────────────────
    tabs.init();

    // Load initial active tab content
    const activeTabBtn = document.querySelector('.tabs__tab--active, [role="tab"][aria-selected="true"]');
    const activeTab = activeTabBtn
      ? (activeTabBtn.dataset.tab || activeTabBtn.getAttribute("aria-controls") || "equity")
      : "equity";
    if (activeTab === "trades") loadTrades();
    if (activeTab === "stages") loadStages();
    if (activeTab === "reports") loadReports();

    // ── Generate Report ──────────────────────────────────────────────
    if (reportBtn) {
      // Remove old listeners by cloning
      const newBtn = reportBtn.cloneNode(true);
      reportBtn.parentNode.replaceChild(newBtn, reportBtn);

      newBtn.addEventListener("click", async () => {
        newBtn.disabled = true;
        newBtn.innerHTML = `
          <span class="btn__spinner" aria-hidden="true"></span>
          Generating...
        `;

        const result = await apiPost("/api/reports/generate", {
          campaign_id: campaignId,
          theme: "dark",
          formats: ["html"],
        });

        newBtn.disabled = false;
        newBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          Generate Report
        `;

        if (result.success) {
          showToast("Report generated successfully!", "success");
        } else {
          showToast("Failed to generate report: " + (result.error?.message || "Unknown error"), "error");
        }
      });
    }

    store.setCampaign(campaign);
  }

  // ── Trades Tab ────────────────────────────────────────────────────
  let tradesLoaded = false;

  async function loadTrades() {
    if (tradesLoaded || !tradesTbody) return;
    tradesLoaded = true;

    tradesTbody.innerHTML = '<tr class="loading-row"><td colspan="7">Loading trades...</td></tr>';

    const result = await apiGet(`/api/campaigns/${encodeURIComponent(campaignId)}/trades`);
    if (!result.success || !result.data) {
      tradesTbody.innerHTML = '<tr class="loading-row"><td colspan="7">Failed to load trades.</td></tr>';
      return;
    }

    const trades = result.data;

    if (trades.length === 0) {
      tradesTbody.innerHTML = '<tr class="loading-row"><td colspan="7">No trades recorded.</td></tr>';
      return;
    }

    tradesTbody.innerHTML = trades
      .map(
        (t) => `
      <tr>
        <td>${escapeHtml(t.entry_time || "—")}</td>
        <td>${escapeHtml(t.exit_time || "—")}</td>
        <td>${escapeHtml(t.direction || "—")}</td>
        <td class="number">${t.entry_price != null ? t.entry_price.toFixed(5) : "—"}</td>
        <td class="number">${t.exit_price != null ? t.exit_price.toFixed(5) : "—"}</td>
        <td class="number ${(t.profit || 0) >= 0 ? "positive" : "negative"}">${t.profit != null ? t.profit.toFixed(2) : "—"}</td>
        <td class="number ${(t.pnl_pct || 0) >= 0 ? "positive" : "negative"}">${t.pnl_pct != null ? (t.pnl_pct * 100).toFixed(2) + "%" : "—"}</td>
      </tr>
    `
      )
      .join("");
  }

  // ── Stages Tab ────────────────────────────────────────────────────
  let stagesLoaded = false;

  async function loadStages() {
    if (stagesLoaded || !stagesList) return;
    stagesLoaded = true;

    stagesList.innerHTML = '<div class="loading">Loading stages...</div>';

    const result = await apiGet(`/api/campaigns/${encodeURIComponent(campaignId)}/stages`);
    if (!result.success || !result.data) {
      stagesList.innerHTML = '<div class="loading">Failed to load stages.</div>';
      return;
    }

    const stages = result.data;

    if (stages.length === 0) {
      stagesList.innerHTML = '<div class="loading">No stages recorded.</div>';
      return;
    }

    stagesList.innerHTML = stages
      .map(
        (s) => `
      <div class="stage-item">
        <span class="stage-indicator ${s.status || "pending"}"></span>
        <div class="stage-content">
          <span class="stage-name">${escapeHtml(s.name || "Unknown Stage")}</span>
          <span class="stage-duration">${s.duration || "—"}</span>
          <span class="stage-status ${s.status || "pending"}">${escapeHtml(s.status || "—")}</span>
        </div>
      </div>
    `
      )
      .join("");
  }

  // ── Reports Tab ───────────────────────────────────────────────────
  let reportsLoaded = false;

  async function loadReports() {
    if (reportsLoaded || !reportsList) return;
    reportsLoaded = true;

    reportsList.innerHTML = '<div class="loading">Loading reports...</div>';

    const result = await apiGet(`/api/campaigns/${encodeURIComponent(campaignId)}/reports`);
    if (!result.success || !result.data) {
      reportsList.innerHTML = '<div class="loading">Failed to load reports.</div>';
      return;
    }

    const reports = result.data;

    if (reports.length === 0) {
      reportsList.innerHTML = '<div class="loading">No reports generated yet. Use the "Generate Report" button above.</div>';
      return;
    }

    reportsList.innerHTML = reports
      .map(
        (r) => `
      <div class="report-item">
        <span class="report-name">${escapeHtml(r.name || "Report")}</span>
        <span class="report-date">${r.created_at ? formatDate(r.created_at) : "—"}</span>
        <a href="${escapeHtml(r.url || "#")}" class="btn btn--secondary btn--sm" download>Download</a>
      </div>
    `
      )
      .join("");
  }

  // ── Init ──────────────────────────────────────────────────────────
  loadSidebar();
  loadCampaign();

  // Cleanup on page unload
  window.addEventListener("beforeunload", () => {
    chart.destroy();
    tabs.destroy();
  });
}
