"""Tests for the Statistics Engine — pure Python metric computations."""

import math

import pytest

from quantlab.readers.models import EquityPoint, Trade
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import StatsResult
from quantlab.tools.exceptions import InsufficientDataError

engine = StatisticsEngine()


# ── Sample data ───────────────────────────────────────────────────────────────

SAMPLE_TRADES = [
    Trade(entry_time="2024-01-01 08:00", exit_time="2024-01-01 16:00", direction="LONG", lots=0.1, profit=250.0, drawdown=50.0),
    Trade(entry_time="2024-01-02 08:00", exit_time="2024-01-02 16:00", direction="SHORT", lots=0.2, profit=-150.0, drawdown=30.0),
    Trade(entry_time="2024-01-03 08:00", exit_time="2024-01-03 16:00", direction="LONG", lots=0.1, profit=100.0, drawdown=20.0),
    Trade(entry_time="2024-01-04 08:00", exit_time="2024-01-04 16:00", direction="SHORT", lots=0.15, profit=180.0, drawdown=40.0),
    Trade(entry_time="2024-01-05 08:00", exit_time="2024-01-05 16:00", direction="LONG", lots=0.2, profit=-80.0, drawdown=10.0),
    Trade(entry_time="2024-01-06 08:00", exit_time="2024-01-06 16:00", direction="LONG", lots=0.1, profit=320.0, drawdown=60.0),
    Trade(entry_time="2024-01-07 08:00", exit_time="2024-01-07 16:00", direction="SHORT", lots=0.2, profit=200.0, drawdown=25.0),
    Trade(entry_time="2024-01-08 08:00", exit_time="2024-01-08 16:00", direction="LONG", lots=0.15, profit=-200.0, drawdown=45.0),
    Trade(entry_time="2024-01-09 08:00", exit_time="2024-01-09 16:00", direction="SHORT", lots=0.1, profit=150.0, drawdown=15.0),
    Trade(entry_time="2024-01-10 08:00", exit_time="2024-01-10 16:00", direction="LONG", lots=0.2, profit=90.0, drawdown=5.0),
]

ALL_PROFITABLE_TRADES = [
    Trade(entry_time="2024-01-01 08:00", exit_time="2024-01-01 16:00", direction="LONG", lots=0.1, profit=100.0),
    Trade(entry_time="2024-01-02 08:00", exit_time="2024-01-02 16:00", direction="LONG", lots=0.1, profit=200.0),
]

SAMPLE_EQUITY = [
    EquityPoint(timestamp="2024-01-01", equity=100000.0),
    EquityPoint(timestamp="2024-01-02", equity=100250.0),
    EquityPoint(timestamp="2024-01-03", equity=100100.0),
    EquityPoint(timestamp="2024-01-04", equity=100200.0),
    EquityPoint(timestamp="2024-01-05", equity=100380.0),
    EquityPoint(timestamp="2024-01-06", equity=100300.0),
    EquityPoint(timestamp="2024-01-07", equity=100620.0),
    EquityPoint(timestamp="2024-01-08", equity=100820.0),
    EquityPoint(timestamp="2024-01-09", equity=100420.0),
    EquityPoint(timestamp="2024-01-10", equity=100620.0),
    EquityPoint(timestamp="2024-01-11", equity=100710.0),
    EquityPoint(timestamp="2024-01-12", equity=100570.0),
]

MONOTONIC_EQUITY = [
    EquityPoint(timestamp="2024-01-01", equity=100000.0),
    EquityPoint(timestamp="2024-01-02", equity=101000.0),
    EquityPoint(timestamp="2024-01-03", equity=102000.0),
    EquityPoint(timestamp="2024-01-04", equity=103000.0),
]

SAMPLE_RETURNS = [0.01, -0.005, 0.02, 0.015, -0.01, 0.03, 0.005, -0.008, 0.012, 0.018]


class TestProfitFactor:
    """Tests for ``StatisticsEngine.profit_factor()``."""

    def test_normal_profit_factor(self) -> None:
        """GIVEN a trade list with gross profit 1500 and gross loss 500
        WHEN the engine computes Profit Factor
        THEN the result is 3.0.

        Gross profit: 250+100+180+320+200+150+90 = 1290.0 (we only count positive)
        Gross loss: -150 + -80 + -200 = -430.0
        PF = 1290 / 430 = 3.0
        """
        pf = engine.profit_factor(SAMPLE_TRADES)
        # Profitable trades: 250 + 100 + 180 + 320 + 200 + 150 + 90 = 1290
        # Losing trades: -150 + -80 + -200 = -430
        # 1290 / 430 = 3.0
        assert pf == pytest.approx(3.0, rel=0.01)

    def test_zero_gross_loss_returns_infinity(self) -> None:
        """GIVEN a trade list with all profitable trades (gross loss = 0)
        WHEN the engine computes Profit Factor
        THEN the result is inf (positive infinity).
        """
        pf = engine.profit_factor(ALL_PROFITABLE_TRADES)
        assert pf == math.inf

    def test_empty_trades_raises_insufficient_data(self) -> None:
        """GIVEN an empty trade list
        WHEN the engine attempts to compute Profit Factor
        THEN an InsufficientDataError is raised.
        """
        with pytest.raises(InsufficientDataError):
            engine.profit_factor([])


class TestSharpeRatio:
    """Tests for ``StatisticsEngine.sharpe_ratio()``."""

    def test_sharpe_from_daily_returns(self) -> None:
        """GIVEN a trade list with 252 daily returns
        WHEN the engine computes Sharpe Ratio
        THEN the result equals mean(returns) / std(returns) * sqrt(252).
        """
        sr = engine.sharpe_ratio(SAMPLE_RETURNS, annual_factor=252)

        # Manual calculation
        mean_r = sum(SAMPLE_RETURNS) / len(SAMPLE_RETURNS)
        variance = sum((r - mean_r) ** 2 for r in SAMPLE_RETURNS) / (len(SAMPLE_RETURNS) - 1)
        std_dev = math.sqrt(variance)
        expected = (mean_r / std_dev) * math.sqrt(252)

        assert sr == pytest.approx(expected, rel=0.01)

    def test_zero_std_dev_returns_inf_or_zero(self) -> None:
        """Constant returns produce inf (if positive) or 0."""
        const_returns = [0.01, 0.01, 0.01]
        sr = engine.sharpe_ratio(const_returns)
        assert sr == math.inf

    def test_empty_returns_raises_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError):
            engine.sharpe_ratio([])

    def test_single_return_raises_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError):
            engine.sharpe_ratio([0.01])

    def test_sharpe_with_risk_free_rate(self) -> None:
        """Risk-free rate reduces the numerator."""
        sr_with_rfr = engine.sharpe_ratio(SAMPLE_RETURNS, risk_free_rate=0.001)
        sr_without = engine.sharpe_ratio(SAMPLE_RETURNS, risk_free_rate=0.0)
        assert sr_with_rfr < sr_without


class TestSortinoRatio:
    """Tests for ``StatisticsEngine.sortino_ratio()``."""

    def test_sortino_uses_downside_deviation(self) -> None:
        """GIVEN a trade list with positive returns and some negative returns
        WHEN the engine computes Sortino Ratio
        THEN the denominator uses only negative return deviations.
        """
        sortino = engine.sortino_ratio(SAMPLE_RETURNS)
        sharpe = engine.sharpe_ratio(SAMPLE_RETURNS)

        # Sortino should be >= Sharpe because downside deviation <= std deviation
        assert sortino >= sharpe

    def test_no_downside_returns_infinity(self) -> None:
        """All positive returns = no downside = inf."""
        sr = engine.sortino_ratio([0.01, 0.02, 0.015])
        assert sr == math.inf

    def test_empty_returns_raises_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError):
            engine.sortino_ratio([])


class TestMaxDrawdown:
    """Tests for ``StatisticsEngine.max_drawdown()``."""

    def test_drawdown_from_equity_curve(self) -> None:
        """GIVEN an equity curve peaking at 100820 and troughing at 100420
        WHEN the engine computes max drawdown
        THEN the result is the correct percentage.

        Peak = 100820, trough = 100420
        DD = (100820 - 100420) / 100820 * 100 = 400/100820 * 100 = 0.3967%
        """
        mdd = engine.max_drawdown(SAMPLE_EQUITY)
        # Peak at equity[7] = 100820, trough at equity[8] = 100420
        expected = (100820.0 - 100420.0) / 100820.0 * 100
        assert mdd == pytest.approx(expected, rel=0.01)

    def test_monotonically_increasing_has_zero_drawdown(self) -> None:
        """GIVEN an equity curve with strictly increasing values
        WHEN the engine computes max drawdown
        THEN the result is 0.0%.
        """
        mdd = engine.max_drawdown(MONOTONIC_EQUITY)
        assert mdd == 0.0

    def test_empty_equity_raises_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError):
            engine.max_drawdown([])


class TestMARRatio:
    """Tests for ``StatisticsEngine.mar_ratio()``."""

    def test_mar_from_cagr_and_drawdown(self) -> None:
        """GIVEN CAGR of 15% and max drawdown of 10%
        WHEN the engine computes MAR Ratio
        THEN the result is 1.5.
        """
        mar = engine.mar_ratio(cagr=15.0, max_dd=10.0)
        assert mar == 1.5

    def test_zero_drawdown_returns_infinity(self) -> None:
        """GIVEN a scenario with zero max drawdown
        WHEN the engine computes MAR Ratio
        THEN the result is inf.
        """
        mar = engine.mar_ratio(cagr=15.0, max_dd=0.0)
        assert mar == math.inf


class TestRecoveryFactor:
    """Tests for ``StatisticsEngine.recovery_factor()``."""

    def test_recovery_factor_normal(self) -> None:
        rf = engine.recovery_factor(net_profit=5000.0, max_dd=1000.0)
        assert rf == 5.0

    def test_zero_drawdown_returns_infinity(self) -> None:
        rf = engine.recovery_factor(net_profit=5000.0, max_dd=0.0)
        assert rf == math.inf


class TestExpectancy:
    """Tests for ``StatisticsEngine.expectancy()``."""

    def test_expectancy_from_win_loss_distribution(self) -> None:
        """GIVEN 10 trades where gross_profit=1290, gross_loss=430
        WHEN the engine computes Expectancy
        THEN the result matches the formula.

        7 winning trades: 250, 100, 180, 320, 200, 150, 90
        3 losing trades: -150, -80, -200

        Win rate: 7/10 = 0.7
        Loss rate: 3/10 = 0.3
        Avg win: (250 + 100 + 180 + 320 + 200 + 150 + 90) / 7 = 1290/7 ≈ 184.29
        Avg loss: (150 + 80 + 200) / 3 = 430/3 ≈ 143.33
        Expectancy: 184.29 * 0.7 - 143.33 * 0.3 ≈ 86.0
        """
        exp, exp_ratio = engine.expectancy(SAMPLE_TRADES)
        assert exp == pytest.approx(85.99, rel=0.01)

    def test_all_profitable_trades(self) -> None:
        """All profitable: no losing trades, loss avg = 0, exp ratio = inf."""
        exp, exp_ratio = engine.expectancy(ALL_PROFITABLE_TRADES)
        assert exp > 0
        assert exp_ratio == math.inf

    def test_empty_trades_raises_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError):
            engine.expectancy([])


class TestComputeAll:
    """Tests for ``StatisticsEngine.compute_all()``."""

    def test_all_metrics_with_full_data(self) -> None:
        """All available metrics are computed when all inputs are provided."""
        result = engine.compute_all(
            trades=SAMPLE_TRADES,
            equity=SAMPLE_EQUITY,
            returns=SAMPLE_RETURNS,
            cagr=15.0,
            net_profit=1060.0,
        )

        assert isinstance(result, StatsResult)
        assert result.profit_factor is not None
        assert result.sharpe_ratio is not None
        assert result.sortino_ratio is not None
        assert result.max_drawdown is not None
        assert result.mar_ratio is not None
        assert result.recovery_factor is not None
        assert result.expectancy is not None
        assert result.expectancy_ratio is not None

    def test_partial_data_returns_partial_results(self) -> None:
        """Only metrics with available inputs are computed."""
        result = engine.compute_all(trades=SAMPLE_TRADES)
        assert result.profit_factor is not None
        assert result.expectancy is not None
        assert result.sharpe_ratio is None  # no returns provided
        assert result.max_drawdown is None  # no equity provided

    def test_no_data_returns_empty_result(self) -> None:
        result = engine.compute_all()
        assert result.profit_factor is None
        assert result.sharpe_ratio is None
        assert result.sortino_ratio is None
        assert result.max_drawdown is None
        assert result.mar_ratio is None
        assert result.recovery_factor is None
        assert result.expectancy is None
        assert result.expectancy_ratio is None
