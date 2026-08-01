/**
 * StatsDashboard — Page module for statistics dashboard.
 * Orchestrates KPI cards, main chart with type selector, 4-chart grid,
 * stats table with sort/pagination, sidebar filters, and 15s polling.
 */
import { apiGet } from "../api/client.js";
import PollingService from "../utils/poller.js";
import MetricCard from "../components/MetricCard.js";
import ChartContainer from "../components/ChartContainer.js";
import SkeletonLoader from "../components/SkeletonLoader.js";
import EmptyState from "../components/EmptyState.js";
import createStatsStore from "../stores/stats-store.js";
import toastManager from "../components/Toast.js";
import { escapeHtml } from "../utils/helpers.js";
import { formatNumber, formatPercent } from "../utils/formatters.js";

const POLL_INTERVAL = 15000;
const PAGE_SIZE = 20;
const skeletonLoader = new SkeletonLoader();
const emptyState = new EmptyState();

export default function init() {
  const store = createStatsStore();
  const poller = new PollingService();
  let allCampaigns = [];
  let currentSort = { column: null, dir: null };
  let currentPage = 1;

  // ── DOM Refs ─────────────────────────────────────────────────────

  // KPI card containers
  const sharpeCard = document.getElementById("mc-sharpe");
  const drawdownCard = document.getElementById("mc-drawdown");
  const winrateCard = document.getElementById("mc-winrate");
  const returnCard = document.getElementById("mc-return");

  // Chart containers
  const mainChartEl = document.getElementById("main-chart");
  const drawdownChartEl = document.getElementById("drawdown-chart");
  const winrateChartEl = document.getElementById("winrate-chart");
  const returnChartEl = document.getElementById("return-chart");
  const benchmarkChartEl = document.getElementById("benchmark-chart");

  // Chart title
  const chartTitleEl = document.getElementById("chart-title");

  // Selector and toggle
  const chartTypeSelect = document.getElementById("stats-chart-type");
  const benchmarkToggle = document.getElementById("stats-show-benchmark");

  // Table
  const tableBody = document.getElementById("stats-table-body");
  const paginationEl = document.getElementById("stats-pagination");

  // Filters
  const marketFilter = document.getElementById("stats-market-filter");
  const timeframeFilter = document.getElementById("stats-timeframe-filter");
  const startDateInput = document.getElementById("stats-start-date");
  const endDateInput = document.getElementById("stats-end-date");

  // Empty / error containers
  const emptyContainer = document.getElementById("stats-empty");
  const errorContainer = document.getElementById("stats-error");
  const kpiSkeleton = document.getElementById("stats-kpi-skeleton");
  const mainChartSkeleton = document.getElementById("stats-main-chart-skeleton");
  const gridSkeleton = document.getElementById("stats-grid-skeleton");

  // ── Chart Instances ──────────────────────────────────────────────

  let mainChart = null;
  let drawdownChart = null;
  let winrateChart = null;
  let returnChart = null;
  let benchmarkChart = null;

  // ── Barchart Colors ──────────────────────────────────────────────

  const HIST_COLORS = [
    "#58a6ff", "#3fb950", "#f85149", "#d29922", "#a371f7", "#79c0ff",
  ];

  // ── State Machine ────────────────────────────────────────────────

  function setLoading() {
    // Show skeleton for KPI cards
    if (kpiSkeleton) {
      kpiSkeleton.style.display = "";
      kpiSkeleton.innerHTML = skeletonLoader.render("card", 4);
    }
    // Show skeleton for main chart
    if (mainChartSkeleton) {
      mainChartSkeleton.style.display = "";
    }
    // Show skeleton for 4-chart grid
    if (gridSkeleton) {
      gridSkeleton.style.display = "";
      gridSkeleton.innerHTML = skeletonLoader.render("chart", 4);
    }
    // Hide other states
    if (errorContainer) errorContainer.style.display = "none";
    if (emptyContainer) emptyContainer.style.display = "none";
  }

  function setError(message) {
    if (kpiSkeleton) kpiSkeleton.style.display = "none";
    if (mainChartSkeleton) mainChartSkeleton.style.display = "none";
    if (gridSkeleton) gridSkeleton.style.display = "none";

    if (errorContainer) {
      errorContainer.style.display = "";
      errorContainer.innerHTML = `
        <div class="data-table__error" role="alert">
          <p>${escapeHtml(message || "Failed to load statistics data")}</p>
          <button class="btn btn--primary btn-sm" id="stats-retry-btn">Retry</button>
        </div>
      `;
      const retryBtn = document.getElementById("stats-retry-btn");
      if (retryBtn) {
        retryBtn.addEventListener("click", () => fetchStats());
      }
    }
  }

  function setEmpty() {
    if (kpiSkeleton) kpiSkeleton.style.display = "none";
    if (mainChartSkeleton) mainChartSkeleton.style.display = "none";
    if (gridSkeleton) gridSkeleton.style.display = "none";

    if (emptyContainer) {
      emptyContainer.style.display = "";
      emptyContainer.innerHTML = emptyState.render({
        title: "No Statistics Data Available",
        text: "Statistics will appear here once campaigns have been completed and results are aggregated.",
      });
    }
  }

  function setLoaded(stats) {
    if (kpiSkeleton) kpiSkeleton.style.display = "none";
    if (mainChartSkeleton) mainChartSkeleton.style.display = "none";
    if (gridSkeleton) gridSkeleton.style.display = "none";
    if (errorContainer) errorContainer.style.display = "none";
    if (emptyContainer) emptyContainer.style.display = "none";

    allCampaigns = stats.campaigns || [];
    renderKpiCards(stats);
    renderMainChart(stats);
    renderChartGrid(stats);
    renderTable();
  }

  // ── KPI Cards ────────────────────────────────────────────────────

  function renderKpiCards(stats) {
    new MetricCard(sharpeCard, {
      metricType: "sharpe",
      label: "Avg Sharpe",
      value: stats.avg_sharpe,
    }).render();

    new MetricCard(drawdownCard, {
      metricType: "drawdown",
      label: "Avg Drawdown",
      value: stats.avg_drawdown,
    }).render();

    new MetricCard(winrateCard, {
      metricType: "winrate",
      label: "Avg Win Rate",
      value: stats.avg_win_rate,
    }).render();

    new MetricCard(returnCard, {
      metricType: "return",
      label: "Avg Return",
      value: stats.avg_return,
    }).render();
  }

  // ── Main Chart ───────────────────────────────────────────────────

  function getChartTypeTitle(type) {
    const titles = {
      sharpe: "Sharpe Ratio Distribution",
      drawdown: "Max Drawdown Distribution",
      winrate: "Win Rate Distribution",
      return: "Total Return Distribution",
      benchmark: "Benchmark Comparison",
    };
    return titles[type] || "Sharpe Ratio Distribution";
  }

  function buildHistogramTrace(values, label) {
    const valid = (values || []).filter((v) => v != null && isFinite(v));
    if (valid.length === 0) {
      return [{ type: "histogram", x: [0], marker: { color: HIST_COLORS[0] }, opacity: 0.3 }];
    }
    return [
      {
        type: "histogram",
        x: valid,
        marker: {
          color: HIST_COLORS[0],
          line: { color: HIST_COLORS[1], width: 1 },
        },
        opacity: 0.85,
        name: label,
      },
    ];
  }

  function buildBenchmarkTrace(campaigns, benchmark) {
    if (!campaigns || campaigns.length === 0 || !benchmark) {
      return [{ type: "histogram", x: [0], marker: { color: HIST_COLORS[0] }, opacity: 0.3 }];
    }

    const campaignSharpe = campaigns.map((c) => c.sharpe).filter((v) => v != null && isFinite(v));
    const benchmarkSharpe = benchmark.sharpe_values || [];

    const traces = [];
    if (campaignSharpe.length > 0) {
      traces.push({
        type: "histogram",
        x: campaignSharpe,
        name: "Campaigns",
        marker: { color: HIST_COLORS[0] },
        opacity: 0.7,
      });
    }
    if (benchmarkSharpe.length > 0) {
      traces.push({
        type: "histogram",
        x: benchmarkSharpe,
        name: "Benchmark",
        marker: { color: HIST_COLORS[2] },
        opacity: 0.5,
      });
    }
    if (traces.length === 0) {
      traces.push({ type: "histogram", x: [0], marker: { color: HIST_COLORS[0] }, opacity: 0.3 });
    }
    return traces;
  }

  function getMainChartTraces(stats) {
    const type = store.getState().chartType || "sharpe";
    const showBench = store.getState().showBenchmark;

    if (type === "benchmark" || (type === "sharpe" && showBench)) {
      return buildBenchmarkTrace(stats.campaigns, stats.benchmark);
    }

    let values = [];
    switch (type) {
      case "sharpe":
        values = (stats.campaigns || []).map((c) => c.sharpe);
        break;
      case "drawdown":
        values = (stats.campaigns || []).map((c) => c.max_drawdown);
        break;
      case "winrate":
        values = (stats.campaigns || []).map((c) => c.win_rate);
        break;
      case "return":
        values = (stats.campaigns || []).map((c) => c.total_return);
        break;
      default:
        values = (stats.campaigns || []).map((c) => c.sharpe);
    }
    return buildHistogramTrace(values, getChartTypeTitle(type));
  }

  function renderMainChart(stats) {
    if (!mainChartEl) return;

    const title = getChartTypeTitle(store.getState().chartType || "sharpe");
    if (chartTitleEl) {
      chartTitleEl.textContent = title;
    }

    if (!mainChart) {
      mainChart = new ChartContainer("main-chart", {});
    }

    const traces = getMainChartTraces(stats);
    mainChart.init(traces, {
      title: { text: "", font: { size: 14 } },
      xaxis: { title: { text: title } },
      yaxis: { title: { text: "Count" } },
      barmode: store.getState().showBenchmark ? "overlay" : "stack",
      height: 500,
    });
  }

  function updateMainChart(stats) {
    if (!mainChartEl) return;

    const title = getChartTypeTitle(store.getState().chartType || "sharpe");
    if (chartTitleEl) {
      chartTitleEl.textContent = title;
    }

    const traces = getMainChartTraces(stats);
    const layout = {
      title: { text: "", font: { size: 14 } },
      xaxis: { title: { text: title } },
      yaxis: { title: { text: "Count" } },
      barmode: store.getState().showBenchmark ? "overlay" : "stack",
      height: 500,
    };

    if (mainChart) {
      mainChart.update(traces, layout);
    } else {
      mainChart = new ChartContainer("main-chart", {});
      mainChart.init(traces, layout);
    }
  }

  // ── Chart Grid ───────────────────────────────────────────────────

  function getOrInitChart(containerId, containerVar, traceData, layoutOverrides) {
    // Reuse existing instance to avoid duplicate ResizeObservers
    if (containerVar) {
      containerVar.update(traceData, layoutOverrides);
      return containerVar;
    }
    const chart = new ChartContainer(containerId, {});
    chart.init(traceData, layoutOverrides);
    return chart;
  }

  function renderChartGrid(stats) {
    const distributions = stats.distributions || {};
    const campaigns = stats.campaigns || [];

    // Drawdown Distribution
    if (drawdownChartEl) {
      const ddValues = distributions.drawdown || campaigns.map((c) => c.max_drawdown).filter(Boolean);
      drawdownChart = getOrInitChart("drawdown-chart", drawdownChart, buildHistogramTrace(ddValues, "Max Drawdown"), {
        title: { text: "Drawdown Distribution", font: { size: 12 } },
        height: 350,
      });
    }

    // Win Rate Distribution
    if (winrateChartEl) {
      const wrValues = distributions.win_rate || campaigns.map((c) => c.win_rate).filter(Boolean);
      winrateChart = getOrInitChart("winrate-chart", winrateChart, buildHistogramTrace(wrValues, "Win Rate"), {
        title: { text: "Win Rate Distribution", font: { size: 12 } },
        height: 350,
      });
    }

    // Return Distribution
    if (returnChartEl) {
      const retValues = distributions.return || campaigns.map((c) => c.total_return).filter(Boolean);
      returnChart = getOrInitChart("return-chart", returnChart, buildHistogramTrace(retValues, "Total Return"), {
        title: { text: "Return Distribution", font: { size: 12 } },
        height: 350,
      });
    }

    // Benchmark Comparison
    if (benchmarkChartEl) {
      const benchTraces = buildBenchmarkTrace(campaigns, stats.benchmark);
      benchmarkChart = getOrInitChart("benchmark-chart", benchmarkChart, benchTraces, {
        title: { text: "Benchmark Comparison", font: { size: 12 } },
        barmode: "overlay",
        height: 350,
      });
    }
  }

  // ── Stats Table ──────────────────────────────────────────────────

  function sortCampaigns(campaigns) {
    if (!currentSort.column || !currentSort.dir) return campaigns;
    return [...campaigns].sort((a, b) => {
      const aVal = a[currentSort.column] ?? "";
      const bVal = b[currentSort.column] ?? "";
      if (typeof aVal === "string") {
        const cmp = aVal.localeCompare(bVal);
        return currentSort.dir === "asc" ? cmp : -cmp;
      }
      return currentSort.dir === "asc" ? aVal - bVal : bVal - aVal;
    });
  }

  function filterCampaigns(campaigns) {
    const filters = store.getState().filters;
    if (!filters) return campaigns;

    return campaigns.filter((c) => {
      if (filters.market && c.market !== filters.market) return false;
      if (filters.timeframe && c.timeframe !== filters.timeframe) return false;
      if (filters.startDate && c.date && c.date < filters.startDate) return false;
      if (filters.endDate && c.date && c.date > filters.endDate) return false;
      return true;
    });
  }

  function renderTable() {
    if (!tableBody) return;

    let campaigns = filterCampaigns(allCampaigns);
    campaigns = sortCampaigns(campaigns);

    if (campaigns.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="9" class="data-table__empty">
            ${allCampaigns.length === 0
              ? "No campaign data available."
              : "No campaigns match the current filters."}
          </td>
        </tr>
      `;
      if (paginationEl) paginationEl.style.display = "none";
      return;
    }

    // Paginate
    const totalPages = Math.max(1, Math.ceil(campaigns.length / PAGE_SIZE));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * PAGE_SIZE;
    const paged = campaigns.slice(start, start + PAGE_SIZE);

    // Build rows
    let html = "";
    for (const c of paged) {
      const returnClass = (c.total_return || 0) >= 0
        ? "data-table__cell--positive"
        : "data-table__cell--negative";

      html += `
        <tr class="data-table__row">
          <td class="data-table__cell" data-label="Campaign">${escapeHtml(c.name || c.id || "—")}</td>
          <td class="data-table__cell" data-label="Market">${escapeHtml(c.market || "—")}</td>
          <td class="data-table__cell" data-label="Timeframe">${escapeHtml(c.timeframe || "—")}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Sharpe">${c.sharpe != null ? c.sharpe.toFixed(2) : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Max DD">${c.max_drawdown != null ? c.max_drawdown.toFixed(2) + "%" : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Win Rate">${c.win_rate != null ? (c.win_rate * 100).toFixed(1) + "%" : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Profit Factor">${c.profit_factor != null ? c.profit_factor.toFixed(2) : "—"}</td>
          <td class="data-table__cell data-table__cell--number ${returnClass}" data-label="Total Return">${c.total_return != null ? c.total_return.toFixed(2) : "—"}</td>
          <td class="data-table__cell data-table__cell--number" data-label="Trades">${c.trade_count != null ? c.trade_count : "—"}</td>
        </tr>
      `;
    }

    tableBody.innerHTML = html;
    renderPagination(campaigns.length, totalPages);
  }

  function renderPagination(totalItems, totalPages) {
    if (!paginationEl) return;

    paginationEl.innerHTML = `
      <span class="data-table__pagination-info">Page ${currentPage} of ${totalPages} (${totalItems} campaigns)</span>
      <button class="btn btn--sm ${currentPage <= 1 ? "btn--disabled" : "btn--secondary"}"
        id="prev-page-btn" ${currentPage <= 1 ? "disabled" : ""}>Previous</button>
      <button class="btn btn--sm ${currentPage >= totalPages ? "btn--disabled" : "btn--secondary"}"
        id="next-page-btn" ${currentPage >= totalPages ? "disabled" : ""}>Next</button>
    `;

    const prevBtn = document.getElementById("prev-page-btn");
    const nextBtn = document.getElementById("next-page-btn");

    if (prevBtn && currentPage > 1) {
      prevBtn.addEventListener("click", () => {
        currentPage--;
        renderTable();
      });
    }
    if (nextBtn && currentPage < totalPages) {
      nextBtn.addEventListener("click", () => {
        currentPage++;
        renderTable();
      });
    }

    paginationEl.style.display = "";
  }

  // ── Data Loading ─────────────────────────────────────────────────

  async function fetchStats() {
    setLoading();

    const filters = store.getState().filters;
    const params = new URLSearchParams();
    if (filters.market) params.set("market", filters.market);
    if (filters.timeframe) params.set("timeframe", filters.timeframe);
    if (filters.startDate) params.set("start_date", filters.startDate);
    if (filters.endDate) params.set("end_date", filters.endDate);

    const queryStr = params.toString();
    const url = "/api/stats" + (queryStr ? "?" + queryStr : "");
    const result = await apiGet(url);

    if (!result.success) {
      store.notify("error", result.error);
      setError(result.error);
      toastManager.show({
        type: "error",
        message: "Failed to load statistics: " + (result.error || "Unknown error"),
      });
      return;
    }

    const stats = result.data || {};
    store.loadStats(stats);

    if (!stats.avg_sharpe && !stats.avg_drawdown && !stats.campaigns?.length) {
      setEmpty();
    } else {
      setLoaded(stats);
      const campaignCount = (stats.campaigns || []).length;
      if (campaignCount > 0) {
        toastManager.show({
          type: "success",
          message: `Loaded statistics for ${campaignCount} campaign${campaignCount !== 1 ? "s" : ""}`,
        });
      }
    }
  }

  // ── Chart Type Selector ──────────────────────────────────────────

  if (chartTypeSelect) {
    chartTypeSelect.addEventListener("change", () => {
      const type = chartTypeSelect.value;
      store.setChartType(type);

      // Re-render main chart with stored stats
      const stats = store.getState().stats;
      if (stats) {
        updateMainChart(stats);
      }
    });
  }

  // ── Benchmark Toggle ─────────────────────────────────────────────

  if (benchmarkToggle) {
    benchmarkToggle.addEventListener("change", () => {
      store.toggleBenchmark();

      // Re-render main chart with stored stats
      const stats = store.getState().stats;
      if (stats) {
        updateMainChart(stats);
      }
    });
  }

  // ── Filter Changes ───────────────────────────────────────────────

  function handleFilterChange() {
    if (marketFilter) store.setFilter("market", marketFilter.value);
    if (timeframeFilter) store.setFilter("timeframe", timeframeFilter.value);
    if (startDateInput) store.setFilter("startDate", startDateInput.value);
    if (endDateInput) store.setFilter("endDate", endDateInput.value);

    // Re-fetch with new filters
    currentPage = 1;
    fetchStats();
  }

  if (marketFilter) {
    marketFilter.addEventListener("change", handleFilterChange);
  }
  if (timeframeFilter) {
    timeframeFilter.addEventListener("change", handleFilterChange);
  }
  if (startDateInput) {
    startDateInput.addEventListener("change", handleFilterChange);
  }
  if (endDateInput) {
    endDateInput.addEventListener("change", handleFilterChange);
  }

  // ── Init ─────────────────────────────────────────────────────────

  setLoading();
  fetchStats();

  // Start polling at 15s interval
  poller.start("/api/stats", POLL_INTERVAL, (data) => {
    const stats = data || {};
    store.loadStats(stats);

    if (!stats.avg_sharpe && !stats.avg_drawdown && !stats.campaigns?.length) {
      setEmpty();
    } else {
      allCampaigns = stats.campaigns || [];
      renderKpiCards(stats);
      updateMainChart(stats);
      renderChartGrid(stats);
      renderTable();
    }
  });

  // Cleanup on page navigation
  window.addEventListener("beforeunload", () => {
    poller.stop();
  });
}
