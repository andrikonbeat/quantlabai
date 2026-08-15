"""Tests for dashboard API endpoints."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from quantlab.pipeline.models import PipelineRun, StageRun, StageStatus
from sdk.quantlab.dashboard.app import ServerConfig, resolve_sqcli_binary

from .seed import seed_campaign, seed_campaign_without_metrics, seed_export_data


class TestSqcliPathResolution:
    """DSH-01: sqcli binary resolution precedence and unavailable reporting."""

    def _make_sqcli_dir(self, tmp_path, name):
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "sqcli").touch()
        return d

    def test_env_path_used_when_set(self, tmp_path, monkeypatch):
        env_dir = self._make_sqcli_dir(tmp_path, "env-bin")
        monkeypatch.setenv("SQX_INSTALL_PATH", str(env_dir))
        binary = resolve_sqcli_binary(None)
        assert binary is not None
        assert Path(binary) == (env_dir / "sqcli").resolve()

    def test_config_overrides_env(self, tmp_path, monkeypatch):
        env_dir = self._make_sqcli_dir(tmp_path, "env-bin")
        cfg_dir = self._make_sqcli_dir(tmp_path, "cfg-bin")
        monkeypatch.setenv("SQX_INSTALL_PATH", str(env_dir))
        config = ServerConfig(sqx_install_path=str(cfg_dir))
        binary = resolve_sqcli_binary(config)
        assert Path(binary) == (cfg_dir / "sqcli").resolve()

    def test_unresolvable_returns_none_and_app_reports_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SQX_INSTALL_PATH", raising=False)
        config = ServerConfig(sqx_install_path=str(tmp_path / "no-such-dir"))
        with patch(
            "sdk.quantlab.dashboard.app.DEFAULT_SQX_INSTALL_PATH",
            str(tmp_path / "no-default"),
        ):
            assert resolve_sqcli_binary(config) is None
            with patch("sdk.quantlab.dashboard.app.CliRunner"):
                from sdk.quantlab.dashboard.app import create_app

                app = create_app(config=config)
        assert app.config["SQCLI_PATH"] is None
        assert app.config["CLI_RUNNER"] is None
        assert "sqcli unavailable" in app.config["SQCLI_UNAVAILABLE"]


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

    def test_campaigns_returns_empty_list_when_no_campaigns(self, store_client):
        """Isolated lake: no seeded campaigns means an empty list (hermetic)."""
        client, _store = store_client
        resp = client.get("/api/campaigns")
        data = resp.get_json()
        assert data["data"] == []

    def test_campaigns_entries_carry_spec_field_contract(self, store_client):
        """Each entry SHALL carry campaign_id, market, timeframe, sharpe,
        profit_factor, win_rate, status, total_return."""
        client, store = store_client
        seed_campaign(store, "campaign-123")
        resp = client.get("/api/campaigns")
        assert resp.status_code == 200
        entries = resp.get_json()["data"]
        assert len(entries) == 1
        entry = entries[0]
        for field in (
            "campaign_id",
            "market",
            "timeframe",
            "sharpe",
            "profit_factor",
            "win_rate",
            "status",
            "total_return",
        ):
            assert field in entry, f"campaign entry missing spec field '{field}'"
        assert entry["campaign_id"] == "campaign-123"
        assert entry["market"] == "EURUSD"
        assert entry["timeframe"] == "H1"
        assert entry["sharpe"] == 1.5
        assert entry["profit_factor"] == 1.8
        assert entry["win_rate"] == 0.55
        assert entry["status"] == "completed"
        assert entry["total_return"] == 0.18

    def test_campaigns_missing_metadata_is_empty_safe(self, store_client):
        """Entries without market/timeframe/status metadata surface None."""
        client, store = store_client
        seed_campaign_without_metrics(
            store,
            "bare-campaign",
            market=None,
            timeframe=None,
            status=None,
        )
        resp = client.get("/api/campaigns")
        assert resp.status_code == 200
        entry = resp.get_json()["data"][0]
        assert entry["market"] is None
        assert entry["timeframe"] is None
        assert entry["status"] is None
        assert entry["sharpe"] is None
        assert entry["total_return"] is None


class TestCampaignDetailEndpoint:
    """GET /api/campaigns/<id> returns campaign detail."""

    def test_campaign_detail_returns_404_for_missing(self, client):
        resp = client.get("/api/campaigns/nonexistent")
        assert resp.status_code == 404

    def test_campaign_detail_returns_json(self, client):
        resp = client.get("/api/campaigns/nonexistent")
        assert resp.content_type == "application/json"

    def test_campaign_detail_returns_real_sections(self, store_client):
        """Detail sections (equity_curve, trades, statistics) come from the
        lake's real export data, not hardcoded empties."""
        client, store = store_client
        seed_campaign(store, "campaign-123")
        seed_export_data(store, "campaign-123")
        resp = client.get("/api/campaigns/campaign-123")
        assert resp.status_code == 200
        entry = resp.get_json()["data"]
        assert entry["campaign_id"] == "campaign-123"
        assert len(entry["equity_curve"]) == 2
        assert entry["equity_curve"][0]["equity"] == 100000.0
        assert len(entry["trades"]) == 2
        assert entry["trades"][0]["profit"] == 150.0
        assert entry["statistics"]["total_trades"] == 120
        assert entry["phases"] == []
        assert "equity" not in entry  # renamed to equity_curve per spec

    def test_campaign_detail_returns_404_for_absent_id(self, store_client):
        client, store = store_client
        seed_campaign(store, "campaign-123")
        resp = client.get("/api/campaigns/other-campaign")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "CAMPAIGN_NOT_FOUND"


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

    def test_pipeline_detail_returns_stages(self, store_client):
        """Detail shows stages with name/status/duration/error from a real
        seeded run."""
        client, store = store_client
        run = PipelineRun(
            run_id="pipe-run-abc",
            pipeline_name="research",
            stages=[
                StageRun(name="data", status=StageStatus.COMPLETED, duration=1.5),
                StageRun(name="analyze", status=StageStatus.FAILED, duration=0.5, error="boom"),
            ],
        )
        store.save_pipeline_run(run)
        resp = client.get("/api/pipeline/pipe-run-abc")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["run_id"] == "pipe-run-abc"
        assert len(data["stages"]) == 2
        assert data["stages"][0]["name"] == "data"
        assert data["stages"][0]["status"] == "completed"
        assert data["stages"][0]["duration"] == 1.5
        assert data["stages"][1]["name"] == "analyze"
        assert data["stages"][1]["error"] == "boom"


class TestStatsEndpoint:
    """GET /api/stats returns aggregated statistics."""

    def test_stats_returns_200(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_stats_returns_json(self, client):
        resp = client.get("/api/stats")
        assert resp.content_type == "application/json"

    def test_stats_empty_safe_zeros(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        stats = resp.get_json()["data"]
        assert stats["sharpe_mean"] == 0.0
        assert stats["sharpe_std"] == 0.0
        assert stats["max_drawdown_pct"] == 0.0
        assert stats["win_rate_mean"] == 0.0
        assert stats["total_trades"] == 0
        assert stats["benchmark_comparison"] is None

    def test_stats_returns_aggregated_spec_fields(self, store_client):
        client, store = store_client
        seed_campaign(
            store,
            "campaign-a",
            metrics={
                "sharpe_ratio": 1.0,
                "win_rate": 0.5,
                "max_drawdown": -10.0,
                "total_trades": 100,
            },
        )
        seed_campaign(
            store,
            "campaign-b",
            metrics={
                "sharpe_ratio": 2.0,
                "win_rate": 0.6,
                "max_drawdown": -14.0,
                "total_trades": 200,
            },
        )
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        stats = resp.get_json()["data"]
        assert stats["sharpe_mean"] == 1.5
        assert stats["sharpe_std"] == pytest.approx(0.707106, abs=1e-5)
        assert stats["max_drawdown_pct"] == -12.0
        assert stats["win_rate_mean"] == 0.55
        assert stats["total_trades"] == 300
        assert stats["benchmark_comparison"] is None
        assert stats["total_campaigns"] == 2
        assert "generated_at" in stats


class TestReportGenerationEndpoint:
    """POST /api/reports/generate triggers report generation."""

    def test_report_generate_uses_real_export_data(self, store_client):
        """The report contains real trades/equity/statistics and the response
        carries the spec'd result fields."""
        client, store = store_client
        seed_export_data(store, "campaign-123")
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "campaign-123", "formats": ["html", "json"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        for field in (
            "campaign_id",
            "html_path",
            "json_path",
            "charts_generated",
            "generation_time_ms",
        ):
            assert field in data, f"report result missing '{field}'"
        assert data["campaign_id"] == "campaign-123"
        assert isinstance(data["charts_generated"], list)

        json_path = Path(data["json_path"])
        assert json_path.exists(), f"json report not written at {json_path}"
        report = json.loads(json_path.read_text(encoding="utf-8"))
        assert report["campaign_id"] == "campaign-123"
        assert report["trade_count"] == 2
        assert len(report["equity_curve"]) == 2
        assert report["statistics"]["total_trades"] == 120
        assert report["statistics"]["sharpe_ratio"] == 1.5

    def test_report_generate_returns_json(self, store_client):
        client, store = store_client
        seed_export_data(store, "campaign-123")
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "campaign-123"},
        )
        assert resp.content_type == "application/json"
        assert resp.get_json()["success"] is True

    def test_report_generate_404_for_missing_campaign(self, store_client):
        """A genuinely absent campaign id returns 404 with the error envelope."""
        client, store = store_client
        resp = client.post(
            "/api/reports/generate",
            json={"campaign_id": "campaign-does-not-exist"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "CAMPAIGN_NOT_FOUND"

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
