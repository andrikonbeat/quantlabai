"""Tests for PortfolioComposer — weight parsing, normalization, optimization flow."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from quantlab.phase4.portfolio_composer import (
    PortfolioComposer,
    PortfolioWeightResult,
    WeightResult,
)
from quantlab.phase4.errors import PortfolioOptimizationError


# ── Dataclass unit tests ──────────────────────────────────────────────────────


class TestWeightResult:
    """Tests for WeightResult dataclass."""

    def test_creation(self):
        wr = WeightResult("strat_1", 0.3, 1)
        assert wr.strategy_id == "strat_1"
        assert wr.weight == 0.3
        assert wr.rank == 1


class TestPortfolioWeightResult:
    """Tests for PortfolioWeightResult dataclass."""

    def test_creation(self):
        wr = WeightResult("strat_1", 0.3, 1)
        pwr = PortfolioWeightResult(
            weights=[wr],
            total_weight=0.3,
            fitness="ReturnDDRatio",
            is_normalized=True,
        )
        assert len(pwr.weights) == 1
        assert pwr.total_weight == 0.3
        assert pwr.fitness == "ReturnDDRatio"
        assert pwr.is_normalized is True

    def test_defaults(self):
        pwr = PortfolioWeightResult()
        assert pwr.weights == []
        assert pwr.total_weight == 0.0
        assert pwr.fitness == "ReturnDDRatio"
        assert pwr.is_normalized is False


# ── _parse_weights ────────────────────────────────────────────────────────────


class TestParseWeights:
    """Tests for _parse_weights static method."""

    def test_valid_weights(self):
        result = {"weights": {"strat_1": 0.3, "strat_2": 0.7}}
        pwr = PortfolioComposer._parse_weights(result, fitness="ReturnDDRatio")

        assert len(pwr.weights) == 2
        assert pwr.total_weight == pytest.approx(1.0)
        assert pwr.fitness == "ReturnDDRatio"
        assert pwr.is_normalized is True

        # Rank 1: strat_2 (0.7)
        assert pwr.weights[0].strategy_id == "strat_2"
        assert pwr.weights[0].weight == 0.7
        assert pwr.weights[0].rank == 1

        # Rank 2: strat_1 (0.3)
        assert pwr.weights[1].strategy_id == "strat_1"
        assert pwr.weights[1].rank == 2

    def test_three_weights_ranking(self):
        result = {"weights": {"a": 0.1, "b": 0.5, "c": 0.4}}
        pwr = PortfolioComposer._parse_weights(result)
        assert [w.strategy_id for w in pwr.weights] == ["b", "c", "a"]
        assert [w.rank for w in pwr.weights] == [1, 2, 3]

    def test_tie_break_by_id(self):
        """Same weight values should be deterministic — sorted by id."""
        result = {"weights": {"z": 0.5, "a": 0.5}}
        pwr = PortfolioComposer._parse_weights(result)
        # Both have 0.5, tie-break by strategy_id ascending
        assert pwr.weights[0].strategy_id == "a"
        assert pwr.weights[0].rank == 1
        assert pwr.weights[1].strategy_id == "z"
        assert pwr.weights[1].rank == 2

    def test_empty_weights_raises(self):
        result = {"weights": {}}
        with pytest.raises(PortfolioOptimizationError, match="Empty weights"):
            PortfolioComposer._parse_weights(result)

    def test_missing_weights_key_raises(self):
        result = {}
        with pytest.raises(PortfolioOptimizationError, match="Missing.*weights"):
            PortfolioComposer._parse_weights(result)

    def test_negative_weight_raises(self):
        result = {"weights": {"a": -0.1, "b": 0.5}}
        with pytest.raises(PortfolioOptimizationError, match="negative"):
            PortfolioComposer._parse_weights(result)

    def test_weight_over_one_raises(self):
        result = {"weights": {"a": 0.5, "b": 1.5}}
        with pytest.raises(PortfolioOptimizationError, match="exceeds 1.0"):
            PortfolioComposer._parse_weights(result)

    def test_non_numeric_weight_raises(self):
        result = {"weights": {"a": "invalid"}}
        with pytest.raises(PortfolioOptimizationError, match="numeric"):
            PortfolioComposer._parse_weights(result)

    def test_not_normalized(self):
        """Weights sum to 0.6 — should not be flagged as normalized."""
        result = {"weights": {"a": 0.3, "b": 0.3}}
        pwr = PortfolioComposer._parse_weights(result)
        assert pwr.is_normalized is False
        assert pwr.total_weight == pytest.approx(0.6)

    def test_not_normalized_barely_over_epsilon(self):
        """Sum = 1.02, > 0.01 from 1.0 => not normalized."""
        result = {"weights": {"a": 0.51, "b": 0.51}}
        pwr = PortfolioComposer._parse_weights(result)
        assert pwr.is_normalized is False
        assert pwr.total_weight == pytest.approx(1.02)

    def test_normalized_within_epsilon_low(self):
        """Sum = 0.995, within 0.01 epsilon => normalized."""
        result = {"weights": {"a": 0.5, "b": 0.495}}
        pwr = PortfolioComposer._parse_weights(result)
        assert pwr.is_normalized is True
        assert pwr.total_weight == pytest.approx(0.995)

    def test_normalized_within_epsilon_high(self):
        """Sum = 1.005, within 0.01 epsilon => normalized."""
        result = {"weights": {"a": 0.5, "b": 0.505}}
        pwr = PortfolioComposer._parse_weights(result)
        assert pwr.is_normalized is True
        assert pwr.total_weight == pytest.approx(1.005)

    def test_single_strategy(self):
        result = {"weights": {"only_one": 1.0}}
        pwr = PortfolioComposer._parse_weights(result)
        assert len(pwr.weights) == 1
        assert pwr.weights[0].strategy_id == "only_one"
        assert pwr.weights[0].rank == 1
        assert pwr.is_normalized is True

    def test_result_not_dict_raises(self):
        with pytest.raises(PortfolioOptimizationError, match="Expected dict"):
            PortfolioComposer._parse_weights("not a dict")

    def test_weights_not_dict_raises(self):
        result = {"weights": [1, 2, 3]}
        with pytest.raises(
            PortfolioOptimizationError, match="Expected dict for.*weights"
        ):
            PortfolioComposer._parse_weights(result)

    def test_fitness_passthrough(self):
        """Fitness string should be passed through to PortfolioWeightResult."""
        result = {"weights": {"a": 1.0}}
        pwr = PortfolioComposer._parse_weights(result, fitness="SharpeRatio")
        assert pwr.fitness == "SharpeRatio"

    def test_integer_weights_accepted(self):
        """Integer weights (e.g. 0, 1) should be accepted and cast to float."""
        result = {"weights": {"a": 0, "b": 1}}
        pwr = PortfolioComposer._parse_weights(result)
        # b (weight=1) sorts first
        assert pwr.weights[0].strategy_id == "b"
        assert pwr.weights[0].weight == 1.0
        assert pwr.weights[0].rank == 1
        # a (weight=0) sorts second
        assert pwr.weights[1].strategy_id == "a"
        assert pwr.weights[1].weight == 0.0
        assert pwr.weights[1].rank == 2
        # Sum = 1, should be normalized
        assert pwr.is_normalized is True


# ── normalize_weights ────────────────────────────────────────────────────────


class TestNormalizeWeights:
    """Tests for normalize_weights static method."""

    def test_normalize_basic(self):
        weights = {"a": 0.3, "b": 0.3}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert sum(normalized.values()) == pytest.approx(1.0)
        assert normalized["a"] == pytest.approx(0.5)
        assert normalized["b"] == pytest.approx(0.5)

    def test_normalize_sums_to_one(self):
        for _ in range(5):
            result = PortfolioComposer.normalize_weights(
                {"a": 0.1, "b": 0.2, "c": 0.7}
            )
            assert abs(sum(result.values()) - 1.0) < 1e-10

    def test_clamps_negative(self):
        weights = {"a": -0.5, "b": 0.5}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert normalized["a"] == 0.0
        assert normalized["b"] == 1.0

    def test_clamps_over_one(self):
        weights = {"a": 0.5, "b": 2.0}
        normalized = PortfolioComposer.normalize_weights(weights)
        # After clamp: a=0.5, b=1.0 → sum=1.5 → a=0.5/1.5, b=1.0/1.5
        assert normalized["a"] == pytest.approx(0.5 / 1.5)
        assert normalized["b"] == pytest.approx(1.0 / 1.5)
        assert sum(normalized.values()) == pytest.approx(1.0)

    def test_single_weight(self):
        weights = {"a": 0.5}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert normalized["a"] == pytest.approx(1.0)

    def test_single_weight_over_one(self):
        weights = {"a": 5.0}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert normalized["a"] == pytest.approx(1.0)

    def test_single_weight_negative_raises(self):
        """Single negative weight clamps to 0.0, total=0 → raises."""
        weights = {"a": -5.0}
        with pytest.raises(
            PortfolioOptimizationError, match="total is zero"
        ):
            PortfolioComposer.normalize_weights(weights)

    def test_empty_weights_raises(self):
        with pytest.raises(PortfolioOptimizationError, match="Cannot normalize empty"):
            PortfolioComposer.normalize_weights({})

    def test_all_zeros_raises(self):
        with pytest.raises(PortfolioOptimizationError, match="total is zero"):
            PortfolioComposer.normalize_weights({"a": 0.0, "b": 0.0})

    def test_all_negative_raises(self):
        with pytest.raises(PortfolioOptimizationError, match="total is zero"):
            PortfolioComposer.normalize_weights({"a": -0.1, "b": -0.2})

    def test_preserves_keys(self):
        weights = {"alpha": 0.2, "beta": 0.3, "gamma": 0.5}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert set(normalized.keys()) == {"alpha", "beta", "gamma"}

    def test_normalize_mixed_clamping(self):
        """Mix of valid, negative, and over-one weights."""
        weights = {"a": -0.1, "b": 0.3, "c": 2.0}
        normalized = PortfolioComposer.normalize_weights(weights)
        # After clamping: a=0, b=0.3, c=1.0 => total=1.3
        assert normalized["a"] == pytest.approx(0.0)
        assert normalized["b"] == pytest.approx(0.3 / 1.3)
        assert normalized["c"] == pytest.approx(1.0 / 1.3)
        assert sum(normalized.values()) == pytest.approx(1.0)

    def test_float_precision_stability(self):
        """Very small weights should not cause numerical instability."""
        weights = {"a": 1e-10, "b": 1.0}
        normalized = PortfolioComposer.normalize_weights(weights)
        assert sum(normalized.values()) == pytest.approx(1.0)


# ── optimize_weights (async) ──────────────────────────────────────────────────


class TestOptimizeWeights:
    """Tests for optimize_weights async method."""

    @pytest.mark.asyncio
    async def test_success(self):
        client = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            return_value={"weights": {"a": 0.3, "b": 0.7}}
        )
        composer = PortfolioComposer(client)
        composer._loaded_strategy_ids = ["a", "b"]

        result = await composer.optimize_weights(fitness="SharpeRatio")

        assert isinstance(result, PortfolioWeightResult)
        assert len(result.weights) == 2
        assert result.fitness == "SharpeRatio"
        assert result.is_normalized is True
        assert result.weights[0].strategy_id == "b"
        assert result.weights[0].weight == 0.7

    @pytest.mark.asyncio
    async def test_no_strategies_loaded_raises(self):
        composer = PortfolioComposer(AsyncMock())
        with pytest.raises(
            PortfolioOptimizationError, match="No strategies loaded"
        ):
            await composer.optimize_weights()

    @pytest.mark.asyncio
    async def test_client_raises_wrapped(self):
        client = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            side_effect=RuntimeError("SQX crash")
        )
        composer = PortfolioComposer(client)
        composer._loaded_strategy_ids = ["a"]

        with pytest.raises(
            PortfolioOptimizationError, match="Optimization failed"
        ):
            await composer.optimize_weights()

    @pytest.mark.asyncio
    async def test_invalid_weights_from_api_raises(self):
        """Validation error from _parse_weights should propagate directly."""
        client = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            return_value={"weights": {"a": -0.1, "b": 0.5}}
        )
        composer = PortfolioComposer(client)
        composer._loaded_strategy_ids = ["a", "b"]

        with pytest.raises(PortfolioOptimizationError, match="negative"):
            await composer.optimize_weights()

    @pytest.mark.asyncio
    async def test_empty_weights_from_api_raises(self):
        client = AsyncMock()
        client.recompute_portfolio = AsyncMock(return_value={"weights": {}})
        composer = PortfolioComposer(client)
        composer._loaded_strategy_ids = ["a", "b"]

        with pytest.raises(PortfolioOptimizationError, match="Empty weights"):
            await composer.optimize_weights()


# ── create_portfolio (backward compatibility) ─────────────────────────────────


class TestCreatePortfolio:
    """Tests for create_portfolio high-level method — must still return Path."""

    @pytest.mark.asyncio
    async def test_returns_path(self):
        client = AsyncMock()
        client.load_strategy = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            return_value={"weights": {"a": 1.0}}
        )
        client.save_portfolio = AsyncMock(
            return_value={"path": "/tmp/test_portfolio.cfx"}
        )

        composer = PortfolioComposer(client)
        result = await composer.create_portfolio(
            strategy_ids=["a"],
            name="test_portfolio",
        )

        assert isinstance(result, Path)
        assert str(result) == "/tmp/test_portfolio.cfx"

    @pytest.mark.asyncio
    async def test_preserves_loaded_strategies(self):
        client = AsyncMock()
        client.load_strategy = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            return_value={"weights": {"a": 1.0}}
        )
        client.save_portfolio = AsyncMock(
            return_value={"path": "/tmp/test.cfx"}
        )

        composer = PortfolioComposer(client)
        await composer.create_portfolio(
            strategy_ids=["a"],
            name="test",
        )

        assert composer.loaded_strategies == ["a"]

    @pytest.mark.asyncio
    async def test_multiple_strategies(self):
        client = AsyncMock()
        client.load_strategy = AsyncMock()
        client.recompute_portfolio = AsyncMock(
            return_value={"weights": {"s1": 0.6, "s2": 0.4}}
        )
        client.save_portfolio = AsyncMock(
            return_value={"path": "/tmp/multi.cfx"}
        )

        composer = PortfolioComposer(client)
        result = await composer.create_portfolio(
            strategy_ids=["s1", "s2"],
            name="multi_test",
        )

        assert isinstance(result, Path)
        # Load was called for both
        assert client.load_strategy.call_count == 2
