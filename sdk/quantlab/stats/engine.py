"""Statistics engine — pure Python trading metric computations.

Computes standard trading performance metrics from backtest results
without any SQX dependency. Operates on ``Trade[]`` and
``EquityPoint[]`` from the ``readers`` module.

Metrics
-------
- **Profit Factor**: gross_profit / abs(gross_loss)
- **Sharpe Ratio**: annualised risk-adjusted return
- **Sortino Ratio**: downside deviation only
- **Max Drawdown**: largest peak-to-trough decline (%)
- **MAR Ratio**: CAGR / max_drawdown
- **Recovery Factor**: net_profit / max_drawdown
- **Expectancy**: avg(win) * win_rate - avg(loss) * loss_rate
"""

from __future__ import annotations

import math
from typing import Optional

from quantlab.readers.models import EquityPoint, Trade
from quantlab.stats.models import StatsResult
from quantlab.tools.exceptions import InsufficientDataError


class StatisticsEngine:
    """Computes trading performance metrics from backtest results.

    All methods are pure computations — no side effects, no IO.
    Operates on the Pydantic models from ``quantlab.readers``.

    Usage::

        engine = StatisticsEngine()
        result = engine.compute_all(trades, equity, cagr=0.15)
        print(f"PF: {result.profit_factor}, Sharpe: {result.sharpe_ratio}")
    """

    # ── Profit Factor ──────────────────────────────────────────────────────────

    @staticmethod
    def profit_factor(trades: list[Trade]) -> float:
        """Compute Profit Factor = gross_profit / abs(gross_loss).

        When gross_loss is zero, returns infinity (all trades profitable).

        Args:
            trades: List of trades.

        Returns:
            Profit factor as a float, or ``math.inf`` when gross loss is zero.

        Raises:
            InsufficientDataError: If the trade list is empty.
        """
        if not trades:
            raise InsufficientDataError("Empty trade list — cannot compute profit factor.")

        gross_profit = sum(t.profit for t in trades if t.profit > 0)
        gross_loss = sum(t.profit for t in trades if t.profit < 0)

        if gross_loss == 0:
            return math.inf

        return gross_profit / abs(gross_loss)

    # ── Sharpe Ratio ───────────────────────────────────────────────────────────

    @staticmethod
    def sharpe_ratio(returns: list[float], annual_factor: int = 252, risk_free_rate: float = 0.0) -> float:
        """Compute the annualised Sharpe ratio.

        ``sharpe = (mean(returns) - risk_free_rate) / std(returns) * sqrt(annual_factor)``

        Args:
            returns: List of per-period returns.
            annual_factor: Number of periods per year (252 for daily, 52 for weekly, 12 for monthly).
            risk_free_rate: Risk-free rate per period (default 0).

        Returns:
            Annualised Sharpe ratio.

        Raises:
            InsufficientDataError: If the returns list is empty or has
                fewer than 2 elements (std requires at least 2).
        """
        if len(returns) < 2:
            raise InsufficientDataError(
                f"At least 2 returns are required to compute Sharpe ratio (got {len(returns)})."
            )

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return math.inf if (mean_return - risk_free_rate) > 0 else 0.0

        excess = mean_return - risk_free_rate
        return (excess / std_dev) * math.sqrt(annual_factor)

    # ── Sortino Ratio ──────────────────────────────────────────────────────────

    @staticmethod
    def sortino_ratio(returns: list[float], annual_factor: int = 252, risk_free_rate: float = 0.0) -> float:
        """Compute the annualised Sortino ratio (downside deviation only).

        ``sortino = (mean(returns) - risk_free_rate) / downside_std * sqrt(annual_factor)``

        Downside deviation considers only negative return deviations from
        the risk-free rate.

        Args:
            returns: List of per-period returns.
            annual_factor: Number of periods per year (default 252).
            risk_free_rate: Risk-free rate per period (default 0).

        Returns:
            Annualised Sortino ratio.

        Raises:
            InsufficientDataError: If the returns list is empty.
        """
        if not returns:
            raise InsufficientDataError("Empty returns list — cannot compute Sortino ratio.")

        mean_return = sum(returns) / len(returns)
        downside_deviations = [
            (r - risk_free_rate) ** 2
            for r in returns
            if r < risk_free_rate
        ]

        if not downside_deviations:
            # No downside periods — ratio is effectively infinite
            return math.inf

        downside_std = math.sqrt(sum(downside_deviations) / len(downside_deviations))

        if downside_std == 0:
            return math.inf

        excess = mean_return - risk_free_rate
        return (excess / downside_std) * math.sqrt(annual_factor)

    # ── Maximum Drawdown ───────────────────────────────────────────────────────

    @staticmethod
    def max_drawdown(equity: list[EquityPoint]) -> float:
        """Compute maximum drawdown as a positive percentage.

        MDD is the largest peak-to-trough decline in the equity curve,
        expressed as a percentage (e.g., 25.0 for a 25% decline).

        Args:
            equity: List of ordered EquityPoint models.

        Returns:
            Maximum drawdown as a percentage (0.0 for monotonically
            increasing equity).

        Raises:
            InsufficientDataError: If the equity list is empty.
        """
        if not equity:
            raise InsufficientDataError("Empty equity curve — cannot compute max drawdown.")

        peak = equity[0].equity
        max_dd = 0.0

        for point in equity:
            if point.equity > peak:
                peak = point.equity
            dd = (peak - point.equity) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    # ── MAR Ratio ──────────────────────────────────────────────────────────────

    @staticmethod
    def mar_ratio(cagr: float, max_dd: float) -> float:
        """Compute MAR Ratio = CAGR / max_drawdown.

        Args:
            cagr: Compound annual growth rate as a percentage (e.g., 15.0 for 15%).
            max_dd: Maximum drawdown as a percentage (e.g., 10.0 for 10%).

        Returns:
            MAR ratio, or ``math.inf`` if max_drawdown is zero.
        """
        if max_dd == 0:
            return math.inf
        return cagr / max_dd

    # ── Recovery Factor ────────────────────────────────────────────────────────

    @staticmethod
    def recovery_factor(net_profit: float, max_dd: float) -> float:
        """Compute Recovery Factor = net_profit / max_drawdown.

        Args:
            net_profit: Total net profit in account currency.
            max_dd: Maximum drawdown as a positive number (e.g., 1000.0).

        Returns:
            Recovery factor, or ``math.inf`` if max_drawdown is zero.
        """
        if max_dd == 0:
            return math.inf
        return net_profit / max_dd

    # ── Expectancy ─────────────────────────────────────────────────────────────

    @staticmethod
    def expectancy(trades: list[Trade]) -> tuple[float, float]:
        """Compute Expectancy and Expectancy Ratio.

        Expectancy = avg(win_amount) * win_rate - avg(loss_amount) * loss_rate
        Expectancy Ratio = expectancy / avg(loss_amount)

        Args:
            trades: List of trades.

        Returns:
            Tuple of (expectancy, expectancy_ratio).

        Raises:
            InsufficientDataError: If the trade list is empty.
        """
        if not trades:
            raise InsufficientDataError("Empty trade list — cannot compute expectancy.")

        winning_trades = [t.profit for t in trades if t.profit > 0]
        losing_trades = [t.profit for t in trades if t.profit < 0]

        total = len(trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        win_rate = win_count / total
        loss_rate = loss_count / total

        avg_win = sum(winning_trades) / win_count if win_count > 0 else 0.0
        avg_loss = abs(sum(losing_trades) / loss_count) if loss_count > 0 else 0.0

        exp = avg_win * win_rate - avg_loss * loss_rate
        exp_ratio = exp / avg_loss if avg_loss > 0 else math.inf

        return exp, exp_ratio

    # ── Compute All ────────────────────────────────────────────────────────────

    def compute_all(
        self,
        trades: Optional[list[Trade]] = None,
        equity: Optional[list[EquityPoint]] = None,
        returns: Optional[list[float]] = None,
        cagr: Optional[float] = None,
        net_profit: Optional[float] = None,
        annual_factor: int = 252,
        risk_free_rate: float = 0.0,
    ) -> StatsResult:
        """Compute all available metrics from the provided data.

        Only computes metrics whose input data is provided. Missing
        inputs result in ``None`` for that metric.

        Args:
            trades: List of trades (required for PF and expectancy).
            equity: List of equity points (required for MDD).
            returns: List of per-period returns (required for Sharpe/Sortino).
            cagr: CAGR percentage (required for MAR).
            net_profit: Net profit (required for recovery factor).
            annual_factor: Periods per year for Sharpe/Sortino.
            risk_free_rate: Risk-free rate per period.

        Returns:
            A ``StatsResult`` with computed metrics.
        """
        result = StatsResult()

        if trades is not None:
            try:
                result.profit_factor = self.profit_factor(trades)
            except InsufficientDataError:
                pass

            try:
                exp, exp_ratio = self.expectancy(trades)
                result.expectancy = exp
                result.expectancy_ratio = exp_ratio
            except InsufficientDataError:
                pass

        if equity is not None:
            try:
                result.max_drawdown = self.max_drawdown(equity)
                mdd = result.max_drawdown
                if cagr is not None:
                    result.mar_ratio = self.mar_ratio(cagr, mdd)
                if net_profit is not None:
                    result.recovery_factor = self.recovery_factor(net_profit, mdd)
            except InsufficientDataError:
                pass

        if returns is not None:
            try:
                result.sharpe_ratio = self.sharpe_ratio(returns, annual_factor, risk_free_rate)
                result.sortino_ratio = self.sortino_ratio(returns, annual_factor, risk_free_rate)
            except InsufficientDataError:
                pass

        return result
