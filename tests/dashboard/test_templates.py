"""Tests for dashboard Jinja2 templates render correctly."""

import pytest


class TestTemplateRendering:
    """All dashboard pages render their templates without errors."""

    def test_base_template_exists(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"QuantLab" in resp.data or b"dashboard" in resp.data.lower()

    def test_campaign_list_template_renders(self, client):
        resp = client.get("/campaigns")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_campaign_detail_template_renders(self, client):
        # Campaign detail requires a valid campaign_id with data;
        # the template gracefully handles missing campaign via default filter.
        resp = client.get("/campaigns/nonexistent")
        assert resp.status_code == 200

    def test_pipeline_monitor_template_renders(self, client):
        resp = client.get("/pipeline")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_stats_dashboard_template_renders(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_all_templates_contain_navigation(self, client):
        pages = ["/", "/campaigns", "/pipeline", "/stats"]
        for page in pages:
            resp = client.get(page)
            assert resp.status_code == 200
            html = resp.data.decode("utf-8")
            assert "nav" in html.lower() or "header" in html.lower()

    def test_templates_contain_dashboard_root(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "dashboard" in html.lower()