"""SelectionEngine — scoring, verdicts, and strategy selection."""

from __future__ import annotations

from typing import Optional

from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.models import SelectionResult, StrategyAnalysis


class SelectionEngine:
    """Score strategies and select the best performers.

    Verdicts:
        - ``ACCEPT``: strategy has no overfit flags.
        - ``REJECT``: strategy has one or more overfit flags.

    The accepted strategies are ordered by composite score descending.
    If no strategy is accepted, a warning is emitted.

    Usage::

        engine = SelectionEngine()
        result = engine.select(analyses, thresholds)
    """

    def select(
        self,
        analyses: list[StrategyAnalysis],
        thresholds: AnalysisThresholds | None = None,
    ) -> SelectionResult:
        """Select strategies from an analysed list.

        Args:
            analyses: Per-strategy analysis results.
            thresholds: Override thresholds. Defaults to ``AnalysisThresholds()``.

        Returns:
            A ``SelectionResult`` with verdicts, selected names, and warnings.
        """
        thresholds = thresholds or AnalysisThresholds()
        verdicts: dict[str, str] = {}
        selected: list[str] = []
        warnings: list[str] = []

        # Split accepted and rejected
        accepted: list[tuple[float, str]] = []
        for analysis in analyses:
            verdict = "ACCEPT" if not analysis.flags else "REJECT"
            verdicts[analysis.name] = verdict
            if verdict == "ACCEPT":
                accepted.append((analysis.score, analysis.name))

        # Sort accepted by score descending, then by name for determinism
        accepted.sort(key=lambda item: (-item[0], item[1]))
        selected = [name for _, name in accepted]

        if not selected:
            warnings.append("No strategies passed selection thresholds.")

        return SelectionResult(
            analyses=list(analyses),
            verdicts=verdicts,
            selected=selected,
            warnings=warnings,
        )
