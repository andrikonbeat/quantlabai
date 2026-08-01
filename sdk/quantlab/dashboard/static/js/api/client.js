/**
 * API Client — fetch with retry, AbortController, timeout
 * Returns { success, data, error }
 */

const DEFAULT_TIMEOUT = 15000;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

/**
 * Fetch wrapper with timeout and retry logic.
 * @param {string} url
 * @param {object} options - fetch options
 * @param {number} [retries=MAX_RETRIES]
 * @returns {Promise<{success: boolean, data: any, error: string|null}>}
 */
async function apiFetch(url, options = {}, retries = MAX_RETRIES) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT);

  try {
    const response = await fetch(url, {
      ...options,
      signal: options.signal
        ? combineSignals(options.signal, controller.signal)
        : controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error");
      return { success: false, data: null, error: `HTTP ${response.status}: ${errorText}` };
    }

    const data = await response.json();
    return { success: true, data, error: null };
  } catch (err) {
    clearTimeout(timeoutId);

    if (err.name === "AbortError") {
      return { success: false, data: null, error: "Request timed out or was cancelled" };
    }

    if (retries > 0) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY));
      return apiFetch(url, options, retries - 1);
    }

    return { success: false, data: null, error: err.message || "Network error" };
  }
}

/**
 * Combine two AbortSignals into one.
 */
function combineSignals(signal1, signal2) {
  const controller = new AbortController();

  const onAbort = () => controller.abort();
  signal1.addEventListener("abort", onAbort);
  signal2.addEventListener("abort", onAbort);

  if (signal1.aborted || signal2.aborted) {
    controller.abort();
  }

  return controller.signal;
}

/**
 * GET request.
 * @param {string} url
 * @param {{ signal?: AbortSignal }} [opts]
 * @returns {Promise<{success: boolean, data: any, error: string|null}>}
 */
export function apiGet(url, opts = {}) {
  return apiFetch(url, { method: "GET", ...opts });
}

/**
 * POST request.
 * @param {string} url
 * @param {object} body
 * @param {{ signal?: AbortSignal }} [opts]
 * @returns {Promise<{success: boolean, data: any, error: string|null}>}
 */
export function apiPost(url, body, opts = {}) {
  return apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...opts,
  });
}
