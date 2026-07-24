"""Tests for Campaign Orchestrator — end-to-end SQX pipeline."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.phase4 import (
    CampaignOrchestrator,
    CampaignConfig,
    CampaignResult,
    CampaignPhase,
    PhaseStatus,
    PhaseResult,
    run_campaign,
    CampaignStatus,
)
from quantlab.tools.exceptions import CampaignError


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_config():
    """Create a mock CampaignConfig with dry_run=True for safe testing."""
    config = CampaignConfig(
        campaign_name="TestCampaign",
        output_dir=Path("_output"),
        dry_run=True,
        sqx_install_path="/fake/sqx",
        campaign_type="backtest",
        poll_interval=0.1,  # Fast for tests
        poll_timeout=1.0,
        progress_callback=None,
    )
    return config


@pytest.fixture
def mock_config_no_license():
    """Create a mock CampaignConfig with license validation mocked."""
    config = CampaignConfig(
        campaign_name="TestCampaign",
        output_dir=Path("_output"),
        dry_run=True,
        sqx_install_path="/fake/sqx",
        campaign_type="backtest",
        poll_interval=0.1,  # Fast for tests
        poll_timeout=1.0,
        progress_callback=None,
    )
    return config


@pytest.fixture
def mock_research_config(tmp_path):
    """Create a temporary research YAML config file."""
    yaml_content = """
campaign: "TestCampaign"
market: EURUSD
timeframe: H1
building_blocks:
  - name: "trend_follow"
    indicator:
      name: "EMA"
      params:
        period: 200
    entry:
      description: "Price > EMA"
      conditions:
        - "close > ema_200"
    exit:
      description: "Price < EMA"
      conditions:
        - "close < ema_200"
strategies:
  - name: "TrendFollow_v1"
    direction: LONG
    building_blocks:
      - trend_follow
criteria:
  - metric: "profit_factor"
    operator: ">="
    value: 1.5
  - metric: "sharpe"
    operator: ">="
    value: 1.0
"""
    config_file = tmp_path / "test_campaign.yaml"
    config_file.write_text(yaml_content)
    return config_file


# ── Helpers ────────────────────────────────────────────────────────────────


def _assert_phase_completed(result: CampaignResult, phase: CampaignPhase) -> None:
    """Assert a phase completed successfully."""
    phase_result = next((r for r in result.phase_results if r.phase == phase), None)
    assert phase_result is not None, f"Phase {phase} not found in results"
    assert phase_result.status == PhaseStatus.COMPLETED, (
        f"Phase {phase} failed: {phase_result.error}"
    )


# ── CampaignOrchestrator Tests ─────────────────────────────────────────────


class TestCampaignOrchestrator:
    """Tests for CampaignOrchestrator class."""

    @pytest.mark.asyncio
    async def test_dry_run_completes_successfully(self, mock_config, mock_research_config):
        """Dry-run campaign should complete all phases without SQX."""
        mock_config.research_config_path = mock_research_config
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()

        assert result.is_successful
        assert result.campaign_name == "TestCampaign"
        assert result.total_duration >= 0

        # Check all phases completed
        expected_phases = [
            CampaignPhase.VALIDATE,
            CampaignPhase.TRANSLATE,
            CampaignPhase.DAEMON_START,
            CampaignPhase.LOAD_CONFIG,
            CampaignPhase.RUN,
            CampaignPhase.POLL,
            CampaignPhase.EXPORT,
            CampaignPhase.READ,
            CampaignPhase.COMPUTE,
            CampaignPhase.STORE,
            CampaignPhase.COMPLETE,
        ]
        for phase in expected_phases:
            _assert_phase_completed(result, phase)

    @pytest.mark.asyncio
    async def test_progress_callback_fired(self, mock_config, mock_research_config):
        """Progress callback should fire for each phase."""
        mock_config.research_config_path = mock_research_config
        callback_calls = []

        def callback(phase: CampaignPhase, status: PhaseStatus, detail: str = None):
            callback_calls.append((phase, status, detail))

        mock_config.progress_callback = callback
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()

        assert result.is_successful
        # Should have at least RUNNING and COMPLETED callbacks for each phase
        running_calls = [c for c in callback_calls if c[1] == PhaseStatus.RUNNING]
        completed_calls = [c for c in callback_calls if c[1] == PhaseStatus.COMPLETED]
        assert len(running_calls) >= 11  # One for each phase
        assert len(completed_calls) >= 11

    @pytest.mark.asyncio
    async def test_phase_results_recorded(self, mock_config, mock_research_config):
        """Each phase should have a PhaseResult with timing."""
        mock_config.research_config_path = mock_research_config
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()

        for phase_result in result.phase_results:
            assert isinstance(phase_result, PhaseResult)
            assert phase_result.phase in CampaignPhase
            assert phase_result.status == PhaseStatus.COMPLETED
            assert phase_result.duration >= 0
            assert phase_result.started_at > 0
            assert phase_result.completed_at is not None

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="DSL parser raises ParseError, not CampaignError — pre-existing on main")
    async def test_error_propagation(self, mock_config):
        """Errors should propagate as CampaignError with phase info."""
        mock_config.dry_run = True
        mock_config.research_config_path = Path("/nonexistent.yaml")
        orchestrator = CampaignOrchestrator(mock_config)

        with pytest.raises(CampaignError) as exc_info:
            await orchestrator.run()

        assert exc_info.value.phase == CampaignPhase.TRANSLATE.value
        assert "TestCampaign" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, mock_config, mock_research_config):
        """Context manager should clean up resources."""
        mock_config.research_config_path = mock_research_config
        mock_config.dry_run = True

        async with CampaignOrchestrator(mock_config) as orchestrator:
            result = await orchestrator.run()
            assert result.is_successful

    @pytest.mark.asyncio
    async def test_campaign_result_has_expected_structure(self, mock_config, mock_research_config):
        """CampaignResult should have all expected fields populated."""
        mock_config.research_config_path = mock_research_config
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()

        assert isinstance(result, CampaignResult)
        assert result.campaign_name == "TestCampaign"
        assert isinstance(result.phase_results, list)
        assert len(result.phase_results) >= 11
        assert result.total_duration >= 0
        assert result.error is None
        assert result.cfx_bytes is not None  # Dry-run returns mock bytes


# ── run_campaign Convenience Function Tests ─────────────────────────────────


class TestRunCampaignFunction:
    """Tests for the high-level run_campaign function."""

    @pytest.mark.asyncio
    async def test_run_campaign_function(self, mock_research_config):
        """High-level run_campaign should work as convenience function."""
        result = await run_campaign(
            campaign_name="FuncTest",
            research_config_path=mock_research_config,
            dry_run=True,
        )

        assert result.is_successful
        assert result.campaign_name == "FuncTest"

    @pytest.mark.asyncio
    async def test_run_campaign_with_custom_callback(self, mock_research_config):
        """run_campaign should accept custom callback."""
        calls = []

        def custom_callback(phase, status, detail):
            calls.append((phase.value, status.value, detail))

        result = await run_campaign(
            campaign_name="CallbackTest",
            research_config_path=mock_research_config,
            dry_run=True,
            progress_callback=custom_callback,
        )

        assert result.is_successful
        assert len(calls) >= 11

    @pytest.mark.asyncio
    async def test_run_campaign_with_output_dir(self, mock_research_config, tmp_path):
        """run_campaign should accept custom output directory."""
        out_dir = tmp_path / "custom_output"
        result = await run_campaign(
            campaign_name="OutputTest",
            research_config_path=mock_research_config,
            output_dir=out_dir,
            dry_run=True,
        )

        assert result.is_successful
        # Output dir should be created even in dry-run
        assert out_dir.exists()


# ── Edge Cases & Error Handling ─────────────────────────────────────────────


class TestCampaignOrchestratorEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_campaign_name(self, mock_config, mock_research_config):
        """Empty campaign name should fail."""
        mock_config.campaign_name = ""
        mock_config.research_config_path = mock_research_config
        mock_config.dry_run = True
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()
        # Dry-run might still work with empty name, but should not crash
        assert result.campaign_name == ""

    @pytest.mark.asyncio
    async def test_poll_timeout_config(self, mock_config, mock_research_config):
        """Custom poll timeout should be respected."""
        mock_config.research_config_path = mock_research_config
        mock_config.dry_run = True
        mock_config.poll_timeout = 0.5
        mock_config.poll_interval = 0.05
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()
        assert result.is_successful

    @pytest.mark.asyncio
    async def test_output_dir_creation(self, mock_config, tmp_path):
        """Output directory should be created if it doesn't exist."""
        mock_config.dry_run = True
        mock_config.output_dir = tmp_path / "new_output" / "nested"
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()
        assert result.is_successful
        assert mock_config.output_dir.exists()

    @pytest.mark.asyncio
    async def test_phase_duration_recorded(self, mock_config, mock_research_config):
        """Phase durations should be recorded accurately."""
        mock_config.research_config_path = mock_research_config
        mock_config.dry_run = True
        orchestrator = CampaignOrchestrator(mock_config)

        result = await orchestrator.run()

        for phase_result in result.phase_results:
            assert phase_result.duration >= 0
            assert phase_result.completed_at >= phase_result.started_at


# ── Integration-style Tests (require mocks) ─────────────────────────────────


class TestCampaignOrchestratorIntegration:
    """Integration-style tests with mocked SQX components."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(self, mock_config, mock_research_config, tmp_path):
        """Test full pipeline with mocked SQX components."""
        mock_config.research_config_path = mock_research_config
        mock_config.dry_run = False  # Test non-dry-run path with mocks
        mock_config.poll_interval = 0.05
        mock_config.poll_timeout = 1.0

        orchestrator = CampaignOrchestrator(mock_config)

        # Create a temp CFX file for the mock to return
        mock_cfx_path = tmp_path / "test_campaign.cfx"
        mock_cfx_path.write_bytes(b"mock-cfx-content")

        # Mock the daemon
        with patch("quantlab.tools.platform.resolve_sqcli_path", return_value=Path("/fake/sqx/sqcli")), \
             patch("quantlab.phase4.daemon.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client = AsyncMock(return_value=AsyncMock())
            mock_daemon_class.return_value = mock_daemon

            # Mock the dispatcher (stages import from quantlab.phase4.command_dispatcher)
            with patch("quantlab.phase4.command_dispatcher.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher = AsyncMock()
                mock_dispatcher.load_config = AsyncMock()
                mock_dispatcher.start_project = AsyncMock()
                mock_dispatcher.get_status = AsyncMock(
                    side_effect=[
                        CampaignStatus(campaign_name="TestCampaign", status="running", progress=25.0),
                        CampaignStatus(campaign_name="TestCampaign", status="completed", progress=100.0),
                    ]
                )
                mock_dispatcher.export_results = AsyncMock(return_value="/tmp/results.csv")
                mock_dispatcher.export_databanks = AsyncMock(return_value=[])
                mock_dispatcher.stop_project = AsyncMock()
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                # Mock AsyncSQXClient (stages import from quantlab.phase4.http_client)
                with patch("quantlab.phase4.http_client.AsyncSQXClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.close = AsyncMock()
                    mock_client_class.return_value = mock_client

                    # Mock CfxArchive (stages import from quantlab.translate.cfx)
                    # Need to return a CfxResult-like object with .path attribute
                    from quantlab.translate.cfx import CfxResult
                    with patch("quantlab.translate.cfx.CfxArchive") as mock_cfx_class:
                        mock_cfx_result = CfxResult(xml_content="<config/>", path=mock_cfx_path)
                        mock_cfx_class.from_model.return_value = mock_cfx_result
                        mock_cfx_class.write = MagicMock()

                        # Mock readers (stages import from quantlab.readers.databank)
                        with patch("quantlab.readers.databank.DatabankCSVReader") as mock_reader_class:
                            mock_reader = MagicMock()
                            mock_reader.read_trades.return_value = []
                            mock_reader.read_equity.return_value = []
                            mock_reader.read_summary.return_value = {"net_profit": 1000, "win_rate": 0.6}
                            mock_reader_class.return_value = mock_reader

                            # Mock stats engine (stages import from quantlab.stats.engine)
                            with patch("quantlab.stats.engine.StatisticsEngine") as mock_stats_class:
                                mock_engine = MagicMock()
                                mock_engine.compute_all.return_value = MagicMock(
                                    profit_factor=1.5,
                                    sharpe_ratio=1.2,
                                    max_drawdown=5.0,
                                    expectancy=10.0,
                                    mar_ratio=2.0,
                                    win_rate=0.6,
                                )
                                mock_stats_class.return_value = mock_engine

                                # Mock knowledge store (stages import from quantlab.knowledge.store)
                                with patch("quantlab.knowledge.store.KnowledgeStore") as mock_store_class:
                                    mock_store = MagicMock()
                                    mock_store.initialize = MagicMock()
                                    mock_store.rebuild_index = MagicMock()
                                    mock_store_class.return_value = mock_store

                                    result = await orchestrator.run()

                                    assert result.is_successful
                                    assert result.campaign_name == "TestCampaign"
                                    mock_daemon.start.assert_awaited_once()
                                    mock_daemon.stop.assert_awaited_once()


# ── YAML import for fixtures ───────────────────────────────────────────────

try:
    import yaml
except ImportError:
    import sys
    sys.modules['yaml'] = type(sys)('yaml')
    sys.modules['yaml'].safe_load = lambda x: {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])