/**
 * ChartContainer — Plotly.react wrapper with loading state, resize handling,
 * and error boundary.
 */
const PLOTLY_GLOBALS = {
  config: {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale", "resetScale2d"],
    modeBarButtonsToAdd: ["drawline", "eraseshape"],
    toImageButtonOptions: {
      format: "svg",
      filename: "quantlab-chart",
      height: 600,
      width: 1200,
    },
  },
  layout: {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: {
      family: "'Inter', system-ui, sans-serif",
      size: 12,
      color: "var(--color-text-secondary)",
    },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: "var(--color-bg-elevated)",
      bordercolor: "var(--color-border)",
      font: {
        family: "'Inter', sans-serif",
        size: 12,
        color: "var(--color-text-primary)",
      },
    },
    xaxis: {
      gridcolor: "var(--color-border-subtle)",
      zerolinecolor: "var(--color-border)",
      tickfont: { size: 11 },
    },
    yaxis: {
      gridcolor: "var(--color-border-subtle)",
      zerolinecolor: "var(--color-border)",
      tickfont: { size: 11 },
    },
    margin: { l: 48, r: 16, t: 24, b: 48 },
    legend: { orientation: "h", y: -0.25, font: { size: 11 } },
    transition: { duration: 300, easing: "cubic-in-out" },
  },
  palette: [
    "#2563EB", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#EC4899", "#06B6D4", "#84CC16",
  ],
};

export default class ChartContainer {
  /**
   * @param {string} containerId - DOM element ID
   * @param {object} [options]
   */
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.el = document.getElementById(containerId);
    if (!this.el) {
      console.warn(`ChartContainer: element #${containerId} not found`);
      return;
    }

    this.wrapper = this.el.closest(".chart-container") || this.el.parentElement;
    this._options = options;
    this._resizeObserver = null;
    this._errorEl = null;

    // Set loading state
    if (this.wrapper) {
      this.wrapper.classList.add("chart-container--loading");
    }
  }

  /**
   * First render using Plotly.react.
   * @param {Array} traceData - Plotly trace data
   * @param {object} [layoutOverrides] - layout overrides
   */
  init(traceData, layoutOverrides = {}) {
    if (!this.el || typeof Plotly === "undefined") {
      this._showError("Chart library not available");
      return;
    }

    const layout = {
      ...PLOTLY_GLOBALS.layout,
      ...layoutOverrides,
      colorway: layoutOverrides.colorway || PLOTLY_GLOBALS.palette,
    };

    try {
      Plotly.react(this.el, traceData, layout, PLOTLY_GLOBALS.config);
      this._setupResizeObserver();
      this._setLoaded();
    } catch (err) {
      console.error("ChartContainer.init error:", err);
      this._showError("Failed to render chart");
    }
  }

  /**
   * Update chart with new trace data using Plotly.react.
   * @param {Array} traceData
   * @param {object} [layoutOverrides]
   */
  update(traceData, layoutOverrides = {}) {
    if (!this.el || typeof Plotly === "undefined") return;

    const layout = {
      ...PLOTLY_GLOBALS.layout,
      ...layoutOverrides,
      colorway: layoutOverrides.colorway || PLOTLY_GLOBALS.palette,
    };

    try {
      Plotly.react(this.el, traceData, layout, PLOTLY_GLOBALS.config);
      this._setLoaded();
    } catch (err) {
      console.error("ChartContainer.update error:", err);
    }
  }

  /**
   * Cleanup — purge Plotly, disconnect observer.
   */
  destroy() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }

    if (this.el && typeof Plotly !== "undefined") {
      try {
        Plotly.purge(this.el);
      } catch (err) {
        console.warn("ChartContainer.destroy:", err);
      }
    }
  }

  // ── Internal ──────────────────────────────────────────────────────

  _setupResizeObserver() {
    if (typeof ResizeObserver === "undefined") return;

    const container = this.wrapper || this.el;
    this._resizeObserver = new ResizeObserver(() => {
      if (this.el && typeof Plotly !== "undefined") {
        Plotly.Plots.resize(this.el);
      }
    });
    this._resizeObserver.observe(container);
  }

  _setLoaded() {
    if (this.wrapper) {
      this.wrapper.classList.remove("chart-container--loading");
      this.wrapper.classList.add("chart-container--loaded");
    }
    if (this._errorEl) {
      this._errorEl.style.display = "none";
    }
  }

  _showError(message) {
    if (this.wrapper) {
      this.wrapper.classList.remove("chart-container--loading");
    }

    // Create or show error element
    if (!this._errorEl) {
      this._errorEl = document.createElement("div");
      this._errorEl.className = "chart-container__error";
      this._errorEl.innerHTML = `<p>${message}</p>`;
      const body = this.wrapper
        ? this.wrapper.querySelector(".chart-container__body") || this.wrapper
        : this.el?.parentElement;
      if (body) body.appendChild(this._errorEl);
    } else {
      this._errorEl.style.display = "";
    }
  }
}
