/**
 * Campaign List Page — orchestrates data fetching, store, and components.
 */
import { apiGet } from "../api/client.js";
import store from "../stores/campaign-store.js";
import PollingService from "../utils/poller.js";
import debounce from "../utils/debounce.js";
import Sidebar from "../components/Sidebar.js";
import DataTable from "../components/DataTable.js";
import SkeletonLoader from "../components/SkeletonLoader.js";
import EmptyState from "../components/EmptyState.js";

export default function init() {
  const tableBody = document.getElementById("campaign-table-body");
  const sidebarEl = document.getElementById("campaign-list-sidebar");
  const searchInput = document.getElementById("campaign-search");
  const statusFilter = document.getElementById("status-filter");
  const marketFilter = document.getElementById("market-filter");
  const skeletonContainer = document.getElementById("skeleton-container");
  const errorContainer = document.getElementById("error-container");
  const emptyContainer = document.getElementById("empty-container");
  const tableContainer = document.getElementById("table-container");
  const totalEl = document.getElementById("total-campaigns");
  const runningEl = document.getElementById("running-campaigns");
  const completedEl = document.getElementById("completed-campaigns");

  // ── State ──────────────────────────────────────────────────────────
  let currentSort = { column: null, dir: null };
  let currentPage = 1;
  const PAGE_SIZE = 20;

  // ── Component instances ────────────────────────────────────────────
  const sidebar = new Sidebar(sidebarEl);
  const dataTable = new DataTable(tableBody);
  const skeletonLoader = new SkeletonLoader();
  const emptyState = new EmptyState();

  // ── Polling ────────────────────────────────────────────────────────
  const poller = new PollingService();

  // ── Render helper ──────────────────────────────────────────────────
  function render(campaigns) {
    // Update summary stats
    if (totalEl) totalEl.textContent = campaigns.length;
    if (runningEl) runningEl.textContent = campaigns.filter((c) => c.status === "running").length;
    if (completedEl) completedEl.textContent = campaigns.filter((c) => c.status === "completed").length;

    // Apply filters
    const search = store.getState("search");
    const statusF = store.getState("statusFilter");
    const marketF = store.getState("marketFilter");

    let filtered = campaigns.filter((c) => {
      if (search) {
        const q = search.toLowerCase();
        const matchName = (c.name || c.id || "").toLowerCase().includes(q);
        const matchMarket = (c.market || "").toLowerCase().includes(q);
        if (!matchName && !matchMarket) return false;
      }
      if (statusF && c.status !== statusF) return false;
      if (marketF && c.market !== marketF) return false;
      return true;
    });

    // Sort
    if (currentSort.column && currentSort.dir) {
      filtered = filtered.sort((a, b) => {
        const aVal = a[currentSort.column] ?? 0;
        const bVal = b[currentSort.column] ?? 0;
        if (typeof aVal === "string") {
          const cmp = aVal.localeCompare(bVal);
          return currentSort.dir === "asc" ? cmp : -cmp;
        }
        return currentSort.dir === "asc" ? aVal - bVal : bVal - aVal;
      });
    }

    // Pagination
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * PAGE_SIZE;
    const paged = filtered.slice(start, start + PAGE_SIZE);

    // Render sidebar
    if (sidebarEl) {
      const activeId = window.location.pathname.replace("/campaigns/", "");
      sidebar.render(campaigns, activeId);
    }

    // Render table
    if (tableBody) {
      dataTable.render(paged, currentSort, currentPage, totalPages);
    }

    // Show/hide states
    if (skeletonContainer) skeletonContainer.style.display = "none";

    if (filtered.length === 0 && campaigns.length === 0 && !errorContainer) {
      // Empty state
      if (emptyContainer) {
        emptyContainer.style.display = "";
        emptyContainer.innerHTML = emptyState.render({
          title: "No campaigns yet",
          text: "Create your first campaign to start backtesting and analyzing trading strategies.",
          actionLabel: "New Campaign",
          actionUrl: "/campaigns/new",
        });
      }
    } else {
      if (emptyContainer) emptyContainer.style.display = "none";
    }

    // Show table
    if (tableContainer) tableContainer.style.display = "";
    if (errorContainer) errorContainer.style.display = "none";

    // Update filter selects
    const markets = [...new Set(campaigns.map((c) => c.market).filter(Boolean))];
    if (marketFilter) {
      const currentVal = marketFilter.value;
      marketFilter.innerHTML = '<option value="">All Markets</option>' +
        markets.map((m) => `<option value="${m}">${m}</option>`).join("");
      marketFilter.value = currentVal;
    }
  }

  // ── Error handler ──────────────────────────────────────────────────
  function showError(errorMsg) {
    if (skeletonContainer) skeletonContainer.style.display = "none";
    if (tableContainer) tableContainer.style.display = "none";
    if (emptyContainer) emptyContainer.style.display = "none";
    if (errorContainer) {
      errorContainer.style.display = "";
      errorContainer.innerHTML = `
        <div class="data-table__error">
          <p>${errorMsg}</p>
          <button class="btn btn--primary" onclick="window.location.reload()">Retry</button>
        </div>
      `;
    }
  }

  // ── Loading state ──────────────────────────────────────────────────
  function showLoading() {
    if (skeletonContainer) {
      skeletonContainer.innerHTML = skeletonLoader.render("row", 5);
      skeletonContainer.style.display = "";
    }
    if (tableContainer) tableContainer.style.display = "none";
    if (errorContainer) errorContainer.style.display = "none";
    if (emptyContainer) emptyContainer.style.display = "none";
  }

  // ── Data fetch ─────────────────────────────────────────────────────
  async function loadCampaigns() {
    showLoading();
    const result = await apiGet("/api/campaigns");
    if (!result.success) {
      store.setState("loading", false);
      store.setState("error", result.error);
      showError(result.error);
      return;
    }
    const campaigns = result.data || [];
    store.setState("loading", false);
    store.setState("error", null);
    store.setState("campaigns", campaigns);
    render(campaigns);
  }

  // ── Cross-fade transition ──────────────────────────────────────────
  function renderWithFade(campaigns) {
    const tableEl = tableBody?.closest(".data-table");
    if (tableEl) {
      tableEl.style.transition = "opacity var(--duration-slow) var(--ease-in-out)";
      tableEl.style.opacity = "0";
      requestAnimationFrame(() => {
        render(campaigns);
        requestAnimationFrame(() => {
          tableEl.style.opacity = "1";
        });
      });
    } else {
      render(campaigns);
    }
  }

  // ── Init ───────────────────────────────────────────────────────────
  showLoading();
  loadCampaigns();

  // Polling at 10s interval
  poller.start("/api/campaigns", 10000, (data) => {
    if (data) {
      store.setState("campaigns", data);
      renderWithFade(data);
    }
  });

  // Store subscription for filter changes
  store.subscribe("campaigns", (data) => {
    renderWithFade(data);
  });

  // ── Event wiring ───────────────────────────────────────────────────

  // Search with 300ms debounce
  if (searchInput) {
    const debouncedSearch = debounce((e) => {
      store.setState("search", e.target.value);
    }, 300);
    searchInput.addEventListener("input", debouncedSearch);
  }

  // Status filter
  if (statusFilter) {
    statusFilter.addEventListener("change", (e) => {
      store.setState("statusFilter", e.target.value);
    });
  }

  // Market filter
  if (marketFilter) {
    marketFilter.addEventListener("change", (e) => {
      store.setState("marketFilter", e.target.value);
    });
  }

  // Register filter handler after render: when store notifies with filter changes, re-render
  store.subscribe("search", () => {
    const campaigns = store.getState("campaigns") || [];
    render(campaigns);
  });

  store.subscribe("statusFilter", () => {
    const campaigns = store.getState("campaigns") || [];
    render(campaigns);
  });

  store.subscribe("marketFilter", () => {
    const campaigns = store.getState("campaigns") || [];
    render(campaigns);
  });

  // ── Cleanup on page unload ─────────────────────────────────────────
  window.addEventListener("beforeunload", () => {
    poller.stop();
  });
}
