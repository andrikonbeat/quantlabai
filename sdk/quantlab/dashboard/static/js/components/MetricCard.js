/**
 * MetricCard — renders a KPI metric card with icon, value, label,
 * sparkline, delta indicator, and animated counter.
 */
import { escapeHtml } from "../utils/helpers.js";

const COLOR_THRESHOLDS = {
  sharpe: { good: 1.0, ok: 0.5, bad: 0 },
  drawdown: { good: 5, ok: 15, bad: 15, invert: true },
  winrate: { good: 60, ok: 40, bad: 40 },
  return: { good: 0, ok: -5, bad: -5, invert: false },
};

function getColorClass(value, metricType) {
  const t = COLOR_THRESHOLDS[metricType];
  if (!t || value == null) return "muted";

  if (t.invert) {
    if (value < t.good) return "good";
    if (value < t.ok) return "ok";
    return "bad";
  }
  if (value >= t.good) return "good";
  if (value >= t.ok) return "ok";
  return "bad";
}

function formatMetricValue(value, metricType) {
  if (value == null) return "—";
  switch (metricType) {
    case "sharpe":
      return value.toFixed(2);
    case "drawdown":
      return value.toFixed(1) + "%";
    case "winrate":
      return (value * 100).toFixed(1) + "%";
    case "return":
      return value.toFixed(2);
    default:
      return String(value);
  }
}

/**
 * Generate a sparkline SVG with 7 data points.
 * @param {number[]} points - array of 7 numbers
 * @returns {string} SVG markup
 */
function renderSparkline(points) {
  if (!points || points.length < 2) return "";

  const width = 100;
  const height = 24;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const xStep = width / (points.length - 1);
  const pts = points
    .map((p, i) => {
      const x = i * xStep;
      const y = height - ((p - min) / range) * (height - 2) - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const polyPoints = `${pts} ${width},${height} 0,${height}`;

  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="sparkline-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="currentColor" stop-opacity="0.01"/>
        </linearGradient>
      </defs>
      <polyline points="${pts}"/>
      <polygon points="${polyPoints}"/>
    </svg>
  `;
}

function renderDelta(value, metricType) {
  if (value == null) return "";
  const cls = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
  const arrow = value > 0 ? "↑" : value < 0 ? "↓" : "→";
  return `<span class="metric-card__delta metric-card__delta--${cls}">${arrow}${Math.abs(value).toFixed(1)}</span>`;
}

const SVG_ICONS = {
  sharpe:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  drawdown:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  winrate:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
  return:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
};

export default class MetricCard {
  /**
   * @param {string|Element} container - container selector or element
   * @param {object} opts
   * @param {string} opts.metricType - 'sharpe' | 'drawdown' | 'winrate' | 'return'
   * @param {string} opts.label
   * @param {number|null} opts.value
   * @param {number[]} [opts.sparkline] - 7 data points
   * @param {number} [opts.delta] - delta value
   */
  constructor(container, opts = {}) {
    this.container = typeof container === "string"
      ? document.querySelector(container)
      : container;
    this.opts = opts;
    this._currentValue = 0;
  }

  /**
   * Render the metric card.
   */
  render() {
    if (!this.container) return;
    const { metricType = "sharpe", label = "", value = null, sparkline, delta } = this.opts;

    if (value == null) {
      this._renderLoading();
      return;
    }

    const colorClass = getColorClass(value, metricType);
    const formattedValue = formatMetricValue(value, metricType);
    const iconName = metricType;
    const iconSvg = SVG_ICONS[iconName] || SVG_ICONS.sharpe;
    const sparklineHtml = sparkline ? renderSparkline(sparkline) : "";
    const deltaHtml = renderDelta(delta, metricType);

    this.container.innerHTML = `
      <div class="metric-card">
        <div class="metric-card__icon metric-card__icon--${iconName}">${iconSvg}</div>
        <div class="metric-card__content">
          <span class="metric-card__label">${escapeHtml(label)}</span>
          <span class="metric-card__value metric-card__value--${colorClass}" id="mc-${iconName}-value">${formattedValue}</span>
          ${deltaHtml}
          ${sparklineHtml ? `<div class="metric-card__sparkline">${sparklineHtml}</div>` : ""}
        </div>
      </div>
    `;

    // Animate counter
    this._animateCounter(value, metricType);
  }

  /**
   * Update the card with new data.
   * @param {object} data
   */
  update(data) {
    this.opts = { ...this.opts, ...data };
    this.render();
  }

  // ── Internal ──────────────────────────────────────────────────────

  _renderLoading() {
    this.container.innerHTML = `
      <div class="metric-card metric-card--loading">
        <div class="metric-card__icon">
          <div class="skeleton skeleton--text" style="width:20px;height:20px;border-radius:50%;"></div>
        </div>
        <div class="metric-card__content">
          <span class="metric-card__label">${escapeHtml(this.opts.label || "")}</span>
          <span class="metric-card__value"></span>
        </div>
      </div>
    `;
  }

  _animateCounter(targetValue, metricType) {
    const valueEl = this.container.querySelector(`#mc-${metricType}-value`);
    if (!valueEl) return;

    const start = this._currentValue;
    const end = targetValue || 0;
    const duration = 600;
    const startTime = performance.now();

    const step = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * eased;

      if (metricType === "drawdown") {
        valueEl.textContent = current.toFixed(1) + "%";
      } else if (metricType === "winrate") {
        valueEl.textContent = (current * 100).toFixed(1) + "%";
      } else {
        valueEl.textContent = current.toFixed(2);
      }

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        this._currentValue = end;
        // Final formatted value
        valueEl.textContent = formatMetricValue(end, metricType);
      }
    };

    requestAnimationFrame(step);
  }
}
