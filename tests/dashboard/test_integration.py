"""Integration tests for the dashboard — full request/response cycles."""

import pytest


class TestDashboardIntegration:
    """End-to-end dashboard integration tests."""

    def test_server_starts_and_health_check_passes(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["status"] == "ok"

    def test_campaign_list_page_links_to_api(self, client):
        resp = client.get("/campaigns")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "campaign" in html.lower()

    def test_pipeline_page_links_to_api(self, client):
        resp = client.get("/pipeline")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "pipeline" in html.lower()

    def test_stats_page_links_to_api(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "stat" in html.lower()

    def test_api_campaigns_then_detail_flow(self, client):
        campaigns_resp = client.get("/api/campaigns")
        assert campaigns_resp.status_code == 200
        campaigns = campaigns_resp.get_json()
        assert isinstance(campaigns["data"], list)

        if campaigns["data"]:
            campaign_id = campaigns["data"][0].get("id", campaigns["data"][0].get("campaign_id"))
            if campaign_id:
                detail_resp = client.get(f"/api/campaigns/{campaign_id}")
                assert detail_resp.status_code in (200, 404)

    def test_static_css_served(self, client):
        # Modular CSS entry point (flat dashboard.css monolith was removed).
        resp = client.get("/static/css/design-tokens.css")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/css")

    def test_static_js_served(self, client):
        # Modular JS entry point (flat dashboard.js monolith was removed).
        resp = client.get("/static/js/main.js")
        assert resp.status_code == 200
        assert "javascript" in resp.content_type

    def test_report_generation_endpoint_accepts_post(self, client):
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "test-campaign", "formats": ["html"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_all_pages_return_200(self, client):
        pages = ["/", "/campaigns", "/pipeline", "/stats"]
        for page in pages:
            resp = client.get(page)
            assert resp.status_code == 200, f"Page {page} returned {resp.status_code}"

    def test_api_health_consistent_across_requests(self, client):
        for _ in range(3):
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["data"]["status"] == "ok"