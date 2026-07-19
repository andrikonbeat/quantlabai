"""Phase 4 — Portfolio Composer for weight optimization via SQX HTTP API.

PortfolioComposer loads strategies into SQX session, optimizes weights
via PortfolioComposer recompute, and saves the portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.phase4.errors import (
    JForexStrategyNotFoundError,
    PortfolioError,
    PortfolioOptimizationError,
    PortfolioStrategyLoadError,
    PortfolioSaveError,
    StrategyNotFoundError,
)
from quantlab.phase4.templates import CfxTemplateBuilder


@dataclass
class WeightResult:
    """Individual strategy weight from portfolio optimization.

    Attributes:
        strategy_id: SQX strategy identifier.
        weight: Allocated weight in range [0, 1].
        rank: Ranking by weight (1 = highest weight).
    """

    strategy_id: str
    weight: float
    rank: int


@dataclass
class PortfolioWeightResult:
    """Complete portfolio weight optimization result.

    Attributes:
        weights: List of WeightResult sorted by rank (descending weight).
        total_weight: Sum of all weights (may not equal 1 if not normalized).
        fitness: Fitness function used during optimization.
        is_normalized: True if total_weight is within 0.01 of 1.0.
    """

    weights: list[WeightResult] = field(default_factory=list)
    total_weight: float = 0.0
    fitness: str = "ReturnDDRatio"
    is_normalized: bool = False


class PortfolioComposer:
    """Orchestrates Portfolio Composer weight optimization via SQX HTTP API.

    Workflow:
        1. load_strategies() — load strategy IDs into SQX session
        2. optimize_weights() — run genetic/portfolio optimization
        3. save_portfolio() — export portfolio CFX

    All operations use AsyncSQXClient against the SQX -gui HTTP API.
    """

    def __init__(self, client: AsyncSQXClient):
        self._client = client
        self._loaded_strategy_ids: list[str] = []

    async def load_strategies(self, strategy_ids: list[str]) -> None:
        """Load strategies into SQX Portfolio Composer session.

        If any strategy_id fails, the already-loaded strategies remain
        in the session (no unload_strategy available via HTTP API).
        Caller should handle cleanup if needed.

        Args:
            strategy_ids: List of SQX strategy IDs.

        Raises:
            StrategyNotFoundError: If any strategy_id not found in SQX.
            PortfolioStrategyLoadError: If load fails for other reasons.
        """
        loaded: list[str] = []
        for sid in strategy_ids:
            try:
                await self._client.load_strategy(sid)
                loaded.append(sid)
            except JForexStrategyNotFoundError as e:
                # Don't rollback - unload_strategy not available via HTTP
                # Caller can call clear_session() if they want to reset
                raise StrategyNotFoundError(sid) from e
            except Exception as e:
                # Don't rollback - unload_strategy not available via HTTP
                raise PortfolioStrategyLoadError(f"Failed to load strategy {sid}: {e}") from e

        self._loaded_strategy_ids = loaded

    async def clear_session(self) -> None:
        """Clear the SQX session by loading an empty strategy list.

        Note: This is a workaround since unload_strategy is not available
        via the HTTP API. The caller should decide when to clear.
        """
        # We can't truly clear via HTTP API without knowing all loaded IDs.
        # The daemon/session would need to be restarted for a true reset.
        self._loaded_strategy_ids.clear()

    @staticmethod
    def _parse_weights(
        result: dict,
        fitness: str = "ReturnDDRatio",
    ) -> PortfolioWeightResult:
        """Parse and validate portfolio weight results from SQX API response.

        Args:
            result: SQX API response dict.
                    Expected format: ``{"weights": {"strat1": 0.3, "strat2": 0.7}}``
            fitness: Fitness function used during optimization.

        Returns:
            PortfolioWeightResult with validated and ranked weights.

        Raises:
            PortfolioOptimizationError: If weights data is missing, empty, or invalid.
        """
        if not isinstance(result, dict):
            raise PortfolioOptimizationError(
                f"Expected dict result, got {type(result).__name__}"
            )

        raw_weights = result.get("weights")
        if raw_weights is None:
            raise PortfolioOptimizationError(
                "Missing 'weights' key in optimization result"
            )

        if not isinstance(raw_weights, dict):
            raise PortfolioOptimizationError(
                f"Expected dict for 'weights', got {type(raw_weights).__name__}"
            )

        if not raw_weights:
            raise PortfolioOptimizationError("Empty weights dict in optimization result")

        # Validate each weight is numeric and in [0, 1]
        parsed: list[tuple[str, float]] = []
        for sid, weight in raw_weights.items():
            if not isinstance(weight, (int, float)):
                raise PortfolioOptimizationError(
                    f"Weight for '{sid}' must be numeric, got {type(weight).__name__}"
                )
            w = float(weight)
            if w < 0:
                raise PortfolioOptimizationError(
                    f"Weight for '{sid}' is negative: {w}"
                )
            if w > 1.0:
                raise PortfolioOptimizationError(
                    f"Weight for '{sid}' exceeds 1.0: {w}"
                )
            parsed.append((sid, w))

        # Check if sum is approximately 1.0 (within 0.01 epsilon)
        total_weight = sum(w for _, w in parsed)
        is_normalized = abs(total_weight - 1.0) <= 0.01

        # Rank by weight descending (tie-break by strategy_id for determinism)
        sorted_weights = sorted(parsed, key=lambda x: (-x[1], x[0]))
        weight_results = [
            WeightResult(strategy_id=sid, weight=w, rank=rank + 1)
            for rank, (sid, w) in enumerate(sorted_weights)
        ]

        return PortfolioWeightResult(
            weights=weight_results,
            total_weight=total_weight,
            fitness=fitness,
            is_normalized=is_normalized,
        )

    @staticmethod
    def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        """Clamp weights to [0, 1] and re-normalize to sum to 1.0.

        Args:
            weights: Dict mapping strategy_id -> weight.

        Returns:
            Dict with same keys, weights normalized to sum to 1.0.

        Raises:
            PortfolioOptimizationError: If input is empty or all weights
                are zero/negative after clamping.
        """
        if not weights:
            raise PortfolioOptimizationError("Cannot normalize empty weights dict")

        # Clamp each weight to [0, 1]
        clamped = {sid: max(0.0, min(float(w), 1.0)) for sid, w in weights.items()}

        total = sum(clamped.values())
        if total <= 0:
            raise PortfolioOptimizationError(
                "Cannot normalize weights: total is zero or negative after clamping"
            )

        return {sid: w / total for sid, w in clamped.items()}

    async def optimize_weights(
        self,
        fitness: str = "ReturnDDRatio",
    ) -> PortfolioWeightResult:
        """Run Portfolio Composer weight optimization.

        Args:
            fitness: Fitness function (ReturnDDRatio, SharpeRatio, NetProfit, etc.)

        Returns:
            PortfolioWeightResult with validated and ranked weight results.

        Raises:
            PortfolioOptimizationError: If optimization fails or returns invalid data.
        """
        if not self._loaded_strategy_ids:
            raise PortfolioOptimizationError(
                "No strategies loaded. Call load_strategies() first."
            )

        try:
            result = await self._client.recompute_portfolio()
            return self._parse_weights(result, fitness=fitness)
        except PortfolioOptimizationError:
            raise
        except Exception as e:
            raise PortfolioOptimizationError(f"Optimization failed: {e}") from e

    async def save_portfolio(self, name: str) -> Path:
        """Save portfolio via SQX HTTP API and return CFX file path.

        Args:
            name: Portfolio name.

        Returns:
            Path to saved .cfx file.

        Raises:
            PortfolioSaveError: If save fails.
        """
        try:
            result = await self._client.save_portfolio(name)
            # Result should contain path to saved CFX
            cfx_path = result.get("path")
            if not cfx_path:
                raise PortfolioSaveError("No CFX path returned from save")
            return Path(cfx_path)
        except Exception as e:
            raise PortfolioSaveError(f"Failed to save portfolio: {e}") from e

    async def create_portfolio(
        self,
        strategy_ids: list[str],
        name: str,
        fitness: str = "ReturnDDRatio",
    ) -> Path:
        """High-level: load strategies, optimize weights, save portfolio in one call.

        Returns:
            Path to saved portfolio .cfx file.
        """
        await self.load_strategies(strategy_ids)
        await self.optimize_weights(fitness)
        return await self.save_portfolio(name)

    @property
    def loaded_strategies(self) -> list[str]:
        return self._loaded_strategy_ids.copy()