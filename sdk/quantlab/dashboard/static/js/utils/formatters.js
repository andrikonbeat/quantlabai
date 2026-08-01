/**
 * Formatters — locale-aware number/date formatting utilities.
 */

/**
 * Format a number with locale separators and optional decimals.
 * @param {number} n
 * @param {number} [decimals=2]
 * @returns {string}
 */
export function formatNumber(n, decimals = 2) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format as percentage string.
 * @param {number} n - decimal (e.g. 0.25 → "25.00%")
 * @param {number} [decimals=2]
 * @returns {string}
 */
export function formatPercent(n, decimals = 2) {
  if (n == null || isNaN(n)) return "—";
  return (n * 100).toFixed(decimals) + "%";
}

/**
 * Format as currency with symbol.
 * @param {number} n
 * @param {string} [currency="USD"]
 * @returns {string}
 */
export function formatCurrency(n, currency = "USD") {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Format ISO date string to human-readable.
 * @param {string} isoStr - ISO 8601 string
 * @returns {string}
 */
export function formatDate(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

/**
 * Format seconds to human-readable duration.
 * @param {number} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds) || seconds < 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  if (h === 0) return `${remM}m ${s}s`;
  return `${h}h ${remM}m`;
}
