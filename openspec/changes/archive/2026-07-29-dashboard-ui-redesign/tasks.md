# Tasks: Dashboard UI Redesign

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,930 |
| 400-line budget risk | Low (per-slice) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Design System) → PR 2 (Campaign List) → PR 3 (Campaign Detail) → PR 4 (Pipeline) → PR 5 (Stats) → PR 6 (Polish) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Design system tokens, reset, base, components CSS | PR 1 | `curl localhost:8080 \| grep -c 'design-tokens.css'` | `flask run`, verify CSS variables on :root | Revert PR 1 merge; old dashboard.css still serves |
| 2 | Campaign list page rewrite | PR 2 | `curl localhost:8080 \| grep 'type="module"'` | Browse `/campaigns`, verify skeleton→loaded transition | Revert PR 2 merge; PR 1 CSS remains |
| 3 | Campaign detail page rewrite | PR 3 | DevTools console: `document.querySelectorAll('.tab-btn').length === 4` | Browse `/campaigns/<id>`, click tabs | Revert PR 3 merge; campaign_list.html unchanged |
| 4 | Pipeline monitor rewrite | PR 4 | DevTools console: `typeof ToastManager !== 'undefined'` | Browse `/pipeline`, verify polling | Revert PR 4 merge; Toast.js removed |
| 5 | Stats dashboard rewrite | PR 5 | `curl localhost:8080/stats \| grep 'skeleton'` | Browse `/stats`, switch chart types | Revert PR 5 merge; campaign_detail.html unchanged |
| 6 | WCAG audit, reduced-motion, cleanup, delete old files | PR 6 | `pa11y http://localhost:8080` | Tab-through all pages, verify skip-link | Revert PR 6 merge; old files restored from git |

## Slice 1 — Design System Foundation (~350 lines)

- [x] PR1-01: Create `static/css/design-tokens.css` — 3-level HSL token system (global/semantic/component), typography, spacing, elevation, radius, animation
- [x] PR1-02: Create `static/css/reset.css` + `static/css/base.css` — modern reset, Inter font, scrollbar, body defaults
- [x] PR1-03: Create `static/css/layouts/dashboard-grid.css` + `detail-layout.css` — grid sidebar/main, 3 breakpoints
- [x] PR1-04: Create `static/css/components/buttons.css`, `badges.css`, `forms.css` — BEM classes with `--color-*` tokens
- [x] PR1-05: Create `static/css/utilities.css` — `.sr-only`, `.truncate`, `.flex-center`, spacing utils
- [x] PR1-06: Modify `templates/base.html` — layered CSS imports, conditional Plotly, ARIA landmarks, `prefers-color-scheme` meta

## Slice 2 — Campaign List (~400 lines)

- [x] PR2-01: Create `static/css/components/sidebar.css` — collapsible sections, BEM with `.sidebar__*` classes
- [x] PR2-02: Create `static/css/components/data-table.css` — sort indicators, sticky header, pagination
- [x] PR2-03: Create `static/css/components/skeleton.css` + `empty-state.css` — shimmer animation, centered SVG
- [x] PR2-04: Create `static/js/api/client.js`, `utils/formatters.js`, `utils/debounce.js`, `utils/poller.js` — fetch with retry/AbortController, PollingService class
- [x] PR2-05: Create `static/js/stores/campaign-store.js` + `main.js` + `pages/CampaignList.js` — pub/sub store, path routing, page module
- [x] PR2-06: Create `static/js/components/DataTable.js`, `Sidebar.js`, `SkeletonLoader.js`, `EmptyState.js` — sort/paginate, collapsible sections, shimmer rendering
- [x] PR2-07: Modify `templates/campaign_list.html` — BEM classes, skeleton containers, empty/error states, `type="module"` scripts

## Slice 3 — Campaign Detail (~380 lines)

- [x] PR3-01: Create `tabs.css`, `metric-card.css`, `chart-container.css` — fix `.tab-pane` → `.tab-panel` bug, ARIA classes, sparkline SVGs
- [x] PR3-02: Create `static/js/components/ChartContainer.js` — Plotly.react singleton, never newPlot, resize handler
- [x] PR3-03: Create `MetricCard.js`, `Tabs.js`, `StatusBadge.js` — counter animation, keyboard nav (← → Home End), status→icon mapping
- [x] PR3-04: Create `pages/CampaignDetail.js`, extend `stores/campaign-store.js` — wire chart/metrics/tabs, generate report→Toast
- [x] PR3-05: Modify `templates/campaign_detail.html` — fix tab class bug, ARIA roles, skeleton metrics, toast container, module scripts

## Slice 4 — Pipeline Monitor (~250 lines)

- [x] PR4-01: Create `modal-toast.css` + `static/js/components/Toast.js` — 4 variants, stack queue, auto-dismiss, slide-in animation
- [x] PR4-02: Create `stores/pipeline-store.js` + `pages/PipelineMonitor.js` — wire table/stage detail/log viewer, polling, terminal-style log with auto-scroll
- [x] PR4-03: Modify `templates/pipeline_monitor.html` — skeleton containers, error state with retry, toast container

## Slice 5 — Statistics Dashboard (~210 lines)

- [x] PR5-01: Create `stores/stats-store.js` + `pages/StatsDashboard.js` — wire chart grid/KPI cards/stats table, chart type selector, benchmark toggle, date range filter
- [x] PR5-02: Modify `templates/stats_dashboard.html` — skeleton containers for KPI/charts, ARIA labels, date range picker, empty/error states

## Slice 6 — Polish + Accessibility (~200 lines)

- [x] PR6-01: WCAG 2.1 AA audit all 4 templates — color contrast, focus-visible rings, ARIA labels, heading hierarchy, skip-to-content link
- [x] PR6-02: Add `@media (prefers-reduced-motion: reduce)` to skeleton, badges, toast, metric-card CSS
- [x] PR6-03: Delete `dashboard.css` and `dashboard.js`, remove `DASHBOARD_V2` feature flag, fix visual regressions
- [x] PR6-04: Lighthouse audit (>80 Perf, >90 A11y), verify no polling leaks, no alert(), Plotly only on chart pages
