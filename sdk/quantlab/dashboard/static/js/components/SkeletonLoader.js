/**
 * SkeletonLoader — renders HTML skeleton placeholders.
 */
export default class SkeletonLoader {
  /**
   * Render skeleton elements.
   * @param {string} type - 'card' | 'row' | 'chart' | 'metric'
   * @param {number} count - number of skeleton elements
   * @returns {string} HTML string
   */
  render(type = "row", count = 1) {
    const items = [];
    for (let i = 0; i < count; i++) {
      items.push(`<div class="skeleton skeleton--${type}" aria-hidden="true"></div>`);
    }
    return items.join("\n");
  }
}
