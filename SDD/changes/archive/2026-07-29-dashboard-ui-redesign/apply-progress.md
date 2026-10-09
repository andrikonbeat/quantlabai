# Apply Progress — PR 5: Statistics Dashboard

**Change**: dashboard-ui-redesign
**Slice**: 5 of 6 (Statistics Dashboard)
**Mode**: Strict TDD
**PR Strategy**: stacked-to-main (PR 5 of 6)
**Review Budget**: ~210 lines

## PR1 Completed Tasks (carried forward)

### PR1-01 through PR1-06
*(Design system foundation — 6 tasks)*

## PR2 Completed Tasks

### PR2-01 through PR2-07
*(Campaign list — 7 tasks)*

## PR3 Completed Tasks

### PR3-01 through PR3-05
*(Campaign detail — 5 tasks)*

## PR4 Completed Tasks

### PR4-01: Create Toast system (CSS + JS)
- **Created**: `static/css/components/modal-toast.css` — BEM toast with `.toast-container`, `.toast`, `.toast--success/error/warning/info`, `.toast__icon`, `.toast__message`, `.toast__close`, `.toast__progress`; slide-in animation from right, progress bar animation (100%→0%), `@layer components`, max 5 visible, `prefers-reduced-motion` support
- **Created**: `static/js/components/Toast.js` — ToastManager singleton with `show({ type, message, duration })`, `dismiss(id)`, `dismissAll()`; auto-dismiss durations: success/info 4s, warning 8s, error no auto-dismiss; max 5 visible (oldest dismisses when 6th added); progress bar animated alongside timer; close button; slide-in; `role="alert"` + `aria-live="polite"`
- **Modified**: `templates/base.html` — added `modal-toast.css` link in correct `@layer` order (after data-table.css)
- **Tests**: 24

### PR4-02: Create PipelineMonitor page module + store
- **Created**: `static/js/stores/pipeline-store.js` — `createPipelineStore()` with subscribe/notify pattern; state: `{ runs, loading, error, statusFilter, selectedRunId }`; actions: `loadRuns(runs)`, `setFilter(filter)`, `selectRun(runId)`
- **Created**: `static/js/pages/PipelineMonitor.js` — full page orchestrator: API load with spinning refresh icon, overview stats (total/running/success/failed with semantic colors), pipeline table with StatusBadge integration, stage detail expand/collapse, log viewer with terminal-style (dark bg, green text, auto-scroll), PollingService (10s interval), loading skeletons, error state with retry, empty state with EmptyState component, search filter, status filter, Toast notifications on load/error
- **Tests**: 17

### PR4-03: Update pipeline_monitor.html
- **Modified**: `templates/pipeline_monitor.html` — replaced old classes with BEM `.data-table__*`, `.sidebar__*`, `.stat-card` pattern; 4 stat card skeleton containers; `type="module"` dynamic import for PipelineMonitor.js; skeleton containers for overview stats and table rows; `.toast-container` for notifications; `.log-panel` terminal-style pre; `.stage-detail` expandable section; ARIA attributes (`role="region"`, `aria-label`, `aria-busy`)
- **Modified**: `static/css/utilities.css` — added `.stat-card`, `.spinning`, `.overview-stats`, `.stage-dots`, `.stage-dot--*`, `.stage-item`, `.log-panel`, `.log-header` styles
- **Tests**: 12

## PR5 Completed Tasks

### PR5-01: Create stats-store.js + StatsDashboard.js
- **Created**: `static/js/stores/stats-store.js` — `createStatsStore()` with subscribe/notify/gitState; initial state: `{ stats: null, loading: true, error: null, chartType: 'sharpe', showBenchmark: false, filters: { market: '', timeframe: '', startDate: '', endDate: '' } }`; actions: `loadStats()`, `setChartType()`, `toggleBenchmark()`, `setFilter()`
- **Created**: `static/js/pages/StatsDashboard.js` — full page orchestrator: loads `/api/stats` with filter params, renders 4 MetricCards (Sharpe/Drawdown/WinRate/Return with MetricCard component), main chart via ChartContainer with 5 chart type selector (sharpe/drawdown/winrate/return/benchmark), benchmark toggle overlay, 4-chart grid (drawdown/winrate/return/benchmark distributions), campaign stats table with client-side sort + pagination (20 per page), sidebar filters (market/timeframe/date range) that cascade to re-fetch, PollingService at 15s interval, loading skeletons for KPI/chart/grid, error state with retry, empty state via EmptyState, Toast notifications; ChartContainer instances are reused on polling to avoid duplicate ResizeObservers; no `alert()` calls
- **Tests**: 36

### PR5-02: Update stats_dashboard.html
- **Modified**: `templates/stats_dashboard.html` — BEM classes (`.sidebar__header`, `.sidebar__section`, `.data-table__*`, `.chart-container__*`), skeleton containers for KPI cards (`#stats-kpi-skeleton`), main chart (`#stats-main-chart-skeleton`), and chart grid (`#stats-grid-skeleton`), empty state section (`#stats-empty`), error state section (`#stats-error` with role=alert), ARIA labels on all filter controls (`aria-label="Select chart type"`, etc.), `aria-sort` on sortable table headers, `role="table"` on stats table, `role="complementary"` on sidebar filter, date range picker with styled inputs (`.form-input`), toast container (`.toast-container`), chart-container--large for main chart, `.metric-card-wrapper` for each KPI card; extends base.html with type="module" system via main.js
- **Tests**: 27

## TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| PR5-01 | test_pr5_stats_dashboard.py | Unit | ✅ 367/367 | ✅ Written | ✅ Passed | ✅ 36 tests | ✅ Clean — extracted getOrInitChart to avoid duplicate ResizeObservers on polling |
| PR5-02 | test_pr5_stats_dashboard.py | Unit | ✅ 367/367 | ✅ Written | ✅ Passed | ✅ 27 tests | ✅ Clean |

## Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `python -m pytest tests/dashboard/test_pr5_stats_dashboard.py -q --tb=short` → 63 passed, 0 failed |
| Runtime harness scenario | `flask run` then browse `/stats` — 4 KPI cards render with counter animations, main chart responds to chart type selector (5 types), benchmark toggle adds overlay, 4-chart grid renders all histograms, stats table sorts on column click with pagination, sidebar filters (market/timeframe/date) cascade to re-fetch, empty state shows when no campaigns, error state shows retry button, toast on load success (manual verification) |
| Rollback boundary | Revert PR 5 merge; stats-store.js and StatsDashboard.js removed; PR 1/2/3/4 CSS/JS intact; pipeline_monitor.html unchanged |

## Test Summary
- **PR5 tests**: 63 (36 store/page + 27 template)
- **Total dashboard tests**: 430 (367 existing + 63 new)
- **Layers**: Unit (63)

## Files Changed
| File | Action |
|------|--------|
| static/js/stores/stats-store.js | Created |
| static/js/pages/StatsDashboard.js | Created |
| templates/stats_dashboard.html | Modified |
| tests/dashboard/test_pr5_stats_dashboard.py | Created |
| openspec/changes/dashboard-ui-redesign/tasks.md | Modified |

## Status
23/23 tasks complete (6 PR1 + 7 PR2 + 5 PR3 + 3 PR4 + 2 PR5). Ready for PR 6 (Polish + Accessibility).
