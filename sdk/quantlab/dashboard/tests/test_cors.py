"""Tests for Flask CORS enablement on mobile dev endpoints."""
from __future__ import annotations

import pytest
from flask import Flask

from quantlab.dashboard.app import create_app


class TestFlaskCors:
    """CORS contract: mobile dev origin MUST receive Access-Control-Allow-Origin."""

    @pytest.fixture()
    def app(self) -> Flask:
        return create_app()

    @pytest.fixture()
    def client(self, app: Flask):
        return app.test_client()

    def test_health_returns_cors_header_for_mobile_origin(self, client):
        resp = client.get(
            "/api/health",
            headers={"Origin": "http://10.0.2.2:8080"},
        )
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "http://10.0.2.2:8080"

    def test_health_allows_get_method(self, client):
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://10.0.2.2:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "Access-Control-Allow-Methods" in resp.headers
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]

    def test_campaigns_returns_cors_header_for_emulator_origin(self, client):
        resp = client.get(
            "/api/campaigns",
            headers={"Origin": "http://10.0.3.2:8080"},
        )
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_stats_returns_cors_header_for_localhost_origin(self, client):
        resp = client.get(
            "/api/stats",
            headers={"Origin": "http://127.0.0.1:8080"},
        )
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8080"
