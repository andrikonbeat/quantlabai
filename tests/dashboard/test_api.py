"""Tests for dashboard API endpoints."""

import pytest


class TestHealthEndpoint:
    """GET /api/health returns server status."""

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_json(self, client):
        resp = client.get("/api/health")
        assert resp.content_type == "application/json"

    def test_health_returns_status_ok(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == "ok"


class TestCampaignsEndpoint:
    """GET /api/campaigns returns campaign list."""

    def test_campaigns_returns_200(self, client):
        resp = client.get("/api/campaigns")
        assert resp.status_code == 200

    def test_campaigns_returns_json(self, client):
        resp = client.get("/api/campaigns")
        assert resp.content_type == "application/json"

    def test_campaigns_returns_list(self, client):
        resp = client.get("/api/campaigns")
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


class TestCampaignDetailEndpoint:
    """GET /api/campaigns/<id> returns campaign detail."""

    def test_campaign_detail_returns_404_for_missing(self, client):
        resp = client.get("/api/campaigns/nonexistent")
        assert resp.status_code == 404

    def test_campaign_detail_returns_json(self, client):
        resp = client.get("/api/campaigns/nonexistent")
        assert resp.content_type == "application/json"


class TestPipelineEndpoint:
    """GET /api/pipeline returns pipeline runs."""

    def test_pipeline_returns_200(self, client):
        resp = client.get("/api/pipeline")
        assert resp.status_code == 200

    def test_pipeline_returns_json(self, client):
        resp = client.get("/api/pipeline")
        assert resp.content_type == "application/json"

    def test_pipeline_returns_list(self, client):
        resp = client.get("/api/pipeline")
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


class TestPipelineDetailEndpoint:
    """GET /api/pipeline/<id> returns pipeline run detail."""

    def test_pipeline_detail_returns_404_for_missing(self, client):
        resp = client.get("/api/pipeline/nonexistent")
        assert resp.status_code == 404


class TestStatsEndpoint:
    """GET /api/stats returns aggregated statistics."""

    def test_stats_returns_200(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_stats_returns_json(self, client):
        resp = client.get("/api/stats")
        assert resp.content_type == "application/json"


class TestReportGenerationEndpoint:
    """POST /api/reports/generate triggers report generation."""

    def test_report_generate_returns_200(self, client):
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "test-campaign"},
        )
        assert resp.status_code == 200

    def test_report_generate_returns_json(self, client):
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "test-campaign"},
        )
        assert resp.content_type == "application/json"

    def test_report_generate_requires_campaign_id(self, client):
        resp = client.post(
            "/api/reports/generate",
            json={},
        )
        assert resp.status_code == 400


class TestDashboardPages:
    """HTML page routes return templates."""

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_campaigns_page_returns_200(self, client):
        resp = client.get("/campaigns")
        assert resp.status_code == 200

    def test_pipeline_page_returns_200(self, client):
        resp = client.get("/pipeline")
        assert resp.status_code == 200

    def test_stats_page_returns_200(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200