"""Tests for dashboard static assets exist and are served.

The dashboard uses a modular static architecture (see PR6-03): CSS
tokens/components/layouts live under css/ and JS modules under js/.
The flat dashboard.css / dashboard.js monoliths were deleted during
that refactor, so these tests assert the modular entry points.
"""

from pathlib import Path

import pytest

# Resolve paths relative to this test file:
# tests/dashboard/test_static.py -> project_root/sdk/quantlab/dashboard/static
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = PROJECT_ROOT / "sdk" / "quantlab" / "dashboard" / "static"
TEMPLATES_DIR = PROJECT_ROOT / "sdk" / "quantlab" / "dashboard" / "templates"

# Modular entry points that replaced the flat monoliths.
CSS_ENTRY = STATIC_DIR / "css" / "design-tokens.css"
JS_ENTRY = STATIC_DIR / "js" / "main.js"


class TestStaticFilesExist:
    """Dashboard static files are present on disk."""

    def test_css_tokens_exist(self):
        assert CSS_ENTRY.is_file()

    def test_js_main_exist(self):
        assert JS_ENTRY.is_file()

    def test_css_non_empty(self):
        assert CSS_ENTRY.stat().st_size > 0

    def test_js_non_empty(self):
        assert JS_ENTRY.stat().st_size > 0


class TestTemplateFilesExist:
    """Dashboard template files are present on disk."""

    def test_base_html_exists(self):
        assert (TEMPLATES_DIR / "base.html").is_file()

    def test_campaign_list_html_exists(self):
        assert (TEMPLATES_DIR / "campaign_list.html").is_file()

    def test_campaign_detail_html_exists(self):
        assert (TEMPLATES_DIR / "campaign_detail.html").is_file()

    def test_pipeline_monitor_html_exists(self):
        assert (TEMPLATES_DIR / "pipeline_monitor.html").is_file()

    def test_stats_dashboard_html_exists(self):
        assert (TEMPLATES_DIR / "stats_dashboard.html").is_file()


class TestStaticContent:
    """Dashboard static files contain expected content."""

    def test_css_contains_dark_theme(self):
        css = (STATIC_DIR / "css" / "design-tokens.css").read_text()
        assert "dark" in css.lower() or "--color" in css

    def test_js_contains_api_client(self):
        js = (STATIC_DIR / "js" / "api" / "client.js").read_text()
        assert "fetch" in js or "api" in js.lower()

    def test_js_contains_plotly(self):
        js = (STATIC_DIR / "js" / "components" / "ChartContainer.js").read_text()
        assert "Plotly" in js or "plotly" in js.lower()

    def test_js_contains_polling(self):
        js = (STATIC_DIR / "js" / "utils" / "poller.js").read_text()
        assert "poll" in js.lower() or "interval" in js.lower()

    def test_js_contains_navigation(self):
        js = (STATIC_DIR / "js" / "main.js").read_text()
        assert "campaign" in js.lower() or "pipeline" in js.lower()
