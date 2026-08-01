/**
 * Debounce — standard debounce with leading option.
 * @param {Function} fn - function to debounce
 * @param {number} ms - delay in milliseconds
 * @param {{ leading?: boolean }} [options]
 * @returns {Function} debounced function
 */
export default function debounce(fn, ms, options = {}) {
  let timeoutId = null;
  let leadingInvoked = false;

  const { leading = false } = options;

  const debounced = function (...args) {
    const invokeNow = leading && !leadingInvoked;

    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }

    if (invokeNow) {
      leadingInvoked = true;
      fn.apply(this, args);
    }

    timeoutId = setTimeout(() => {
      leadingInvoked = false;
      timeoutId = null;
      if (!invokeNow) {
        fn.apply(this, args);
      }
    }, ms);
  };

  debounced.cancel = function () {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    leadingInvoked = false;
  };

  return debounced;
}
