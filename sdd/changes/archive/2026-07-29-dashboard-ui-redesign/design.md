# Design: Dashboard UI Redesign — Professional Financial Interface

## Technical Approach

CSS overhaul + JS rewrite, keeping Flask + Jinja2. Single IIFE monolith (674 lines) and single CSS file (646 lines) → layered component CSS with `@layer` + BEM, and ES modules with pub/sub stores. Plotly migration from `newPlot` to `react`. Delivered in 6 chained PRs under 400-line review budget each, stacked to main.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| JS module system | ES modules (native) | IIFE, Vite/Rollup | No build pipeline needed. Flask serves `type="module"` directly. IIFE is current tech debt. |
| CSS scoping | BEM + `@layer` | CSS Modules, Tailwind | Zero build step. `@layer` fixes cascade without specificity hacks. BEM is already partially used. |
| State management | Pub/sub stores | Redux, Zustand | 4-page scope doesn't warrant a framework. ~30 lines per store. No deps. |
| Chart API | `Plotly.react` | `newPlot` (current) | DOM reuse avoids thrash. Spec mandates 500ms transitions. Existing `newPlot` tears down every update. |
| Polling lifecycle | PollingService class | `setInterval` (current) | Exposes `start/stop/pause/resume`. Current orphaned timers (never cleared) are bug #3 from exploration. |
| API cancellation | AbortController | Promise.race | Standard, cancel semantics, per-request signals. |
| Bundling | None | Vite, esbuild | Flask static dir doesn't need it. Plotly is CDN-only (3.5MB). CSS is 18 files <20KB. |

## Data Flow

```
                    ┌─────────────┐
                    │  main.js     │  (page router)
                    └──────┬──────┘
                           │ import * from pages/*
                    ┌──────▼──────┐
                    │ PageModule  │  (e.g. CampaignList)
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └──────────┐
              ▼            ▼              ▼
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │api/client│ │stores/*  │ │poller.js     │
        └────┬─────┘ └────┬─────┘ └──────┬───────┘
             │            │              │
        fetch()      notify(key,data)  setInterval
        + Abort       subscribers       + visibility
        Controller    → render()        check
```

**Page load**: `main.js` → detects path → imports page module → page calls `apiGet()` → on response `store.notify(key, data)` → subscribers render skeletons→content.

**Polling**: `poller.start(url, 10s)` → `apiGet()` → `store.notify()` → re-render with fade. Page Visibility API pauses on hidden, resumes on visible.

**User interaction** → `store.updateFilter()` → `store.notify()` → subscribers re-render with new params → cascaded API call if server sort needed.

## State Machine (per page)

```
 loading ──(api success)──► loaded ◄──(poll data)── refreshing
    │                            │
    │(api error)            (data empty)
    ▼                            ▼
  error ──(retry)──► loading   empty
```

- **loading**: Skeleton per component, `aria-busy="true"`
- **loaded**: Full content, polling active
- **error**: Error card + retry button, previous data hidden
- **empty**: EmptyState illustration (only if never had data)
- **refreshing**: Data visible + subtle indicator (poll update)

## File Changes

### Delete
| File | Reason |
|------|--------|
| `static/dashboard.css` | Monolith→component split |
| `static/dashboard.js` | IIFE→ES modules |

### Create (CSS — 18 files)
`static/css/design-tokens.css`, `reset.css`, `base.css`, `components/sidebar.css`, `metric-card.css`, `chart-container.css`, `data-table.css`, `tabs.css`, `badges.css`, `buttons.css`, `forms.css`, `modal-toast.css`, `skeleton.css`, `empty-state.css`, `layouts/dashboard-grid.css`, `detail-layout.css`, `utilities.css`

### Create (JS — 21 files)
`static/js/main.js`, `api/client.js`, `stores/{campaign,pipeline,stats}-store.js`, `components/{MetricCard,DataTable,ChartContainer,Tabs,Toast,Sidebar,SkeletonLoader,EmptyState,StatusBadge}.js`, `utils/{formatters,poller,debounce}.js`, `pages/{CampaignList,CampaignDetail,PipelineMonitor,StatsDashboard}.js`

### Modify
| File | Changes |
|------|---------|
| `templates/base.html` | CSS/JS refs → `css/layers.css` import + `js/main.js` module; conditional Plotly (only on chart pages); toast container `<div id="toast-container">`; ARIA landmarks; `prefers-color-scheme` meta |
| `templates/campaign_list.html` | Section classes → `sb-*`, `dt-*`, `sk-*`, `es-*`; skeleton containers; `aria-busy` |
| `templates/campaign_detail.html` | `role=tablist` + ARIA attrs; skeleton metric cards; hidden tab panels (fix the `.tab-panel/.tab-pane` bug); toast container |
| `templates/pipeline_monitor.html` | Skeleton sections; ARIA live region for stage detail; toast container |
| `templates/stats_dashboard.html` | Skeleton charts; ARIA labels on filters; toast container |

### Layer Assignment (CSS)
`@layer reset, tokens, base, components, layouts, utilities;` — every CSS file declares its layer. Reset→tokens→base→components→layouts→utilities order controls cascade.

## Interfaces / Contracts

```js
// Store
const store = createStore()  // { subscribe(key, fn), notify(key, data) }
const unsub = store.subscribe('campaigns', render)
store.notify('campaigns', [{id: 'abc', name: '...'}])

// API Client
apiGet('/api/campaigns', { signal })  // returns { success, data }
apiPost('/api/reports/generate', body, { signal })

// PollingService
const poller = new PollingService(apiClient)
poller.start('/api/pipeline', 5000, (data) => store.notify('pipeline', data))
poller.stop()   // clearInterval
poller.pause()  // visibility hidden
poller.resume() // visibility visible

// ChartContainer (wraps Plotly.react)
const chart = new ChartContainer('equity-chart', { responsive: true })
chart.init(config, layout)   // Plotly.react
chart.update(newData)        // Plotly.react with new traces
chart.destroy()              // Plotly.purge()
```

## Testing Strategy

| Layer | Scope | Approach |
|-------|-------|----------|
| Manual visual | All pages | Checklist per PR: 18 AC items from spec |
| a11y | ARIA, keyboard, contrast | Axe DevTools audit per page |
| Responsive | 480/768/1200px | Browser resize + DevTools emulation |
| Plotly | Chart rendering | Feature flag toggle newPlot vs react; visual diff |
| Regression | All interactive behavior | Tab through all flows, no alert(), polling stops on nav |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Chained PR Slicing

| Slice | Focus | Files | Est. Lines |
|-------|-------|-------|------------|
| 1 | Design System Foundation | `css/design-tokens.css`, `reset`, `base`, `utilities`, `buttons`, `badges`, `forms`, `layouts/dashboard-grid` | ~350 |
| 2 | Campaign List | `sidebar.css`, `data-table.css`, `skeleton.css`, `empty-state.css`; `campaign_list.html`; `main.js`, `api/client.js`, `stores/campaign-store.js`, `utils/*`, `pages/CampaignList.js`, `components/{SkeletonLoader,EmptyState,Sidebar,DataTable}.js` | ~400 |
| 3 | Campaign Detail | `tabs.css`, `metric-card.css`, `chart-container.css`; `campaign_detail.html`; `components/{MetricCard,Tabs,ChartContainer,StatusBadge}.js`, `pages/CampaignDetail.js` | ~380 |
| 4 | Pipeline Monitor | `pipeline_monitor.html`; `stores/pipeline-store.js`, `components/Toast.js`, `pages/PipelineMonitor.js` | ~250 |
| 5 | Statistics Dashboard | `stats_dashboard.html`; `stores/stats-store.js`, `pages/StatsDashboard.js` | ~350 |
| 6 | Polish + Accessibility | All pages: WCAG 2.1 AA audit, `prefers-reduced-motion`, focus management, visual polish | ~200 |

Dependencies: 1→all (foundation), 1→2→3 (campaign pages build on DataTable/Sidebar), 1→4 (needs base), 1→5 (needs base), 6→all (final pass).

## Performance Budget

- **Total JS**: <50KB minified (excl. Plotly CDN ~500KB)
- **Total CSS**: <20KB minified
- **First paint**: <500ms (skeleton immediately visible)
- **Time to interactive**: <2s
- **Lighthouse**: >80 Perf, >90 Accessibility

## Migration / Rollout

Per-PR merge. Old `dashboard.css` and `dashboard.js` archived in git (not deleted until Slice 6). Feature flag `DASHBOARD_V2` on `window.__DASHBOARD_V2` — if absent, old files load. Remove flag in Slice 6.

## Open Questions

- [ ] Plotly CDN conditional loading: check if Plotly is already loaded before injecting `<script>` for chart pages
- [ ] Confirm `campaign_id` in template context — currently `campaign_detail.html` references `{{ campaign.name }}` but Flask route passes only `campaign_id`. JS extracts ID from URL path; confirm no server-side render depends on campaign context.
- [ ] Decide whether to inline SVG icons or load from sprite. Proposal suggests inline for tree-shaking.
