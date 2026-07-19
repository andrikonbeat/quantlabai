"""Tests for Phase 4 exception hierarchy."""

import pytest

from quantlab.phase4.errors import (
    Phase4Error,
    JForexError,
    JForexConnectionError,
    JForexStrategyNotFoundError,
    JForexServerError,
    PortfolioError,
    StrategyNotFoundError,
    PortfolioOptimizationError,
    PortfolioStrategyLoadError,
    PortfolioSaveError,
    PortfolioMasterError,
    OptimizerError,
    OptimizerRunError,
    RetesterError,
    RetesterRunError,
    RetesterDatabankError,
    DatabankPathError,
    SQXError,
    SQXBindingError,
    UnsupportedSQXVersionError,
    SQXDaemonStartError,
    SQXSessionLockError,
)


class TestPhase4ErrorHierarchy:
    """Test that all Phase 4 exceptions inherit from Phase4Error."""

    def test_all_exceptions_inherit_from_phase4error(self):
        """All Phase 4 exceptions should inherit from Phase4Error."""
        exceptions = [
            JForexError,
            JForexConnectionError,
            JForexStrategyNotFoundError,
            JForexServerError,
            PortfolioError,
            StrategyNotFoundError,
            PortfolioOptimizationError,
            PortfolioStrategyLoadError,
            PortfolioSaveError,
            PortfolioMasterError,
            OptimizerError,
            OptimizerRunError,
            RetesterError,
            RetesterRunError,
            RetesterDatabankError,
            DatabankPathError,
            SQXError,
            SQXBindingError,
            UnsupportedSQXVersionError,
            SQXDaemonStartError,
            SQXSessionLockError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, Phase4Error), f"{exc_class.__name__} should inherit from Phase4Error"


class TestJForexErrors:
    """Tests for JForex deployment errors."""

    def test_jforex_connection_error_stores_host_port(self):
        err = JForexConnectionError("127.0.0.1", 8888, "connection refused")
        assert err.host == "127.0.0.1"
        assert err.port == 8888
        assert "127.0.0.1:8888" in str(err)

    def test_jforex_strategy_not_found_stores_id(self):
        err = JForexStrategyNotFoundError("strat-123", "not in SQX")
        assert err.strategy_id == "strat-123"
        assert "strat-123" in str(err)

    def test_jforex_server_error_stores_status_code(self):
        err = JForexServerError(500, "Internal Server Error")
        assert err.status_code == 500
        assert err.response_body == "Internal Server Error"
        assert "500" in str(err)


class TestPortfolioErrors:
    """Tests for Portfolio Composer/Master errors."""

    def test_strategy_not_found_stores_id(self):
        err = StrategyNotFoundError("strat-456", "missing from session")
        assert err.strategy_id == "strat-456"
        assert "strat-456" in str(err)

    def test_portfolio_optimization_error(self):
        err = PortfolioOptimizationError("GA failed to converge")
        assert "GA failed to converge" in str(err)

    def test_portfolio_strategy_load_error(self):
        err = PortfolioStrategyLoadError("HTTP 500 on /load")
        assert "Portfolio strategy load failed" in str(err)

    def test_portfolio_save_error(self):
        err = PortfolioSaveError("Disk full")
        assert "Portfolio save failed" in str(err)

    def test_portfolio_master_error(self):
        err = PortfolioMasterError("Genetic builder crashed")
        assert "Portfolio Master build failed" in str(err)


class TestOptimizerErrors:
    """Tests for Optimizer errors."""

    def test_optimizer_run_error(self):
        err = OptimizerRunError("sqcli returned exit code 1")
        assert "Optimizer run failed" in str(err)


class TestRetesterErrors:
    """Tests for Retester errors."""

    def test_retester_run_error(self):
        err = RetesterRunError("MC simulation timed out")
        assert "Retester run failed" in str(err)

    def test_retester_databank_error(self):
        err = RetesterDatabankError("Invalid databank name: EURUSD_H1")
        assert "Retester databank configuration error" in str(err)

    def test_databank_path_error_stores_name(self):
        err = DatabankPathError("EURUSD_H1", "Path traversal attempt")
        assert err.databank == "EURUSD_H1"
        assert "EURUSD_H1" in str(err)


class TestSQXErrors:
    """Tests for SQX daemon/session errors."""

    def test_sqx_binding_error_enforces_localhost(self):
        err = SQXBindingError("0.0.0.0", "Security violation")
        assert err.bind_address == "0.0.0.0"
        assert "127.0.0.1" in str(err)

    def test_unsupported_sqx_version_error(self):
        err = UnsupportedSQXVersionError("100.0", ["144.2953", "141.2219"])
        assert err.version == "100.0"
        assert err.supported == ["144.2953", "141.2219"]
        assert "100.0" in str(err)
        assert "144.2953" in str(err)

    def test_sqx_daemon_start_error(self):
        err = SQXDaemonStartError("sqcli not found")
        assert "SQX daemon failed to start" in str(err)

    def test_sqx_session_lock_error(self):
        err = SQXSessionLockError("Another process holds the lock")
        assert "Could not acquire SQX session lock" in str(err)


class TestPhase4ErrorBase:
    """Tests for base Phase4Error behavior."""

    def test_phase4_error_with_detail(self):
        err = Phase4Error("Base error", "Additional detail")
        assert "Base error" in str(err)
        assert "Additional detail" in str(err)

    def test_phase4_error_without_detail(self):
        err = Phase4Error("Simple error")
        assert str(err) == "Simple error"

    def test_phase4_error_attributes(self):
        err = Phase4Error("Test message", "Test detail")
        assert err.message == "Test message"
        assert err.detail == "Test detail"