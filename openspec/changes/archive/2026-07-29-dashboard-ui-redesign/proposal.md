# Proposal: Dashboard UI Redesign — Professional Financial Interface

## Intent

Current dashboard is MVP-grade: flat dark theme, **broken tabs** (CSS class mismatch), `alert()` UX, silent error handling, orphaned polling timers, no loading/empty/error states, zero accessibility, no responsive design. Users see stale data, blocking dialogs, and unprofessional visuals. This redesign transforms the frontend into a professional quantitative trading interface while keeping Flask + Jinja2 untouched.

## Scope

### In Scope
- Design token system (3-level: global, semantic, component) with Navy/quantitative palette
- CSS monolith split into layered components (BEM + `@layer`), 8 component files, 2 layout files
- JS monolith (674 lines) → ES modules with pub/sub stores, unified polling + AbortController
- Global Plotly customization (font, gridcolors, `Plotly.react`, qualitative-financial palette)
- UI components: MetricCard, DataTable, Tabs (ARIA), StatusBadges, Toast, Skeleton, EmptyStates
- Page-specific rewrites: Campaign List, Campaign Detail, Pipeline Monitor, Stats Dashboard
- Responsive design (3 breakpoints), WCAG 2.1 AA, prefers-reduced-motion
- Sidebar redesign: collapsible sections, sticky search with debounce, scroll persistence

### Out of Scope
- Backend Python, Flask routes, API response format
- Plotly library swap or removal
- Authentication, authorization
- Routing/library framework (no React/Vue/Svelte)

## Capabilities

### New Capabilities
- None (all changes modify existing dashboard-ui capability)

### Modified Capabilities
- `dashboard-ui`: requirements expanded to include design system tokens, component CSS architecture, ES module JS architecture, responsive design, WCAG 2.1 AA accessibility, loading/empty/error states, micro-interactions, global Plotly customization, toast notifications, and sidebar collapsible sections with search debounce

## Approach

CSS Overhaul + JS Rewrite (keep Flask + Jinja2, no JS framework). Deliver in 6 chained PRs by page slice due to 400-line review budget: (1) Design System + base layout + MetricCard, (2) Campaign List, (3) Campaign Detail, (4) Pipeline Monitor, (5) Stats Dashboard, (6) Polish + accessibility pass. Stacked-to-main via `auto-chain`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/dashboard/static/dashboard.css` | Removed | Split into component CSS files |
| `sdk/quantlab/dashboard/static/dashboard.js` | Removed | Split into ES modules |
| `sdk/quantlab/dashboard/static/css/` | New | Component CSS architecture (8+ files) |
| `sdk/quantlab/dashboard/static/js/` | New | ES module architecture (15+ files) |
| All 4 templates | Modified | ARIA, skeleton, empty states, toasts |
| `openspec/specs/dashboard-ui/spec.md` | Modified | Expanded requirements (UX, a11y, responsive) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tab fix reveals hidden content (currently ALL tabs visible) | High | Preview with PM before deploy; version as breaking change in release notes |
| No frontend test suite | High | Manual checklist per PR; visual diff on critical pages |
| `Plotly.newPlot` → `Plotly.react` migration quirks | Med | Keep both paths with feature flag; test equity curve rapid updates |
| CSS scope creep | Med | Enforce component CSS inventory; no global rule additions outside design tokens |

## Rollback Plan

Full rollback: restore `dashboard.css` + `dashboard.js` and all 4 templates from git. Per-PR rollback: revert the merge commit for that slice. CSS/JS archiving preserves originals until final polish PR.

## Dependencies

- None external. Plotly already loaded from CDN.

## Success Criteria

- [ ] All 14 acceptance criteria pass (professional visual, skeletons, empty states, error states, sort + pagination, Plotly consistency, fade transitions, WCAG 2.1 AA, sidebar scroll persistence, no `alert()`, no polling leaks, 3 responsive breakpoints, CSS layers, ES modules)
- [ ] Visual audit: all 8 critical/medium issues from exploration closed
- [ ] `alert()` count: 0 in JS modules (replaced by Toast)
- [ ] Tab component: `aria-selected`, keyboard nav, functional switching
