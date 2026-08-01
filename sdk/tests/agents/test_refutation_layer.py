"""Tests for RefutationLayer — PR 1: Core + Regime Strategy.

Strict TDD: tests written before implementation (RED).
PR 1: RefutationConfig, FalsationVerdict/RefutationResult dataclasses,
      RefutationStrategy ABC, RegimeMismatchStrategy, RefutationLayer facade.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.dsl.models import HypothesisConfig

# These imports will fail initially (RED) — that's intentional TDD:
from quantlab.agents.refutation import FalsationVerdict, RefutationLayer, RefutationResult
from quantlab.agents.refutation.config import RefutationConfig
from quantlab.agents.refutation.strategies import RefutationStrategy
from quantlab.agents.refutation.strategies.regime import (
    RegimeMismatchStrategy,
    _infer_assumed_regime,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def hyp_trend_following() -> HypothesisConfig:
    return HypothesisConfig(
        name="momentum_hyp",
        description="trend-following momentum on EURUSD",
        data_sources=["yahoo"],
    )


@pytest.fixture
def hyp_mean_reversion() -> HypothesisConfig:
    return HypothesisConfig(
        name="meanrev_hyp",
        description="mean-reversion strategy for range-bound markets",
        data_sources=["yahoo"],
    )


@pytest.fixture
def hyp_generic() -> HypothesisConfig:
    return HypothesisConfig(
        name="generic_hyp",
        description="buy when RSI < 30 on any liquid pair",
        data_sources=["yahoo"],
    )


# ── Task 1.1: RefutationConfig ─────────────────────────────────────────────────


class TestRefutationConfig:
    """RefutationConfig Pydantic model."""

    def test_default_enabled(self) -> None:
        """Default config has enabled=True."""
        config = RefutationConfig()
        assert config.enabled is True

    def test_explicit_disabled(self) -> None:
        """Can set enabled=False explicitly."""
        config = RefutationConfig(enabled=False)
        assert config.enabled is False

    def test_enabled_true_explicit(self) -> None:
        """enabled=True is accepted and stored."""
        config = RefutationConfig(enabled=True)
        assert config.enabled is True

    def test_extra_fields_rejected(self) -> None:
        """Extra fields not in the model are rejected."""
        with pytest.raises(ValueError):
            RefutationConfig(enabled=True, unknown_field="xxx")  # type: ignore[call-arg]


# ── Task 1.2: FalsationVerdict + RefutationResult ──────────────────────────────


class TestFalsationVerdict:
    """FalsationVerdict dataclass fields and behavior."""

    def test_all_fields(self) -> None:
        """All fields are stored correctly."""
        v = FalsationVerdict(
            hypothesis_name="test_hyp",
            falsification_score=0.5,
            evidence=["regime mismatch", "low sharpe"],
            strategy="regime_mismatch",
        )
        assert v.hypothesis_name == "test_hyp"
        assert v.falsification_score == 0.5
        assert v.evidence == ["regime mismatch", "low sharpe"]
        assert v.strategy == "regime_mismatch"

    def test_zero_score_default(self) -> None:
        """Score 0.0 means no falsation found."""
        v = FalsationVerdict(
            hypothesis_name="safe_hyp",
            falsification_score=0.0,
            evidence=[],
            strategy="regime_mismatch",
        )
        assert v.falsification_score == 0.0
        assert v.evidence == []

    def test_max_score(self) -> None:
        """Score up to 1.0 is valid (fully refuted)."""
        v = FalsationVerdict(
            hypothesis_name="bad_hyp",
            falsification_score=1.0,
            evidence=["completely refuted"],
            strategy="adversarial",
        )
        assert v.falsification_score == 1.0


class TestRefutationResult:
    """RefutationResult aggregate."""

    def test_empty_result(self) -> None:
        """Result with no verdicts has empty summary."""
        result = RefutationResult(verdicts=[], summary={})
        assert result.verdicts == []
        assert result.summary == {}

    def test_with_verdicts(self) -> None:
        """Result holds multiple verdicts with summary."""
        verdicts = [
            FalsationVerdict(
                hypothesis_name="h1",
                falsification_score=0.0,
                evidence=[],
                strategy="regime_mismatch",
            ),
            FalsationVerdict(
                hypothesis_name="h2",
                falsification_score=0.6,
                evidence=["regime mismatch"],
                strategy="regime_mismatch",
            ),
        ]
        summary = {"mean_score": 0.3, "max_score": 0.6}
        result = RefutationResult(verdicts=verdicts, summary=summary)
        assert len(result.verdicts) == 2
        assert result.verdicts[0].hypothesis_name == "h1"
        assert result.verdicts[1].falsification_score == 0.6
        assert result.summary["mean_score"] == 0.3


# ── Task 1.3: RefutationStrategy ABC ───────────────────────────────────────────


class TestRefutationStrategy:
    """RefutationStrategy ABC contract."""

    def test_cannot_instantiate_abc(self) -> None:
        """ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            RefutationStrategy()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_refute(self) -> None:
        """Subclass without refute() cannot be instantiated."""
        with pytest.raises(TypeError):

            class Incomplete(RefutationStrategy):  # type: ignore[misc]
                pass

            Incomplete()

    def test_concrete_subclass_works(self) -> None:
        """Subclass with refute() can be instantiated and called."""

        class FakeStrategy(RefutationStrategy):
            async def refute(
                self,
                hypothesis: HypothesisConfig,
                market_context: dict[str, Any] | None = None,
            ) -> FalsationVerdict:
                return FalsationVerdict(
                    hypothesis_name=hypothesis.name,
                    falsification_score=0.0,
                    evidence=[],
                    strategy="fake",
                )

        strat = FakeStrategy()
        assert isinstance(strat, RefutationStrategy)


# ── Task 1.4: RegimeMismatchStrategy ───────────────────────────────────────────


class TestRegimeMismatchHelpers:
    """_infer_assumed_regime helper function."""

    def test_trend_following(self) -> None:
        """'trend-following momentum' infers 'trending'."""
        assert _infer_assumed_regime("trend-following momentum on EURUSD") == "trending"

    def test_trend_keyword(self) -> None:
        """'trend' keyword infers 'trending'."""
        assert _infer_assumed_regime("trend following system") == "trending"

    def test_momentum_keyword(self) -> None:
        """'momentum' keyword infers 'trending'."""
        assert _infer_assumed_regime("momentum strategy") == "trending"

    def test_mean_reversion_dash(self) -> None:
        """'mean-reversion' keyword infers 'range-bound'."""
        assert _infer_assumed_regime("mean-reversion on EURUSD") == "range-bound"

    def test_mean_reversion_text(self) -> None:
        """'mean reversion' keyword infers 'range-bound'."""
        assert _infer_assumed_regime("mean reversion strategy") == "range-bound"

    def test_range_keyword(self) -> None:
        """'range-bound' keyword infers 'range-bound'."""
        assert _infer_assumed_regime("range-bound market strategy") == "range-bound"

    def test_no_keyword_returns_unknown(self) -> None:
        """Description with no regime keywords returns 'unknown'."""
        assert _infer_assumed_regime("buy when RSI < 30") == "unknown"

    def test_empty_description_returns_unknown(self) -> None:
        """Empty description returns 'unknown'."""
        assert _infer_assumed_regime("") == "unknown"


class TestRegimeMismatchStrategy:
    """RegimeMismatchStrategy scoring."""

    @pytest.mark.asyncio
    async def test_s1_regime_mismatch_score_ge_03(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """S-1: Regime mismatch produces falsification_score >= 0.3."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "range-bound"}

        verdict = await strategy.refute(hyp_trend_following, market_context)

        assert verdict.hypothesis_name == "momentum_hyp"
        assert verdict.falsification_score >= 0.3
        assert verdict.strategy == "regime_mismatch"
        assert len(verdict.evidence) >= 1

    @pytest.mark.asyncio
    async def test_score_zero_when_regime_matches(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """When assumed regime matches detected, score is 0.0."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "trending"}

        verdict = await strategy.refute(hyp_trend_following, market_context)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []

    @pytest.mark.asyncio
    async def test_score_zero_when_no_regime_info(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """When no detected regime in context, score is 0.0."""
        strategy = RegimeMismatchStrategy()

        verdict = await strategy.refute(hyp_trend_following, None)

        assert verdict.falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_score_zero_when_unknown_assumed_regime(
        self, hyp_generic: HypothesisConfig
    ) -> None:
        """When assumed regime is 'unknown', score is 0.0."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "range-bound"}

        verdict = await strategy.refute(hyp_generic, market_context)

        assert verdict.falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_score_zero_when_detected_regime_unknown(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """When detected regime is 'unknown', score is 0.0."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "unknown"}

        verdict = await strategy.refute(hyp_trend_following, market_context)

        assert verdict.falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_s4_all_passes_low_score(
        self, hyp_mean_reversion: HypothesisConfig
    ) -> None:
        """S-4: When regimes match, score is low (< 0.3)."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "range-bound"}

        verdict = await strategy.refute(hyp_mean_reversion, market_context)

        assert verdict.falsification_score < 0.3

    @pytest.mark.asyncio
    async def test_mean_reversion_mismatch(
        self, hyp_mean_reversion: HypothesisConfig
    ) -> None:
        """mean-reversion hyp in trending regime scores >= 0.3."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "trending"}

        verdict = await strategy.refute(hyp_mean_reversion, market_context)

        assert verdict.falsification_score >= 0.3

    @pytest.mark.asyncio
    async def test_trend_following_mismatch_score_not_exceed_06(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """RF-2: Regime mismatch score caps at 0.6."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "range-bound"}

        verdict = await strategy.refute(hyp_trend_following, market_context)

        assert verdict.falsification_score <= 0.6

    @pytest.mark.asyncio
    async def test_provides_evidence_on_mismatch(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """Evidence includes assumed and detected regime on mismatch."""
        strategy = RegimeMismatchStrategy()
        market_context = {"detected_regime": "range-bound"}

        verdict = await strategy.refute(hyp_trend_following, market_context)

        assert any("trending" in e for e in verdict.evidence)
        assert any("range-bound" in e for e in verdict.evidence)


# ── Task 1.2/1.5: RefutationLayer Facade ───────────────────────────────────────


class TestRefutationLayer:
    """RefutationLayer facade dispatch and aggregation."""

    @pytest.mark.asyncio
    async def test_default_config_enabled(self) -> None:
        """Layer is enabled by default."""
        layer = RefutationLayer()
        assert layer._config.enabled is True

    @pytest.mark.asyncio
    async def test_s5_disabled_returns_empty_result(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """S-5: When disabled, refute() returns empty result with 0.0 scores."""
        config = RefutationConfig(enabled=False)
        layer = RefutationLayer(config=config)

        result = await layer.refute(
            hypotheses=[hyp_trend_following],
        )

        assert len(result.verdicts) == 1
        assert result.verdicts[0].falsification_score == 0.0
        assert result.verdicts[0].evidence == []

    @pytest.mark.asyncio
    async def test_rf9_disabled_no_strategy_execution(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """RF-9: When disabled, strategies are not executed."""
        config = RefutationConfig(enabled=False)
        layer = RefutationLayer(config=config)

        with patch.object(layer, "_strategies") as mock_strategies:
            result = await layer.refute(
                hypotheses=[hyp_trend_following],
            )

            mock_strategies[0].refute.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_hypotheses_returns_empty_result(self) -> None:
        """No hypotheses returns RefutationResult with empty verdicts."""
        layer = RefutationLayer()

        result = await layer.refute(hypotheses=[])

        assert result.verdicts == []

    @pytest.mark.asyncio
    async def test_rf5_score_is_max_of_strategies(
        self, hyp_trend_following: HypothesisConfig
    ) -> None:
        """RF-5: Final score is max of all strategy scores."""
        layer = RefutationLayer()

        # The regime strategy alone determines the score
        result = await layer.refute(
            hypotheses=[hyp_trend_following],
            market_context={"detected_regime": "range-bound"},
        )

        assert len(result.verdicts) == 1
        assert result.verdicts[0].falsification_score >= 0.3

    @pytest.mark.asyncio
    async def test_rf6_non_blocking_returns_all_hypotheses(
        self,
    ) -> None:
        """RF-6: All hypotheses are returned, none filtered."""
        layer = RefutationLayer()
        hyps = [
            HypothesisConfig(name="h1", description="trend-following momentum"),
            HypothesisConfig(name="h2", description="mean-reversion strategy"),
            HypothesisConfig(name="h3", description="breakout system"),
        ]

        result = await layer.refute(
            hypotheses=hyps,
            market_context={"detected_regime": "range-bound"},
        )

        assert len(result.verdicts) == 3
        names = {v.hypothesis_name for v in result.verdicts}
        assert names == {"h1", "h2", "h3"}

    @pytest.mark.asyncio
    async def test_summary_includes_count_and_max_score(
        self,
    ) -> None:
        """Summary dict includes basic aggregate stats."""
        layer = RefutationLayer()
        hyps = [
            HypothesisConfig(name="h1", description="trend-following momentum"),
            HypothesisConfig(name="h2", description="mean-reversion strategy"),
        ]

        result = await layer.refute(
            hypotheses=hyps,
            market_context={"detected_regime": "range-bound"},
        )

        assert "total_verdicts" in result.summary
        assert result.summary["total_verdicts"] == 2
        assert "max_score" in result.summary
        assert result.summary["max_score"] >= 0.3

    @pytest.mark.asyncio
    async def test_per_hypothesis_verdict(
        self,
    ) -> None:
        """Each hypothesis gets its own verdict with correct strategy name."""
        layer = RefutationLayer()
        hyp = HypothesisConfig(
            name="test_hyp",
            description="trend-following momentum",
        )

        result = await layer.refute(
            hypotheses=[hyp],
            market_context={"detected_regime": "range-bound"},
        )

        v = result.verdicts[0]
        assert v.hypothesis_name == "test_hyp"
        assert v.strategy == "regime_mismatch"
        assert v.falsification_score >= 0.3


# ── Task 2.1: HistoricalCounterExampleStrategy ────────────────────────────────


class TestHistoricalCounterExampleStrategy:
    """HistoricalCounterExampleStrategy — YahooFinanceProvider integration (RF-3)."""

    @pytest.fixture
    def mock_provider(self) -> AsyncMock:
        """Mock YahooFinanceProvider that returns declining price data."""
        provider = AsyncMock()
        # 35 days of consistent decline: 1.12 → 0.77 (generates RSI < 30)
        prices = []
        start_price = 1.12
        for i in range(35):
            price = round(start_price - i * 0.01, 2)
            day = f"2020-01-{i+1:02d}"
            prices.append({
                "date": day, "open": price, "high": price + 0.01,
                "low": price - 0.01, "close": price, "volume": 1000 + i * 100,
            })
        provider.fetch.return_value = {
            "ticker": "EURUSD",
            "prices": prices,
            "fundamentals": {},
            "info": {},
        }
        return provider

    @pytest.fixture
    def hyp_buy_rsi30(self) -> HypothesisConfig:
        return HypothesisConfig(
            name="oversold_buy",
            description="buy when RSI < 30 on EURUSD",
            data_sources=["yahoo"],
            parameters={"symbol": "EURUSD"},
        )

    @pytest.fixture
    def hyp_no_symbol(self) -> HypothesisConfig:
        return HypothesisConfig(
            name="no_symbol_hyp",
            description="buy when momentum is strong",
            data_sources=["yahoo"],
        )

    @pytest.mark.asyncio
    async def test_rf3_counter_example_found_increases_score(
        self, mock_provider: AsyncMock, hyp_buy_rsi30: HypothesisConfig
    ) -> None:
        """RF-3: When a counter-example is found, score increases (up to 0.8)."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        strategy = HistoricalCounterExampleStrategy(provider=mock_provider)
        verdict = await strategy.refute(hypothesis=hyp_buy_rsi30)

        assert verdict.strategy == "historical_counterexample"
        # With consistent decline data, counter-examples should be found
        assert verdict.falsification_score > 0.0
        assert len(verdict.evidence) >= 1

    @pytest.mark.asyncio
    async def test_s2_score_bounded_by_08(
        self, mock_provider: AsyncMock, hyp_buy_rsi30: HypothesisConfig
    ) -> None:
        """S-2/RF-3: Historical counter-example score does not exceed 0.8."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        strategy = HistoricalCounterExampleStrategy(provider=mock_provider)
        verdict = await strategy.refute(hypothesis=hyp_buy_rsi30)

        assert verdict.falsification_score <= 0.8

    @pytest.mark.asyncio
    async def test_no_symbol_returns_zero(
        self, mock_provider: AsyncMock, hyp_no_symbol: HypothesisConfig
    ) -> None:
        """When no symbol can be extracted, score is 0.0."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        strategy = HistoricalCounterExampleStrategy(provider=mock_provider)
        verdict = await strategy.refute(hypothesis=hyp_no_symbol)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []

    @pytest.mark.asyncio
    async def test_provider_error_graceful_skip(
        self, hyp_buy_rsi30: HypothesisConfig
    ) -> None:
        """When YahooFinanceProvider raises an error, strategy skips gracefully."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        provider = AsyncMock()
        provider.fetch.side_effect = Exception("API error")

        strategy = HistoricalCounterExampleStrategy(provider=provider)
        verdict = await strategy.refute(hypothesis=hyp_buy_rsi30)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []

    @pytest.mark.asyncio
    async def test_no_prices_returns_zero(
        self, hyp_buy_rsi30: HypothesisConfig
    ) -> None:
        """When provider returns no prices, score is 0.0."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        provider = AsyncMock()
        provider.fetch.return_value = {
            "ticker": "EURUSD",
            "prices": [],
            "fundamentals": {},
        }

        strategy = HistoricalCounterExampleStrategy(provider=provider)
        verdict = await strategy.refute(hypothesis=hyp_buy_rsi30)

        assert verdict.falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_happy_data_no_counter_example(
        self, hyp_buy_rsi30: HypothesisConfig
    ) -> None:
        """When price data shows consistent uptrend, no counter-example → score 0."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )

        provider = AsyncMock()
        provider.fetch.return_value = {
            "ticker": "EURUSD",
            "prices": [
                {"date": "2020-01-01", "open": 1.00, "high": 1.02, "low": 0.99, "close": 1.01, "volume": 1000},
                {"date": "2020-01-02", "open": 1.01, "high": 1.03, "low": 1.00, "close": 1.02, "volume": 1100},
                {"date": "2020-01-03", "open": 1.02, "high": 1.04, "low": 1.01, "close": 1.03, "volume": 1200},
                {"date": "2020-01-04", "open": 1.03, "high": 1.05, "low": 1.02, "close": 1.04, "volume": 1300},
                {"date": "2020-01-05", "open": 1.04, "high": 1.06, "low": 1.03, "close": 1.05, "volume": 1400},
                {"date": "2020-01-06", "open": 1.05, "high": 1.07, "low": 1.04, "close": 1.06, "volume": 1500},
                {"date": "2020-01-07", "open": 1.06, "high": 1.08, "low": 1.05, "close": 1.07, "volume": 1600},
                {"date": "2020-01-08", "open": 1.07, "high": 1.09, "low": 1.06, "close": 1.08, "volume": 1700},
                {"date": "2020-01-09", "open": 1.08, "high": 1.10, "low": 1.07, "close": 1.09, "volume": 1800},
                {"date": "2020-01-10", "open": 1.09, "high": 1.11, "low": 1.08, "close": 1.10, "volume": 1900},
                {"date": "2020-01-11", "open": 1.10, "high": 1.12, "low": 1.09, "close": 1.11, "volume": 2000},
                {"date": "2020-01-12", "open": 1.11, "high": 1.13, "low": 1.10, "close": 1.12, "volume": 2100},
                {"date": "2020-01-13", "open": 1.12, "high": 1.14, "low": 1.11, "close": 1.13, "volume": 2200},
                {"date": "2020-01-14", "open": 1.13, "high": 1.15, "low": 1.12, "close": 1.14, "volume": 2300},
                {"date": "2020-01-15", "open": 1.14, "high": 1.16, "low": 1.13, "close": 1.15, "volume": 2400},
            ],
            "fundamentals": {},
        }

        strategy = HistoricalCounterExampleStrategy(provider=provider)
        verdict = await strategy.refute(hypothesis=hyp_buy_rsi30)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []


# ── Task 2.2: LLMAdversarialStrategy ─────────────────────────────────────────


class TestLLMAdversarialStrategy:
    """LLMAdversarialStrategy — LLM adversarial refutation (RF-4)."""

    @pytest.fixture
    def hyp_with_rationale(self) -> HypothesisConfig:
        return HypothesisConfig(
            name="cpi_usd",
            description="CPI rising benefits USD",
            llm_rationale="Historical data shows USD strengthens when CPI exceeds expectations",
            source_urls=["https://example.com/cpi-data"],
            data_sources=["yahoo"],
        )

    @pytest.fixture
    def hyp_no_rationale(self) -> HypothesisConfig:
        return HypothesisConfig(
            name="simple_hyp",
            description="momentum strategy on SPY",
            data_sources=["yahoo"],
        )

    @pytest.mark.asyncio
    async def test_rf4_valid_llm_response_parses_score_and_evidence(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """RF-4: When LLM returns valid JSON, score and evidence are parsed."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_agent = AsyncMock()
        mock_agent.call_llm.return_value = json.dumps({
            "score": 0.7,
            "evidence": [
                "CPI rising can also trigger stagflation, hurting USD",
                "Market may have already priced in the CPI increase",
            ],
        })

        strategy = LLMAdversarialStrategy(llm_agent=mock_agent)
        verdict = await strategy.refute(hypothesis=hyp_with_rationale)

        assert verdict.strategy == "llm_adversarial"
        assert verdict.falsification_score == 0.7
        assert len(verdict.evidence) == 2
        assert "stagflation" in verdict.evidence[0]

    @pytest.mark.asyncio
    async def test_rf4_temperature_is_02(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """RF-4: LLMConfig is created with temperature=0.2."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        strategy = LLMAdversarialStrategy()
        assert strategy._llm_config.temperature == 0.2

    @pytest.mark.asyncio
    async def test_s3_llm_returns_score_and_evidence(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """S-3: LLM adversarial returns score + evidence with counter-arguments."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_agent = AsyncMock()
        mock_agent.call_llm.return_value = json.dumps({
            "score": 0.85,
            "evidence": [
                "Counter-argument: rising CPI may already be discounted",
                "Historical regime changes reduce CPI predictive power",
            ],
        })

        strategy = LLMAdversarialStrategy(llm_agent=mock_agent)
        verdict = await strategy.refute(hypothesis=hyp_with_rationale)

        assert verdict.falsification_score > 0.0
        assert len(verdict.evidence) >= 1

    @pytest.mark.asyncio
    async def test_rf4_llm_unavailable_graceful_skip(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """RF-4: When LLM is unavailable (ImportError), strategy skips."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_agent = AsyncMock()
        mock_agent.call_llm.side_effect = ImportError("openai SDK not installed")

        strategy = LLMAdversarialStrategy(llm_agent=mock_agent)
        verdict = await strategy.refute(hypothesis=hyp_with_rationale)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []

    @pytest.mark.asyncio
    async def test_invalid_json_response_returns_zero(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """When LLM returns invalid JSON, strategy skips gracefully."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_agent = AsyncMock()
        mock_agent.call_llm.return_value = "not valid json"

        strategy = LLMAdversarialStrategy(llm_agent=mock_agent)
        verdict = await strategy.refute(hypothesis=hyp_with_rationale)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []

    @pytest.mark.asyncio
    async def test_api_error_graceful_skip(
        self, hyp_with_rationale: HypothesisConfig
    ) -> None:
        """When LLM API raises an error, strategy skips gracefully."""
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_agent = AsyncMock()
        mock_agent.call_llm.side_effect = Exception("API timeout")

        strategy = LLMAdversarialStrategy(llm_agent=mock_agent)
        verdict = await strategy.refute(hypothesis=hyp_with_rationale)

        assert verdict.falsification_score == 0.0
        assert verdict.evidence == []


# ── Task 2.3: Integration — Score aggregation with all strategies ────────────


class TestRefutationLayerPR2Integration:
    """RefutationLayer facade with all three strategies (RF-5)."""

    @pytest.fixture
    def hyp_rsi(self) -> HypothesisConfig:
        return HypothesisConfig(
            name="oversold_buy",
            description="buy when RSI < 30 on EURUSD",
            data_sources=["yahoo"],
            parameters={"symbol": "EURUSD"},
        )

    @pytest.mark.asyncio
    async def test_default_strategies_include_all_three(
        self, hyp_rsi: HypothesisConfig
    ) -> None:
        """Default strategy list includes all three strategies."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        layer = RefutationLayer()
        strategy_types = {type(s).__name__ for s in layer._strategies}

        assert "RegimeMismatchStrategy" in strategy_types
        assert "HistoricalCounterExampleStrategy" in strategy_types
        assert "LLMAdversarialStrategy" in strategy_types

    @pytest.mark.asyncio
    async def test_rf5_max_aggregation_across_all_strategies(
        self, hyp_rsi: HypothesisConfig
    ) -> None:
        """RF-5: Final score is max of all strategy scores."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_historical = AsyncMock(spec=HistoricalCounterExampleStrategy)
        mock_historical.refute.return_value = FalsationVerdict(
            hypothesis_name="oversold_buy",
            falsification_score=0.6,
            evidence=["counter-example found"],
            strategy="historical_counterexample",
        )

        mock_adversarial = AsyncMock(spec=LLMAdversarialStrategy)
        mock_adversarial.refute.return_value = FalsationVerdict(
            hypothesis_name="oversold_buy",
            falsification_score=0.8,
            evidence=["LLM refutes"],
            strategy="llm_adversarial",
        )

        layer = RefutationLayer(strategies=[mock_historical, mock_adversarial])
        result = await layer.refute(hypotheses=[hyp_rsi])

        assert len(result.verdicts) == 1
        assert result.verdicts[0].falsification_score == 0.8  # max(0.6, 0.8)
        assert result.verdicts[0].strategy == "llm_adversarial"

    @pytest.mark.asyncio
    async def test_rf5_all_strategies_zero_score(
        self, hyp_rsi: HypothesisConfig
    ) -> None:
        """When all strategies return 0, aggregate score is 0."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_historical = AsyncMock(spec=HistoricalCounterExampleStrategy)
        mock_historical.refute.return_value = FalsationVerdict(
            hypothesis_name="oversold_buy",
            falsification_score=0.0,
            evidence=[],
            strategy="historical_counterexample",
        )

        mock_adversarial = AsyncMock(spec=LLMAdversarialStrategy)
        mock_adversarial.refute.return_value = FalsationVerdict(
            hypothesis_name="oversold_buy",
            falsification_score=0.0,
            evidence=[],
            strategy="llm_adversarial",
        )

        layer = RefutationLayer(strategies=[mock_historical, mock_adversarial])
        result = await layer.refute(hypotheses=[hyp_rsi])

        assert result.verdicts[0].falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_strategy_failure_does_not_affect_other_strategies(
        self, hyp_rsi: HypothesisConfig
    ) -> None:
        """When one strategy fails, others still contribute to max."""
        from quantlab.agents.refutation.strategies.historical import (
            HistoricalCounterExampleStrategy,
        )
        from quantlab.agents.refutation.strategies.adversarial import (
            LLMAdversarialStrategy,
        )

        mock_historical = AsyncMock(spec=HistoricalCounterExampleStrategy)
        mock_historical.refute.side_effect = Exception("provider error")

        mock_adversarial = AsyncMock(spec=LLMAdversarialStrategy)
        mock_adversarial.refute.return_value = FalsationVerdict(
            hypothesis_name="oversold_buy",
            falsification_score=0.5,
            evidence=["refuted"],
            strategy="llm_adversarial",
        )

        layer = RefutationLayer(strategies=[mock_historical, mock_adversarial])
        result = await layer.refute(hypotheses=[hyp_rsi])

        assert result.verdicts[0].falsification_score == 0.5


# ── Triangulation: edge cases ─────────────────────────────────────────────────


class TestRefutationLayerEdgeCases:
    """Additional edge cases for the refutation layer."""

    @pytest.mark.asyncio
    async def test_market_context_none(self) -> None:
        """market_context=None is handled without error."""
        layer = RefutationLayer()
        hyp = HypothesisConfig(name="h1", description="trend-following momentum")

        result = await layer.refute(hypotheses=[hyp], market_context=None)

        assert len(result.verdicts) == 1
        assert result.verdicts[0].falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_enabled_with_no_market_context(self) -> None:
        """Enabled layer with no market context produces 0 scores."""
        layer = RefutationLayer()
        hyp = HypothesisConfig(name="h1", description="mean-reversion")

        result = await layer.refute(hypotheses=[hyp])

        assert result.verdicts[0].falsification_score == 0.0

    @pytest.mark.asyncio
    async def test_all_scores_aggregated_in_summary(self) -> None:
        """Summary includes all scores for inspection."""
        layer = RefutationLayer()
        hyps = [
            HypothesisConfig(name="h1", description="trend-following momentum"),
            HypothesisConfig(name="h2", description="mean-reversion strategy"),
        ]

        result = await layer.refute(
            hypotheses=hyps,
            market_context={"detected_regime": "trending"},
        )

        # h1 matches (trending=trending) → 0.0, h2 mismatch (range-bound vs trending) → 0.5
        assert result.summary["max_score"] == 0.5
        assert result.summary["mean_score"] == 0.25
        assert result.summary["total_verdicts"] == 2
