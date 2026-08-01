"""Tests for SelectionEngine — verdicts, ordering, and empty-selection warning."""

from __future__ import annotations

import pytest

from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.models import StrategyAnalysis, SelectionResult
from quantlab.analysis.selection import SelectionEngine
from quantlab.readers.models import StrategySummary


class TestSelectionEngine:
    """Tests for strategy selection."""

    def setup_method(self) -> None:
        self.engine = AnalysisEngine()
        self.selector = SelectionEngine()

    def _build_analysis(self, name: str, **overrides) -> StrategyAnalysis:
        """Helper to build a StrategyAnalysis with default healthy values."""
        defaults = {
            "profit_factor": 2.0,
            "sharpe_ratio": 1.5,
            "win_rate": 0.6,
            "max_drawdown": 10.0,
            "total_trades": 200,
            "mc_p10": 1.0,
            "wf_is_sharpe": 1.2,
            "wf_oos_sharpe": 1.0,
        }
        defaults.update(overrides)

        strategy = StrategySummary(strategy_name=name, **defaults)
        return self.engine.analyze(strategy)

    def test_accept_when_no_flags(self) -> None:
        """GIVEN a strategy with no overfit flags
        WHEN selection runs
        THEN the verdict is ACCEPT.
        """
        analysis = self._build_analysis("Good")
        result = self.selector.select([analysis])

        assert result.verdicts["Good"] == "ACCEPT"
        assert "Good" in result.selected

    def test_reject_when_flagged(self) -> None:
        """GIVEN a strategy with overfit flags
        WHEN selection runs
        THEN the verdict is REJECT.
        """
        strategy = StrategySummary(
            strategy_name="Bad",
            profit_factor=5.0,
            total_trades=5,
        )
        analysis = self.engine.analyze(strategy)
        result = self.selector.select([analysis])

        assert result.verdicts["Bad"] == "REJECT"
        assert "Bad" not in result.selected

    def test_eight_of_thirty_accepted(self) -> None:
        """GIVEN 30 strategies where 8 pass all heuristics
        WHEN selection runs
        THEN selected contains exactly 8 entries and verdicts mark 8 ACCEPT / 22 REJECT.
        """
        analyses: list[StrategyAnalysis] = []
        for i in range(8):
            # Healthy strategies: high PF/Sharpe but adequate trades
            s = StrategySummary(
                strategy_name=f"Good_{i}",
                profit_factor=2.0 + i * 0.1,
                sharpe_ratio=1.5 + i * 0.05,
                win_rate=0.6,
                max_drawdown=8.0,
                total_trades=500,
                mc_p10=1.0,
                wf_is_sharpe=1.2,
                wf_oos_sharpe=1.1,
            )
            analyses.append(self.engine.analyze(s))

        for i in range(22):
            # Unhealthy strategies: various flags
            flag_type = i % 4
            if flag_type == 0:
                # Extreme PF + low trades
                s = StrategySummary(
                    strategy_name=f"Bad_PF_{i}",
                    profit_factor=5.0,
                    total_trades=5,
                )
            elif flag_type == 1:
                # MC p10 breach
                s = StrategySummary(
                    strategy_name=f"Bad_MC_{i}",
                    profit_factor=1.5,
                    total_trades=300,
                    mc_p10=-1.2,
                )
            elif flag_type == 2:
                # WF degradation
                s = StrategySummary(
                    strategy_name=f"Bad_WF_{i}",
                    profit_factor=1.5,
                    total_trades=300,
                    wf_is_sharpe=1.0,
                    wf_oos_sharpe=0.4,
                )
            else:
                # Extreme Sharpe + low trades
                s = StrategySummary(
                    strategy_name=f"Bad_SR_{i}",
                    profit_factor=1.5,
                    sharpe_ratio=3.5,
                    total_trades=10,
                )
            analyses.append(self.engine.analyze(s))

        result = self.selector.select(analyses)

        assert len(result.selected) == 8
        accepts = [v for v in result.verdicts.values() if v == "ACCEPT"]
        rejects = [v for v in result.verdicts.values() if v == "REJECT"]
        assert len(accepts) == 8
        assert len(rejects) == 22

    def test_selected_ordered_by_score_desc(self) -> None:
        """GIVEN three ACCEPT strategies with different scores
        WHEN selection runs
        THEN selected is ordered by score descending.
        """
        analyses = [
            self._build_analysis("Low", profit_factor=1.0, sharpe_ratio=0.5, win_rate=0.4, max_drawdown=30.0, total_trades=100),
            self._build_analysis("High", profit_factor=3.0, sharpe_ratio=2.5, win_rate=0.75, max_drawdown=3.0, total_trades=600),
            self._build_analysis("Mid", profit_factor=2.0, sharpe_ratio=1.5, win_rate=0.55, max_drawdown=12.0, total_trades=300),
        ]
        result = self.selector.select(analyses)

        assert result.selected == ["High", "Mid", "Low"]

    def test_empty_selection_produces_warning(self) -> None:
        """GIVEN no strategy passes thresholds
        WHEN selection runs
        THEN selected is empty and a warning is emitted.
        """
        # All strategies are flagged
        analyses = [
            self._build_analysis("Bad1", profit_factor=5.0, total_trades=5),
            self._build_analysis("Bad2", mc_p10=-1.0),
        ]
        result = self.selector.select(analyses)

        assert result.selected == []
        assert any("No strategies passed selection" in w for w in result.warnings)

    def test_rejected_strategies_excluded_from_selected(self) -> None:
        """GIVEN a mix of ACCEPT and REJECT strategies
        WHEN selection runs
        THEN only ACCEPT names appear in selected.
        """
        analyses = [
            self._build_analysis("Accept1"),
            self._build_analysis("Reject1", profit_factor=5.0, total_trades=5),
            self._build_analysis("Accept2", profit_factor=2.5),
        ]
        result = self.selector.select(analyses)

        assert "Accept1" in result.selected
        assert "Accept2" in result.selected
        assert "Reject1" not in result.selected

    def test_result_contains_all_analyses(self) -> None:
        """GIVEN a list of analyses
        WHEN selection runs
        THEN the SelectionResult includes all input analyses.
        """
        analyses = [
            self._build_analysis("A"),
            self._build_analysis("B"),
        ]
        result = self.selector.select(analyses)

        assert len(result.analyses) == 2
        assert {a.name for a in result.analyses} == {"A", "B"}
