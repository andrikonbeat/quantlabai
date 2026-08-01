# Delta for Dashboard UI

## ADDED Requirements

### 1. Design System Tokens

The system MUST define a 3-level token system (global, semantic, component) in CSS custom properties applied to `:root`.

| Token | Value | Type |
|-------|-------|------|
| `--navy-900` | `hsl(220, 45%, 8%)` | bg base |
| `--navy-800` | `hsl(220, 40%, 12%)` | bg secondary |
| `--navy-700` | `hsl(220, 35%, 17%)` | bg tertiary |
| `--blue-400` | `hsl(210, 100%, 66%)` | primary |
| `--green-400` | `hsl(135, 55%, 50%)` | success |
| `--red-400` | `hsl(0, 75%, 55%)` | danger |
| `--amber-400` | `hsl(40, 70%, 50%)` | warning |
| `--purple-400` | `hsl(260, 60%, 65%)` | accent |

Semantic aliases MUST map to these: `--color-primary`, `--color-success`, `--color-danger`, `--color-warning`, `--color-bg`, `--color-bg-secondary`, `--color-bg-tertiary`, `--color-text`, `--color-text-muted`, `--color-border`. Typography: Inter at 400/500/600/700 weights; scale MUST be 12/14/16/18/20/24/32/48px named `--text-xs` through `--text-4xl`. Spacing MUST use 4px base: `--space-1` (4px) through `--space-10` (40px). Elevation: `--shadow-sm` (0 1px 2px rgba(0,0,0,0.3)) through `--shadow-xl` (0 12px 40px rgba(0,0,0,0.6)). Border radius: `--radius-sm` (4px), `--radius-md` (8px), `--radius-lg` (12px), `--radius-xl` (16px). Animation: `--duration-fast` (200ms), `--duration-normal` (300ms), `--duration-slow` (500ms); `--ease-out` (cubic-bezier(0, 0, 0.2, 1)), `--ease-in-out` (cubic-bezier(0.4, 0, 0.2, 1)).

#### Scenario: Tokens are globally available
- GIVEN any dashboard page renders
- WHEN CSS is loaded
- THEN all token custom properties MUST be defined on `:root`
- AND every component MUST reference tokens, never raw values

#### Scenario: HSL format supports future light mode
- GIVEN a future `[data-theme="light"]` override
- WHEN tokens are overridden
- THEN only HSL hue/saturation values MUST change (lightness stays)
- AND semantic aliases MUST still resolve

### 2. CSS Architecture

The system MUST split the monolith into layered files using `@layer`, BEM naming with component prefix, and zero global selector pollution.

**File structure and layer assignment:**

| File | Purpose | @layer |
|------|---------|--------|
| `css/reset.css` | CSS reset/normalize | reset |
| `css/tokens.css` | Design token variables | tokens |
| `css/base.css` | Element defaults, typography | base |
| `css/layout.css` | Grid, sidebar, main-panel | layouts |
| `css/components.css` | Shared components (btn, badge, skeleton) | components |
| `css/metric-card.css` | MetricCard component | components |
| `css/data-table.css` | DataTable component | components |
| `css/tabs.css` | Tabs component | components |
| `css/toast.css` | Toast notification | components |
| `css/utilities.css` | Helpers, animations, responsive overrides | utilities |

Every component class MUST be prefixed: `.mc-*` (MetricCard), `.dt-*` (DataTable), `.tb-*` (Tabs), `.sb-*` (StatusBadge), `.ts-*` (Toast), `.sk-*` (Skeleton), `.es-*` (EmptyState), `.sd-*` (Sidebar). Cascade order MUST be: `reset → tokens → base → components → layouts → utilities`.

#### Scenario: Layer cascade prevents specificity wars
- GIVEN CSS is loaded with `@layer` declarations
- WHEN two rules target the same element
- THEN the layer order determines precedence, not selector specificity
- AND no unlayered rules may exist

### 3. JavaScript Architecture

The system MUST replace the 674-line IIFE with ES modules using a pub/sub store pattern, unified polling service, AbortController-backed API client, and Plotly.react chart manager.

**Module inventory:**

| File | Exports | Dependencies |
|------|---------|-------------|
| `js/store.js` | `createStore`, `subscribe`, `notify` | none |
| `js/api.js` | `apiGet`, `apiPost`, `apiCancel` | none |
| `js/polling.js` | `PollingService` (start/stop/pause/resume) | store |
| `js/charts.js` | `ChartManager` (init/update/cleanup) | Plotly CDN |
| `js/toast.js` | `showToast`, `dismissToast` | store |
| `js/tabs.js` | `initTabs` | none |
| `js/sidebar.js` | `initSidebar` | store |
| `js/pages/utils.js` | `escapeHtml`, `debounce`, `formatCurrency` | none |
| `js/pages/campaign-list.js` | `initCampaignList` | api, store, polling |
| `js/pages/campaign-detail.js` | `initCampaignDetail` | api, store, charts, tabs |
| `js/pages/pipeline.js` | `initPipelineMonitor` | api, store, polling |
| `js/pages/stats.js` | `initStatsDashboard` | api, store, charts |

**Store:** MUST implement `subscribe(key, fn)` returning unsubscribe fn, and `notify(key, data)`. No external state library. **PollingService:** MUST expose `start(url, intervalMs)`, `stop()`, `pause()`, `resume()`. MUST use exponential backoff: 3s → 10s → 30s → 60s max, resetting on success. **API client:** Every `fetch()` MUST accept `AbortSignal`. Retry config: 3 attempts with 1s delay between retries, 15s timeout per request. **ChartManager:** Singleton wrapping `Plotly.react`. MUST register `beforeunload` handler calling `Plotly.purge()` on all managed containers. MUST never call `Plotly.newPlot`.

#### Scenario: Store notifies subscribers on data change
- GIVEN a store with subscribers for key `campaigns`
- WHEN `notify('campaigns', data)` is called
- THEN all subscribers receive the data
- AND the unsubscribe fn, when called, removes the subscriber

#### Scenario: Polling stops on page navigation
- GIVEN polling is active on a page
- WHEN `stop()` is called
- THEN `clearInterval` is invoked on the active timer
- AND no further API calls fire for that poll

### 4. Component Specs

**MetricCard** — MUST support 4 states:

| State | Behavior |
|-------|----------|
| Loading | Skeleton shimmer replaces value |
| Loaded | Value + label + sparkline visible |
| Error | Value replaced by "—" with muted styling |
| Empty | Shows "N/A" with muted styling |

Props: `value`, `label`, `icon`, `trend` (up/down/flat), `colorThreshold` (good/bad/neutral based on value range). Sparkline: inline SVG `<polyline>` with viewBox `0 0 100 24`, stroke-width 2, responsive width. Color thresholds per metric type: sharpe (good≥1, ok≥0, bad<0), drawdown (good<5, ok<15, bad≥15), winrate (good>60, ok>40, bad≤40), return (good>0, ok≥-5, bad<-5).

**DataTable** — sorting: MUST sort client-side for <300 rows, defer to server `?sort=col&order=asc` otherwise. Pagination: show page N of M, prev/next buttons disabled at boundaries. Row selection: click selects row (visual highlight). Headers MUST be sticky on scroll.

**Tabs** — MUST carry full ARIA: `role="tablist"` on container, `role="tab"` with `aria-selected` and `aria-controls` on each button, `role="tabpanel"` with `aria-labelledby` on content. Keyboard: Left/Right arrows move focus, Home goes to first, End to last, Enter/Space activates. Active tab receives focus on activation. Lazy loading: non-active tab panels MUST NOT fetch data until first activation.

**StatusBadge** — icon mapping:

| Status | Icon | Color | Animation |
|--------|------|-------|-----------|
| running | play-circle | `--color-primary` | pulse |
| completed | check-circle | `--color-success` | none |
| failed | x-circle | `--color-danger` | none |
| pending | clock | `--color-text-muted` | none |
| skipped | skip-forward | `--color-warning` | none |

**Toast** — z-index: 10,000 (above all content). Auto-dismiss: success/neutral (4s), warning (6s), error (user dismiss only). Max 5 visible toasts; beyond 5, new toasts push oldest to `dismissing` state. Queue: FIFO with configurable max.

**Skeleton** — shimmer animation: CSS `@keyframes` with linear-gradient background sweep at 1.5s cycle. Dimensions per component: MetricCard (full card), DataTable row (full row height), chart (350px height), text line (1em height, 60% width).

**EmptyState** — SVG illustration: centered 120×120 inline SVG (folder/chart/search icon). Heading: 18px bold, subheading: 14px muted, action button: primary style. Margin: `--space-10` top/bottom.

**Sidebar** — collapsible sections: each `<section>` with toggle button (chevron icon), `aria-expanded` attribute, smooth height transition. Scroll position: save to `sessionStorage` key `sidebar-scroll-{page}`, restore on page load. Active item detection: compare `data-id` against `window.location.pathname`, apply `.active` class.

#### Scenario: Tabs keyboard navigation
- GIVEN focus is on a tab button
- WHEN the Right Arrow key is pressed
- THEN focus moves to the next tab button
- AND the newly focused tab is activated via click
- WHEN Left Arrow is pressed
- THEN focus moves to the previous tab

#### Scenario: Toast queue limits visible count
- GIVEN 5 toasts are visible
- WHEN a 6th toast is triggered
- THEN the oldest toast begins dismissal animation
- AND the new toast appears in its place

### 5. Page States

Every page MUST implement 4 states:

| State | Trigger | UI |
|-------|---------|----|
| Loading | Initial render, no data | Skeleton per component |
| Loaded | Data received | Full content |
| Error | API returns error or fails | Error card with retry button |
| Empty | API returns empty list | EmptyState illustration |

**Campaign List:** Loading/empty/error for sidebar + table independently. Sort columns by click (client-side). Pagination controls show page N of M. **Campaign Detail:** 4 KPI cards with sparkline SVGs. Equity curve via Plotly.react (time x equity). Tabs with lazy loading: Trades, Stages, Reports load on first activation. Report generation: button shows loading spinner, toast on success/error, disabled during API call. **Pipeline Monitor:** Overview stats (total/running/success/failed). Pipeline table with stage dots. Stage detail expand/collapse. Log viewer auto-scroll to bottom on new content. **Stats Dashboard:** Sidebar filters reactive — changing market/timeframe/date re-triggers `/api/stats` with params. Main chart switches between share/drawdown/winrate/return/benchmark. 4-chart grid below. Stats table with all campaign data.

#### Scenario: Campaign detail shows error state with retry
- GIVEN the campaign detail API returns a 500 error
- WHEN the response is received
- THEN an error card replaces the content
- AND a "Retry" button re-fetches the data
- AND the error card remains until retry succeeds

### 6. Responsive Design

Breakpoints: 480px (mobile), 768px (tablet), 1200px (desktop). Sidebar: collapsible at ≤1200px (toggle button visible), overlay at ≤768px (sidebar slides over content), hidden at ≤480px with hamburger menu icon. Charts grid: 2-column at desktop, 1-column below 768px. Tables: horizontal scroll at ≤768px with sticky first column. Metric cards: 4-column at desktop, 2 at 768px, 1 at 480px. Font size: no change below 768px. Search/filter bar: wrap to multi-line at ≤768px.

#### Scenario: Sidebar becomes overlay on tablet
- GIVEN viewport width is 768px
- WHEN the sidebar toggle is clicked
- THEN the sidebar slides in from left as an overlay
- AND content behind is dimmed with semi-transparent backdrop

### 7. Accessibility (WCAG 2.1 AA)

| Component | ARIA Role/Attribute |
|-----------|-------------------|
| Tabs | `tablist`, `tab` (aria-selected), `tabpanel` (aria-labelledby) |
| Sidebar | `navigation`, `aria-label="Sidebar"` |
| Toast | `role="alert"`, `aria-live="polite"` |
| Modal | `role="dialog"`, `aria-modal="true"` |
| Loading | `aria-busy="true"` on container |
| Skeleton | `aria-hidden="true"` |
| DataTable | `role="table"`, `aria-sort` on headers |
| StatusBadge | `aria-label="Status: {status}"` |

**Keyboard navigation:** Tab/Shift+Tab moves focus through interactive elements. Arrow keys navigate within tablist, menu, and select elements. Enter/Space activates buttons and toggles. Escape closes modals, toasts, overlay sidebar. **Focus management:** After tab switch, focus moves to the active tab button. After data load, maintain focus position (don't reset to top). After toast dismiss, return focus to triggering element. **Contrast:** All text MUST meet 4.5:1 ratio (normal) / 3:1 (large). Interactive elements MUST show visible focus ring (2px solid `--color-primary` with 2px offset).

`prefers-reduced-motion`: When detected, disable ALL animations and transitions instantly. Set `animation: none !important; transition-duration: 0s !important;` on all animated elements. `prefers-color-scheme`: CSS structure MUST support `[data-theme="light"]` selector for future light mode. Light mode implementation is out of scope.

#### Scenario: Screen reader reads live updates
- GIVEN a toast notification appears
- WHEN the toast is added to the DOM
- THEN `role="alert"` and `aria-live="polite"` cause the screen reader to announce it
- AND focus remains on the user's current interaction

### 8. Micro-interactions

| Effect | Duration | Property | Easing |
|--------|----------|----------|--------|
| Hover (card/row) | 200ms | border-color, transform | ease-out |
| Hover (button) | 150ms | background-color | ease-out |
| Click (button) | 100ms | transform: scale(0.97) | ease-out |
| Data transition (chart) | 500ms | opacity cross-fade | ease-in-out |
| Page transition | 300ms | opacity 0→1 on new content | ease-out |
| Toast enter | 300ms | translateY + opacity | ease-out |
| Toast exit | 250ms | opacity + translateX | ease-in |
| Skeleton shimmer | 1.5s | background-position infinite | linear |

All `transition` properties MUST target specific CSS properties, never `all` (performance anti-pattern).

#### Scenario: Click scales button momentarily
- GIVEN a primary button is rendered
- WHEN the user clicks it
- THEN a transform scale(0.97) applies for 100ms
- AND the button returns to scale(1) after 100ms

### 9. Plotly Customization

Every Plotly chart MUST use these global layout overrides:

```javascript
{
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: { family: 'Inter, system-ui, sans-serif', color: '--color-text-muted' },
  xaxis: { gridcolor: '--color-bg-tertiary', zerolinecolor: '--color-border' },
  yaxis: { gridcolor: '--color-bg-tertiary', zerolinecolor: '--color-border' },
  hovermode: 'x unified',
  hoverlabel: { bgcolor: '--color-bg-tertiary', font: { color: '--color-text' } },
  margin: { l: 60, r: 20, t: 20, b: 40 }
}
```

Color palette (6-color qualitative financial): `['#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7', '#79c0ff']`. Mode bar: MUST show toggles (zoom, pan, reset, download) on hover, MUST hide otherwise (`displayModeBar: 'hover'`). Animation: `transition: { duration: 500, easing: 'cubic-in-out' }`. `responsive: true` MUST be set on every chart. Resize handler: `Plotly.Plots.resize()` on window resize (debounced 200ms). **Never call `Plotly.newPlot`** — always use `Plotly.react` for initial render AND updates.

#### Scenario: Chart updates via Plotly.react
- GIVEN a chart is rendered via Plotly.react
- WHEN new data arrives
- THEN Plotly.react MUST be called again with updated trace data
- AND the DOM element is reused (not destroyed)

### 10. Acceptance Criteria

| # | Criterion | Page | Verification |
|---|-----------|------|-------------|
| 1 | Professional Navy quantitative palette uniform across all pages | All | Visual audit |
| 2 | All pages show skeleton states on data load | All | Visual + code review |
| 3 | All pages show empty states when no data | All | Visual (empty DB) |
| 4 | All API errors show error card with retry button | All | Mock 500 response |
| 5 | Table sort + pagination works for <300 rows | List, Stats, Pipeline | Click test |
| 6 | All Plotly charts share consistent font/colors/grids | Detail, Stats | Visual audit |
| 7 | Fade transitions on data updates (not instant swap) | All | Visual audit |
| 8 | WCAG 2.1 AA contrast on all text elements | All | Axe/contrast checker |
| 9 | Sidebar scroll position persists across page reload | All | sessionStorage check |
| 10 | Zero `alert()` calls in JS | All | grep alert() |
| 11 | Polling stops on page leave, no orphaned intervals | Pipeline, List | DevTools timer audit |
| 12 | Responsive at 480/768/1200px breakpoints | All | Manual resize test |
| 13 | CSS @layer order found in every .css file | All | Code review |
| 14 | All JS modules use export/import (no IIFE) | All | Code review |
| 15 | Tabs work correctly (aria-selected + show/hide + keyboard) | Detail | Manual + a11y audit |
| 16 | Toast replaces all dialog-based feedback | All | grep alert() + visual |
| 17 | prefers-reduced-motion disables all animations | All | DevTools emulation |
| 18 | Every interactive element has visible focus ring | All | Tab-through audit |
| 19 | Charts use Plotly.react exclusively | Detail, Stats | Code review |
| 20 | Report generate button shows loading state, disables during call | Detail | Visual + network tab |

#### Scenario: All 20 acceptance criteria pass
- GIVEN the implementation is complete
- WHEN each criterion is verified against its verification method
- THEN no criterion fails
- AND the visual audit confirms professional quality
