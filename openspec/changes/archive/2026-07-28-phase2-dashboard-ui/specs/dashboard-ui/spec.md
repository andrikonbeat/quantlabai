# Dashboard UI Specification

## Purpose

Defines the browser-based dashboard UI served by the quantlab CLI, providing campaign visualization, pipeline monitoring, statistics, and report generation triggers.

## Requirements

### Requirement: Flask serves HTML templates and static assets

The system MUST serve the dashboard HTML frontend via Flask, with templates at `sdk/quantlab/dashboard/templates/` and static assets (JS, CSS) at `sdk/quantlab/dashboard/static/`.

#### Scenario: Dashboard UI loads at root URL
- GIVEN the dashboard server is running
- WHEN a browser navigates to `http://localhost:8080/`
- THEN the campaign list page renders
- AND Plotly JS is loaded from CDN
- AND CSS and JS static assets load without 404 errors

### Requirement: Campaign list view with sidebar, status badges, search/filter

The system MUST render a campaign list page with a sidebar containing campaign list with status badges, search/filter input, and a summary table (Campaign ID, Market, Timeframe, Sharpe, Profit Factor, Status).

#### Scenario: Campaign list renders with data
- GIVEN campaigns exist in the Knowledge Lake
- WHEN the dashboard loads
- THEN the sidebar displays campaign entries with status badges
- AND the summary table shows Campaign ID, Market, Timeframe, Sharpe, Profit Factor, Status columns
- AND each row is clickable to navigate to campaign detail

#### Scenario: Search filters campaigns
- GIVEN multiple campaigns exist
- WHEN the user types a search term in the filter input
- THEN only campaigns matching the term are displayed
- AND filtering is case-insensitive

### Requirement: Campaign detail view with equity curve, metrics cards, and tabs

The system MUST render a campaign detail page with equity curve chart, metrics cards (Sharpe, Max DD, Win Rate, Total Return), and tabs for Trades, Stages, and Reports.

#### Scenario: Campaign detail renders equity curve and metrics
- GIVEN campaign `campaign-123` exists with equity data
- WHEN the user navigates to `/campaigns/campaign-123`
- THEN the equity curve Plotly chart renders with timestamp on x-axis and equity on y-axis
- AND metrics cards display Sharpe, Max DD, Win Rate, Total Return
- AND the Trades tab shows a trade table with entry/exit time, direction, profit
- AND the Stages tab shows each stage name, status, duration, and error (if any)

### Requirement: Pipeline monitoring view with stage progress and log panel

The system MUST render a pipeline monitoring page showing horizontal step indicators for stages, duration, "View Log" links, and a bottom log panel.

#### Scenario: Pipeline monitor shows stage progress
- GIVEN a pipeline run is in progress
- WHEN the pipeline monitor page loads
- THEN a horizontal step indicator shows each stage with status icon (pending/running/completed/failed)
- AND each stage shows duration and a "View Log" link
- AND the bottom log panel displays recent log output

### Requirement: Statistics dashboard with cross-campaign charts and benchmark overlay

The system MUST render a statistics dashboard with cross-campaign charts (Sharpe distribution, drawdown comparison, win rate), benchmark overlay toggle, and market/timeframe/date filters.

#### Scenario: Statistics dashboard renders charts and filters
- GIVEN multiple campaigns exist across markets
- WHEN the statistics dashboard loads
- THEN a Sharpe distribution chart renders across campaigns
- AND a drawdown comparison chart renders
- AND a benchmark overlay toggle is available
- AND filtering by market narrows the charts

### Requirement: Report generation trigger from UI

The system MUST provide a "Generate Report" button on the campaign detail page that calls the API and displays generation status.

#### Scenario: Report trigger generates and shows result
- GIVEN campaign `campaign-123` exists
- WHEN the user clicks "Generate Report" on the campaign detail page
- THEN a POST request is sent to `/api/reports/generate`
- AND a loading indicator is shown during generation
- AND on completion, a success message with links to HTML and JSON reports is displayed

### Requirement: Plotly charts render client-side from JSON data

The system MUST fetch chart data from API endpoints as JSON and render Plotly charts client-side in the browser.
