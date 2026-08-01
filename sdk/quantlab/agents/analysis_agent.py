"""AnalysisAgent — parses strategies.csv, computes per-strategy metrics, applies overfit heuristics, and selects strategies.

Consumes ``export_paths`` and ``statistics`` from context artifacts, resolves
``strategies.csv`` from export paths, parses it via ``AnalysisReader``, computes
metrics and heuristics via ``AnalysisEngine``, selects strategies via
``SelectionEngine``, and writes ``strategy_analysis``, ``selected_strategies``,
``strategy_verdicts``, and ``wf_cycles`` to context artifacts.

Implements the ``AnalysisStage.execute()`` contract for pipeline integration.
Mirrors ``StatisticsAgent`` patterns.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.models import SelectionResult, StrategyAnalysis
from quantlab.analysis.reader import AnalysisReader
from quantlab.analysis.selection import SelectionEngine
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import AnalysisStage
from quantlab.tools.exceptions import ParseError

logger = logging.getLogger(__name__)


class AnalysisAgent(AnalysisStage):
    """Parses strategies.csv, computes per-strategy metrics and heuristics, and selects strategies.

    Args:
        min_trades: Minimum trades to avoid extreme-metric flag.
        extreme_pf: Profit factor above this is extreme with low trades.
        extreme_sharpe: Sharpe above this is extreme with low trades.
        oos_is_threshold: Minimum OOS/IS Sharpe ratio.
        score_weights: Per-metric weights for composite score (must sum to 1.0).
    """

    def __init__(
        self,
        min_trades: int = 50,
        extreme_pf: float = 3.0,
        extreme_sharpe: float = 2.0,
        oos_is_threshold: float = 0.7,
        score_weights: Optional[dict[str, float]] = None,
    ) -> None:
        self._min_trades = min_trades
        self._extreme_pf = extreme_pf
        self._extreme_sharpe = extreme_sharpe
        self._oos_is_threshold = oos_is_threshold
        self._score_weights = score_weights or {
            "pf_weight": 0.25,
            "sharpe_weight": 0.20,
            "win_rate_weight": 0.15,
            "mdd_weight": 0.15,
            "mar_weight": 0.10,
            "recovery_weight": 0.10,
            "expectancy_weight": 0.05,
        }
        self._reader = AnalysisReader()
        self._engine = AnalysisEngine()
        self._selector = SelectionEngine()

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _resolve_export_path(self, export_paths: list[str], filename: str) -> Optional[str]:
        """Find a file by name in the export paths list."""
        for path in export_paths:
            if path.endswith(filename):
                return path
        return None

    def _build_thresholds(self, research_config: Optional[dict[str, Any]]) -> AnalysisThresholds:
        """Build AnalysisThresholds from research_config.analysis or defaults."""
        if not research_config:
            return AnalysisThresholds(
                min_trades=self._min_trades,
                extreme_pf=self._extreme_pf,
                extreme_sharpe=self._extreme_sharpe,
                oos_is_threshold=self._oos_is_threshold,
            )

        analysis = research_config.get("analysis") or {}
        return AnalysisThresholds(
            min_trades=analysis.get("min_trades", self._min_trades),
            extreme_pf=analysis.get("extreme_pf", self._extreme_pf),
            extreme_sharpe=analysis.get("extreme_sharpe", self._extreme_sharpe),
            oos_is_threshold=analysis.get("oos_is_threshold", self._oos_is_threshold),
        )

    # ── Pipeline Integration ─────────────────────────────────────────────────────

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute the analysis agent stage.

        Args:
            ctx: ``PipelineContext`` with ``export_paths`` and ``statistics`` in artifacts.

        Returns:
            Dict with ``strategy_analysis``, ``selected_strategies``,
            ``strategy_verdicts``, and ``wf_cycles``.
        """
        return await self.run(ctx)

    async def run(self, context: PipelineContext) -> dict[str, Any]:
        """Execute the analysis agent stage.

        Args:
            context: ``PipelineContext`` with ``export_paths`` and ``statistics`` in artifacts.

        Returns:
            Dict with all analysis artifacts.
        """
        export_paths = context.artifacts.get("export_paths", [])
        if not export_paths:
            logger.warning(
                "No export_paths found in context artifacts — returning empty analysis"
            )
            context.artifacts["strategy_analysis"] = []
            context.artifacts["selected_strategies"] = []
            context.artifacts["strategy_verdicts"] = {}
            context.artifacts["wf_cycles"] = []
            return {
                "strategy_analysis": [],
                "selected_strategies": [],
                "strategy_verdicts": {},
                "wf_cycles": [],
            }

        research_config = context.artifacts.get("research_config") or {}
        thresholds = self._build_thresholds(
            research_config if isinstance(research_config, dict) else {}
        )

        # Resolve strategies.csv
        strategies_path = self._resolve_export_path(export_paths, "strategies.csv")
        if not strategies_path:
            logger.warning("No strategies.csv found in export paths — analysis will be empty")
            context.artifacts["strategy_analysis"] = []
            context.artifacts["selected_strategies"] = []
            context.artifacts["strategy_verdicts"] = {}
            context.artifacts["wf_cycles"] = []
            return {
                "strategy_analysis": [],
                "selected_strategies": [],
                "strategy_verdicts": {},
                "wf_cycles": [],
            }

        # Parse strategies
        try:
            strategies = self._reader.parse(strategies_path)
            logger.info("Read %d strategies from %s", len(strategies), strategies_path)
        except ParseError as exc:
            logger.warning("Failed to parse strategies.csv: %s — analysis will be empty", exc)
            context.artifacts["strategy_analysis"] = []
            context.artifacts["selected_strategies"] = []
            context.artifacts["strategy_verdicts"] = {}
            context.artifacts["wf_cycles"] = []
            return {
                "strategy_analysis": [],
                "selected_strategies": [],
                "strategy_verdicts": {},
                "wf_cycles": [],
            }

        # Analyze and select
        analyses: list[StrategyAnalysis] = []
        for strategy in strategies:
            analysis = self._engine.analyze(strategy, thresholds)
            analyses.append(analysis)

        selection: SelectionResult = self._selector.select(analyses, thresholds)

        # Build wf_cycles from strategies
        wf_cycles: list[dict[str, Any]] = []
        for strategy in strategies:
            if strategy.wf_cycles is not None and strategy.wf_cycles > 0:
                wf_cycles.append({
                    "strategy_name": strategy.strategy_name,
                    "cycles": strategy.wf_cycles,
                    "wf_is_sharpe": strategy.wf_is_sharpe,
                    "wf_oos_sharpe": strategy.wf_oos_sharpe,
                })

        # Serialize analyses for context artifacts
        strategy_analysis_list = [
            {
                "name": a.name,
                "metrics": a.metrics.model_dump() if hasattr(a.metrics, "model_dump") else {},
                "flags": a.flags,
                "score": a.score,
            }
            for a in selection.analyses
        ]

        # Write to context artifacts
        context.artifacts["strategy_analysis"] = strategy_analysis_list
        context.artifacts["selected_strategies"] = selection.selected
        context.artifacts["strategy_verdicts"] = selection.verdicts
        context.artifacts["wf_cycles"] = wf_cycles

        logger.info(
            "AnalysisAgent: analyzed %d strategies, selected %d, %d warnings",
            len(analyses),
            len(selection.selected),
            len(selection.warnings),
        )

        return {
            "strategy_analysis": strategy_analysis_list,
            "selected_strategies": selection.selected,
            "strategy_verdicts": selection.verdicts,
            "wf_cycles": wf_cycles,
        }
