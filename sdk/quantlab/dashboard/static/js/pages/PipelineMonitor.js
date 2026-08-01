/**
 * PipelineMonitor — Page module for pipeline monitoring.
 * Orchestrates overview stats, run table, stage detail, log viewer.
 */
import { apiGet } from "../api/client.js";
import PollingService from "../utils/poller.js";
import StatusBadge from "../components/StatusBadge.js";
import SkeletonLoader from "../components/SkeletonLoader.js";
import EmptyState from "../components/EmptyState.js";
import createPipelineStore from "../stores/pipeline-store.js";
import toastManager from "../components/Toast.js";
import { escapeHtml } from "../utils/helpers.js";

const POLL_INTERVAL = 10000;
const statusBadge = new StatusBadge();
const skeletonLoader = new SkeletonLoader();
const emptyState = new EmptyState();

export default function init() {
  const store = createPipelineStore();
  const poller = new PollingService();
  let currentData = [];

  // ── DOM Refs ─────────────────────────────────────────────────────

  const overviewEl = document.getElementById("pipeline-overview");
  const tableBody = document.getElementById("pipeline-table-body");
  const stageDetailEl = document.getElementById("stage-detail");
  const stageProgressEl = document.getElementById("stage-progress");
  const stageLogEl = document.getElementById("stage-log");
  const stageRunTitle = document.getElementById("stage-run-title");
  const refreshBtn = document.getElementById("refresh-pipeline-btn");
  const refreshIcon = refreshBtn ? refreshBtn.querySelector("svg") : null;

  // ── State Machine ────────────────────────────────────────────────

  function setLoading() {
    if (overviewEl) {
      overviewEl.innerHTML = `
        <div class="overview-stats" aria-busy="true">
          ${skeletonLoader.render("metric", 4)}
        </div>
      `;
    }
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="7">${skeletonLoader.render("row", 5)}</td></tr>`;
    }
  }

  function setError(message) {
    if (overviewEl) {
      overviewEl.innerHTML = `
        <div class="data-table__error" role="alert">
          <p>${escapeHtml(message || "Failed to load pipeline runs")}</p>
          <button class="btn btn--primary btn-sm" onclick="window.location.reload()">Retry</button>
        </div>
      `;
    }
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="data-table__error" role="alert">
              <p>${escapeHtml(message || "Failed to load pipeline data")}</p>
              <button class="btn btn--primary btn-sm" id="retry-table-btn">Retry</button>
            </div>
          </td>
        </tr>
      `;
      const retryBtn = document.getElementById("retry-table-btn");
      if (retryBtn) {
        retryBtn.addEventListener("click", () => fetchRuns());
      }
    }
  }

  function setEmpty() {
    if (overviewEl) {
      overviewEl.innerHTML = "";
    }
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7">
            ${emptyState.render({
              title: "No Pipeline Runs Yet",
              text: "Pipeline runs will appear here once you start backtesting or deploying strategies.",
            })}
          </td>
        </tr>
      `;
    }
  }

  function setLoaded(runs) {
    currentData = runs;
    renderOverview(runs);
    renderTable(runs);
  }

  // ── Rendering ────────────────────────────────────────────────────

  function renderOverview(runs) {
    if (!overviewEl) return;
    const total = runs.length;
    const running = runs.filter((r) => r.status === "running").length;
    const success = runs.filter((r) => r.status === "completed" || r.status === "success").length;
    const failed = runs.filter((r) => r.status === "failed").length;

    overviewEl.innerHTML = `
      <div class="overview-stats" aria-label="Pipeline overview statistics">
        <div class="stat-card">
          <span class="stat-card__value">${total}</span>
          <span class="stat-card__label">Total Runs</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__value" style="color: var(--color-primary);">${running}</span>
          <span class="stat-card__label">Running</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__value" style="color: var(--color-success);">${success}</span>
          <span class="stat-card__label">Success</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__value" style="color: var(--color-danger);">${failed}</span>
          <span class="stat-card__label">Failed</span>
        </div>
      </div>
    `;
  }

  function renderTable(runs) {
    if (!tableBody) return;
    if (runs.length === 0) {
      setEmpty();
      return;
    }

    // Build all rows first
    const fragment = document.createDocumentFragment();
    for (const run of runs) {
      const tr = document.createElement("tr");
      tr.className = "data-table__row data-table__row--clickable";
      tr.dataset.id = run.id || run.run_id || "";
      tr.dataset.runId = run.id || run.run_id || "";

      const stageDots = (run.stages || [])
        .map((s) => {
          const dotClass = s.status === "completed" || s.status === "success"
            ? "stage-dot--success"
            : s.status === "failed" ? "stage-dot--failed"
            : s.status === "running" ? "stage-dot--running"
            : "stage-dot--pending";
          return `<span class="stage-dot ${dotClass}" title="${escapeHtml(s.name || "")}: ${escapeHtml(s.status || "pending")}"></span>`;
        })
        .join("");

      tr.innerHTML = `
        <td class="data-table__cell run-id" data-label="Run ID">${escapeHtml(run.id || run.run_id || "—")}</td>
        <td class="data-table__cell" data-label="Pipeline">${escapeHtml(run.pipeline || run.name || "—")}</td>
        <td class="data-table__cell" data-label="Status">
          ${statusBadge.render(run.status || "pending")}
        </td>
        <td class="data-table__cell" data-label="Started">${escapeHtml(run.started_at || "—")}</td>
        <td class="data-table__cell" data-label="Duration">${escapeHtml(run.duration || "—")}</td>
        <td class="data-table__cell stage-cell" data-label="Stages">
          <span class="stage-dots">${stageDots}</span>
        </td>
        <td class="data-table__cell" data-label="Actions">
          <button class="btn btn--secondary btn-sm view-stages-btn" data-run-id="${escapeHtml(run.id || run.run_id || "")}">View Stages</button>
        </td>
      `;

      // Click handler for "View Stages"
      const viewBtn = tr.querySelector(".view-stages-btn");
      viewBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const runId = viewBtn.dataset.runId;
        store.selectRun(runId);
        loadStageDetail(runId, runs);
      });

      fragment.appendChild(tr);
    }

    tableBody.innerHTML = "";
    tableBody.appendChild(fragment);
  }

  function renderStageProgress(stages) {
    if (!stageProgressEl) return;
    stageProgressEl.innerHTML = stages
      .map(
        (s) => `
      <div class="stage-item">
        <span class="status-badge__icon">${statusBadge.getIcon(s.status || "pending")}</span>
        <span class="stage-item__name">${escapeHtml(s.name || "Unknown Stage")}</span>
        <span class="stage-item__duration">${escapeHtml(s.duration || "—")}</span>
        ${s.error ? `<span class="stage-item__error">${escapeHtml(s.error)}</span>` : ""}
      </div>
    `
      )
      .join("");
  }

  function renderLog(logs) {
    if (!stageLogEl) return;
    const logText = Array.isArray(logs) ? logs.join("\n") : logs || "";
    stageLogEl.textContent = logText;

    // Auto-scroll to bottom
    requestAnimationFrame(() => {
      if (stageLogEl.parentElement) {
        stageLogEl.parentElement.scrollTop = stageLogEl.parentElement.scrollHeight;
      }
    });
  }

  // ── Data Loading ─────────────────────────────────────────────────

  async function fetchRuns() {
    // Spinning animation on refresh icon
    if (refreshIcon) {
      refreshIcon.classList.add("spinning");
    }

    const result = await apiGet("/api/pipeline");

    if (refreshIcon) {
      refreshIcon.classList.remove("spinning");
    }

    if (!result.success) {
      store.notify("error", result.error);
      setError(result.error);
      toastManager.show({
        type: "error",
        message: "Failed to load pipeline runs: " + (result.error || "Unknown error"),
      });
      return;
    }

    const runs = result.data || [];
    store.loadRuns(runs);

    if (runs.length === 0) {
      setEmpty();
    } else {
      setLoaded(runs);
      toastManager.show({
        type: "success",
        message: `Loaded ${runs.length} pipeline run${runs.length !== 1 ? "s" : ""}`,
      });
    }
  }

  async function loadStageDetail(runId, runs) {
    if (!stageDetailEl) return;

    const run = runs.find((r) => (r.id || r.run_id || "") === runId);
    if (!run) return;

    if (stageRunTitle) {
      stageRunTitle.textContent = `Stage Details — ${escapeHtml(run.pipeline || run.name || runId)}`;
    }

    // Show detail panel
    stageDetailEl.classList.remove("hidden");

    // Render stages
    if (run.stages) {
      renderStageProgress(run.stages);
    } else {
      if (stageProgressEl) stageProgressEl.innerHTML = "<p>No stage data available.</p>";
    }

    // Load logs
    const result = await apiGet(`/api/pipeline/${encodeURIComponent(runId)}`);
    if (result.success && result.data) {
      renderLog(result.data.logs || []);

      // Also update stages from full detail
      if (result.data.stages) {
        renderStageProgress(result.data.stages);
      }
    } else {
      if (stageLogEl) {
        stageLogEl.textContent = result.error || "Failed to load logs.";
      }
    }
  }

  // ── Event Binding ────────────────────────────────────────────────

  // Refresh button
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      fetchRuns();
    });
  }

  // Close stage detail
  const closeBtn = document.getElementById("close-stage-detail");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (stageDetailEl) stageDetailEl.classList.add("hidden");
      store.selectRun(null);
    });
  }

  // Clear log
  const clearBtn = document.getElementById("clear-log");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (stageLogEl) stageLogEl.textContent = "";
    });
  }

  // Search filter
  const searchInput = document.getElementById("pipeline-search");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.toLowerCase();
      const rows = tableBody ? tableBody.querySelectorAll(".data-table__row") : [];
      for (const row of rows) {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? "" : "none";
      }
    });
  }

  // Status filter
  const statusFilter = document.getElementById("pipeline-status-filter");
  if (statusFilter) {
    statusFilter.addEventListener("change", () => {
      const filterVal = statusFilter.value.toLowerCase();
      store.setFilter(filterVal);

      let filtered = currentData;
      if (filterVal) {
        filtered = currentData.filter(
          (r) => (r.status || "").toLowerCase() === filterVal
        );
      }
      renderTable(filtered);
    });
  }

  // ── Init ─────────────────────────────────────────────────────────

  setLoading();
  fetchRuns();

  // Start polling
  poller.start("/api/pipeline", POLL_INTERVAL, (data) => {
    const runs = data || [];
    store.loadRuns(runs);
    if (runs.length === 0) {
      setEmpty();
    } else {
      renderOverview(runs);
      renderTable(runs);
    }
  });

  // Cleanup on page navigation
  window.addEventListener("beforeunload", () => {
    poller.stop();
  });
}
