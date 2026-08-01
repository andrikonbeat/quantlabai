## Exploration: QuantLab Dashboard UI Redesign

### Current State

The QuantLab dashboard is an MVP-grade Flask application serving 4 pages (campaign list, campaign detail, pipeline monitor, statistics) through Jinja2 templates. The frontend is a single IIFE (`dashboard.js`, 674 lines) with inline Plotly chart rendering and `setInterval`-based polling, styled by a single CSS file (`dashboard.css`, 646 lines) with CSS custom properties defining a dark theme.

The backend (`app.py`, 285 lines) is a clean Flask app factory with standardized JSON envelope responses (`success_response`/`error_response`), delegating to a CLI runner (`CliRunner`) for data. The backend is **not the problem** — it's well-structured and maintainable.

The existing spec (`openspec/specs/dashboard-ui/spec.md`) covers functional requirements but says nothing about UX quality, accessibility, or visual polish. The current implementation meets those bare functional specs but fails at professional quality.

### Affected Areas

- `sdk/quantlab/dashboard/static/dashboard.css` — CSS rewrite: naming convention, layout system, component styles, responsive breakpoints, animations
- `sdk/quantlab/dashboard/static/dashboard.js` — JS rewrite: modularization, polling lifecycle, error handling, accessibility, chart management
- `sdk/quantlab/dashboard/templates/base.html` — Updated: ARIA landmarks, theme meta tags, structured footer
- `sdk/quantlab/dashboard/templates/campaign_list.html` — Updated: search debounce, empty/error states, pagination UX
- `sdk/quantlab/dashboard/templates/campaign_detail.html` — Updated: tab ARIA, loading skeletons, report generation modal/toast
- `sdk/quantlab/dashboard/templates/pipeline_monitor.html` — Updated: log panel UX, polling indicator, stage progress animation
- `sdk/quantlab/dashboard/templates/stats_dashboard.html` — Updated: chart controls accessibility, filter UX
- `openspec/specs/dashboard-ui/spec.md` — Updated spec to include UX, accessibility, and performance requirements

### Visual Audit

| Issue | Location | Severity | Why It Looks Bad |
|-------|----------|----------|------------------|
| `.metric-value` CSS conflict (defined twice) | CSS lines 167 and 258 | **High** | Campaign list sidebar renders `.metric-value` from the generic rule (0.9rem) instead of the metric-card rule (1.5rem) — inconsistent sizing |
| `.tab-panel` vs `.tab-pane` naming mismatch | CSS line 417 `.tab-panel` vs templates using `class="tab-pane"` | **Critical** | Tab panels are **broken** — the CSS class never matches, so tab content is always visible (no switching) |
| Identical SVG icons for 4 different metrics | campaign_detail.html lines 51-77 | **Medium** | Sharpe, Drawdown, Win Rate, and Return all use the exact same `<polyline>` chart icon — no visual distinction |
| `.stat-value` at 2rem with no context color | CSS line 454 | **Medium** | All stat numbers (total/running/success/failed) are the same color — no semantic coloring to distinguish good from bad |
| No visual hierarchy in sidebar list items | campaign_list.html | **Low** | Campaign items have card-like styling but no visual separation between active/inactive states beyond a subtle border color |
| No transition on chart type change | stats_dashboard.html | **Low** | Chart swaps instantly with no fade — feels jarring |
| Search input has no focus ring or clear button | All templates | **Low** | Input has focus border but no clear button or placeholder styling beyond defaults |
| Status badges use same color scheme as background | CSS lines 142-145 | **Low** | Low-contrast on some statuses — "completed" green on dark background uses rgba with 0.2 opacity |

### UX Audit

| Missing Feature | Impact | Location |
|----------------|--------|----------|
| **Loading skeletons** | User sees "Loading..." text — feels unprofessional | All templates |
| **Empty states** | No UI for "no campaigns" or "no results" — user sees empty box | campaign_list.html, pipeline_monitor.html |
| **Error states with retry** | API errors silently swallowed — page stays in "Loading..." forever | `dashboard.js` — every `!result.success` returns silently |
| **Toast/notification** | `alert()` on report generation — blocking, no styling, cannot be dismissed gracefully | `dashboard.js` lines 377-380 |
| **Button loading states** | "Generate Report" stays enabled during API call — double-clicks cause duplicate requests | campaign_detail.html |
| **Disable states** | "New Report" button is permanently disabled (`disabled` attribute hardcoded) | campaign_list.html line 10 |
| **Polling status** | No visual indicator that data is being polled — user doesn't know if page is live or stale | All pages |
| **Tab keyboard nav** | No arrow key support, no `aria-selected`, no focus management | campaign_detail.html |
| **Search debounce** | Filters fire on every keystroke — unnecessary DOM work | campaign_list.html, pipeline_monitor.html |
| **Back navigation** | No "Back" button from campaign detail to list (sidebar has one, but no browser history enhancement) | campaign_detail.html |

### Technical Debt

**CSS Conflicts and Problems:**
- `.metric-value` declared twice: line 167 (generic: `0.9rem, font-weight: 600`) and line 258 (metric-card: `1.5rem, font-weight: 700`). While specificity cascade makes it work in practice, this is a maintenance trap and the intent is confusing.
- `.tab-panel` (line 417) vs `.tab-pane` (templates). **This means tabs DO NOT WORK** — the CSS `display: none` never applies because the class name doesn't match.
- WebKit-only scrollbar styles (lines 630-645) — Firefox uses `scrollbar-width`, not `::-webkit-scrollbar`.
- `transition: all 0.2s` (lines 108, 229, 232, 396, 404, 528, 546) — using `all` is a performance anti-pattern. Should transition specific properties.
- No CSS source organization — single file with no section comments beyond the minimal ones present. Components are mixed in semi-arbitrary order.
- No `prefers-reduced-motion` media query.
- No `prefers-color-scheme` support — hardcoded dark theme only.

**JS Anti-Patterns:**
- `setInterval` at module level (line 10) — never cleared. Every `init*()` overwrites `pollTimer` without calling `clearInterval()` on the previous one.
- `alert()` for user feedback (lines 377, 379) — blocking dialog, unstyled, no UX. Industry has moved to toasts/notifications a decade ago.
- No `AbortController` — in-flight `fetch` requests cannot be canceled. If user navigates quickly, stale responses may update the wrong page.
- `Plotly.newPlot()` (lines 74, 105, 129, 165) — destroys and recreates the DOM element on each call. `Plotly.react()` is the correct API for updates — it diffs and only updates changed traces.
- No request deduplication — if `loadCampaigns()` fires twice before the first resolves, two parallel requests are in flight.
- Global `window.Dashboard` exposure (line 656) — no module system, no encapsulation beyond the IIFE.
- Error handling pattern `if (!result.success) return;` — silent failure. User sees stale/loading state forever.

**Accessibility Issues:**
- No `role="tablist"`, `role="tab"`, `role="tabpanel"` on tab components
- No `aria-selected`, `aria-controls`, `aria-labelledby` on tabs
- No `aria-live` regions for dynamic content updates
- No `aria-label` on navigation elements
- No keyboard event handlers — tab switching via mouse only
- No `role="status"` or `aria-live="polite"` on loading states
- No focus management after tab switch or data load
- No `role="alert"` on error messages
- No skip-to-content link
- Color contrast relies entirely on the dark theme — no verification against WCAG standards

**Performance:**
- Plotly CDN at ~3.5MB uncompressed — single largest payload, loaded on every page
- `setInterval` polling every 5s on ALL pages — wasteful on campaign detail (mostly static data) and stats dashboard
- No data caching — every poll re-fetches and re-renders everything
- All campaign rows rendered into DOM at once — no virtualization
- Every chart recreated with `newPlot` instead of updated with `react`

### Component Inventory

| Component | CSS Class(es) | Used On | State | Notes |
|-----------|---------------|---------|-------|-------|
| Metric Card | `.metric-card`, `.metric-icon`, `.metric-info`, `.metric-value`, `.metric-label` | Detail, Stats | hover (border + shadow + translateY) | Solid foundation, needs semantic icons |
| Stat Card | `.stat-card`, `.stat-value`, `.stat-label` | List, Pipeline | none | Could be merged with metric-card |
| Button Primary | `.btn.btn-primary` | All | hover, disabled | Solid |
| Button Secondary | `.btn.btn-secondary` | All | hover | Solid |
| Button Danger | `.btn.btn-danger` | — | — | Defined but unused |
| Button Small | `.btn.btn-sm` | All | — | Size variant |
| Status Badge | `.status-badge` (table) | Campaigns, Pipeline | per-status color | Good pattern |
| Status Pill | `.campaign-status` (sidebar) | Campaign list | per-status color | Duplicate of status-badge, could unify |
| Pipeline Stage Dot | `.stage-indicator` | Pipeline | pending/running/success/failed/skipped | Has `pulse` animation for running |
| Tab Button | `.tab-btn`, `.tab-btn.active` | Detail | active/inactive | Broken (class mismatch) |
| Chart Container | `.chart-container`, `.chart-header` | Detail, Stats | — | Solid |
| Plotly Chart | `.plotly-chart`, `.plotly-chart.large` | Detail, Stats | — | Height variants |
| Filter Bar | `.filter-bar` | Campaigns, Pipeline, Stats | focus | Generic, no wrapping issues |
| Search Box | `.search-box`, `.search-icon` | Campaigns, Pipeline, Detail | — | Icon prefix pattern, clean |
| Campaign Item | `.campaign-item` | Campaign list | hover, active | Clean but needs active state polish |
| Loading | `.loading` | All | — | Just centered text — replace with skeleton |
| Table | `table`, `th`, `td`, `.number`, `.positive`, `.negative` | All | row hover | Foundation is solid |
| Sidebar | `.sidebar`, `.sidebar-header` | All | sticky | Responsive breaks to static |
| Pagination | `.pagination`, `.page-info` | Campaign list | disabled prev/next | Functional but unstyled |
| Log Panel | `.log-panel`, `.log-header`, `.log-content` | Pipeline | — | Functional, but log area needs line numbers |
| Detail Header | `.detail-header`, `.detail-actions` | Detail | — | Clean layout |
| Campaign Meta | `.campaign-meta`, `.meta-tags`, `.badge`, `.meta-item` | Detail | — | Clean |

### Code Quality Observations

- **Backend (app.py)**: Well-structured. Clean app factory, consistent error envelope, good separation of concerns. No issues.
- **Templates (Jinja2)**: Clean inheritance from `base.html`. Each page extends with `{% block content %}` and `{% block scripts %}`. Minimal inline JS. Well-structured.
- **CSS**: Good use of CSS custom properties (design tokens). Color palette is cohesive (GitHub-dark inspired). Layout uses CSS Grid effectively. The problem is organizational — components are mixed together, naming is inconsistent (`.status-badge` vs `.campaign-status`), and the `.tab-panel`/`.tab-pane` bug proves no one tested tabs.
- **JS**: The IIFE pattern with `window.Dashboard` exposure is reasonable for an MVP. The API client abstraction (`apiGet`/`apiPost`) is good. `escapeHtml()` utility is present. But the polling lifecycle is broken, error handling is too silent, and there's no modular separation.

### Performance Concerns

1. **Plotly bundle**: 3.5MB loaded from CDN with no code-splitting. Consider lazy-loading Plotly only on pages with charts.
2. **Polling frequency**: 5-second intervals on all pages. Stats and campaign detail don't need polling at all. Campaign list and pipeline could use 10-15s with WebSocket fallbacks.
3. **No data diffing**: Every poll replaces all DOM content. Even if only one campaign changed, the entire table is rebuilt.
4. **Chart duplication**: Stats page renders 4 histograms + 1 main chart. If all load at once, 5 Plotly instances render in parallel.
5. **CSS file**: 646 lines is fine. No overfetching.
6. **JS file**: 674 lines is fine. No bundle concerns.

### Key Findings (Top 10)

1. **🔴 Tabs are broken** — `.tab-panel` vs `.tab-pane` CSS class mismatch means tab switching has never worked
2. **🔴 `alert()` for user feedback** — Report generation uses blocking browser dialogs; needs a notification system
3. **🔴 Orphaned polling timers** — `setInterval` is never cleared and gets overwritten without cleanup
4. **🔴 Silent error handling** — `if (!result.success) return` swallows all errors; user sees stale UI forever
5. **🔴 No loading states** — Text "Loading..." is the only indicator; needs skeleton screens
6. **🔴 No empty states** — Zero campaigns shows an empty table with no guidance
7. **🟡 CSS `.metric-value` conflict** — Two definitions cause confusion and potential maintenance bugs
8. **🟡 `Plotly.newPlot` instead of `Plotly.react`** — Charts destroy/recreate DOM on every update instead of diffing
9. **🟡 No accessibility** — Zero ARIA attributes, no keyboard nav, no focus management, no screen reader support
10. **🟡 No mobile responsiveness** — Only one breakpoint at 1024px; below that, the grid collapses to single column but no further optimization

### Approaches

1. **Incremental Bug-Fix Pass** — Fix the tab panel bug, replace `alert()` with a minimal toast, add `clearInterval` on polling, add basic loading/empty states
   - Pros: Low effort, low risk, fixes critical bugs
   - Cons: Won't achieve "professional financial-grade" look; code remains messy
   - Effort: **Low** (2-3 days)

2. **CSS Overhaul + JS Rewrite** — Reorganize CSS with BEM-like naming, fix all conflicts, modularize JS into concerns (api, charts, pages, utils), add proper UX states and transitions, fix accessibility, improve responsive design
   - Pros: Professional result, maintainable codebase, solves all UX/accessibility issues
   - Cons: Medium effort, some risk of visual regression
   - Effort: **Medium** (1-2 weeks)

3. **Full SPA Migration** — Migrate to React/Vue/Svelte with Vite build step, component library, full test coverage
   - Pros: Most modern, best DX, rich ecosystem
   - Cons: High effort, requires build tooling, removes simplicity of Flask+Jinja2 pattern, overkill for 4 pages, breaks the existing server-rendered architecture
   - Effort: **High** (3-4 weeks)

### Recommendation

**Approach 2: CSS Overhaul + JS Rewrite**. The Flask backend is solid and should be preserved. The existing Jinja2 template structure (block inheritance, page-level scripts) is already well-organized. The problems are entirely in the frontend layer — CSS organization/quality and JS architecture.

Specifically:
- Keep Flask + Jinja2. Do NOT add a JS framework.
- Rewrite CSS with a consistent naming convention (BEM or similar utility approach). Fix the `.metric-value` conflict, unify `.status-badge`/`.campaign-status`, add `prefers-reduced-motion`.
- Modularize JS: separate files or clear module pattern for API client, chart renderers, page controllers, and utilities.
- Add a toast/notification system to replace `alert()`.
- Implement proper polling lifecycle (start/stop with visibility API).
- Add loading skeletons, empty states, and error states with retry buttons.
- Add full ARIA support for tabs, navigation, dynamic content, and keyboard interactions.
- Use `Plotly.react()` instead of `newPlot()`.
- Add 2 more responsive breakpoints (768px tablet, 480px mobile) with sidebar collapsible on mobile.
- Update the openspec to include UX and accessibility requirements.

### Risks

- **Tab fix visual regression**: The tab panel/pane mismatch means the current detail page shows ALL tab content stacked vertically. Fixing it will change the existing visual — some users may be surprised. This is actually a bug fix, not a regression, but worth noting.
- **CSS rewrite scope creep**: Without clear boundaries, the CSS rewrite could expand into every corner of the file. Must scope to dashboard components only.
- **Polling lifecycle changes**: Changing `setInterval` behavior may break real-time pipeline monitoring if not done carefully. Must use `requestAnimationFrame` or visibility-based polling.
- **No existing tests for frontend**: No test suite to validate the rewrite. Visual regression testing is manual unless a tool like Percy or Chromatic is added.
- **Plotly configuration changes**: Switching from `newPlot` to `react` may change chart behavior during rapid updates.

### Ready for Proposal

**Yes**. The exploration is complete. The orchestrator should move to the **propose** phase. Tell the user:
- The fundamental architecture (Flask + Jinja2 templates + low-JS) is sound and should be preserved
- The critical bug (tab panel class mismatch) needs an immediate fix regardless of approach
- The recommended approach is a CSS overhaul + JS rewrite (Approach 2) — medium effort, professional result
- The backend (`app.py`) needs no changes — the problems are entirely frontend
