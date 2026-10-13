"""QuantLab analysis — per-strategy metrics, overfit heuristics, and selection.
Also provides advanced analytics: regime-aware metrics, Pareto frontier,
sensitivity analysis, and robustness checks."""

from quantlab.analysis.advanced import (
    AdvancedAnalysisEngine,
    AdvancedAnalysisResult,
    ParetoResult,
    RegimeMetrics,
    RobustnessResult,
    SensitivityResult,
    create_advanced_analysis_engine,
)
from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.models import SelectionResult, StrategyAnalysis
from quantlab.analysis.reader import AnalysisReader
from quantlab.analysis.selection import SelectionEngine

__all__ = [
    "AdvancedAnalysisEngine",
    "AdvancedAnalysisResult",
    "AnalysisEngine",
    "AnalysisReader",
    "AnalysisThresholds",
    "ParetoResult",
    "RegimeMetrics",
    "RobustnessResult",
    "SelectionEngine",
    "SelectionResult",
    "SensitivityResult",
    "StrategyAnalysis",
    "create_advanced_analysis_engine",
]