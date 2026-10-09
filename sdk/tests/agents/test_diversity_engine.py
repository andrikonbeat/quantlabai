"""Tests for DiversityEngine (T9 task 3.1)."""

from __future__ import annotations

import pytest

from quantlab.dsl.models import HypothesisConfig


def _hyp(name: str = "mean_reversion_rsi_bb", **params) -> HypothesisConfig:
    return HypothesisConfig(
        name=name,
        description="RSI(14) < 30 mean reversion entry",
        parameters=params or {"rsi_period": 14, "rsi_oversold": 30},
        expected_outcome="Sharpe > 1.5",
        confidence=0.6,
    )


class TestDiversityEngine:
    def test_originals_preserved(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        hyps = [_hyp(), _hyp(name="donchian_breakout", donchian_period=20)]
        result = DiversityEngine().diversify(hyps)
        names = [h.name for h in result]
        assert "mean_reversion_rsi_bb" in names
        assert "donchian_breakout" in names

    def test_variants_perturb_numeric_params(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        result = DiversityEngine(diversification_factor=0.5).diversify([_hyp()])
        variants = [h for h in result if h.name.startswith("mean_reversion_rsi_bb__var")]
        assert len(variants) == 2
        values = sorted(v.parameters["rsi_period"] for v in variants)
        assert values == [7, 21]  # 14 * (1 - 0.5), 14 * (1 + 0.5)
        for v in variants:
            assert v.confidence == 0.6
            assert v.description == "RSI(14) < 30 mean reversion entry"

    def test_max_variants_respected(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        result = DiversityEngine(
            diversification_factor=0.5, max_variants_per_hypothesis=1
        ).diversify([_hyp()])
        variants = [h for h in result if "__var" in h.name]
        assert len(variants) == 1

    def test_non_numeric_params_yield_no_variants(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        hyp = _hyp(direction="LONG", mode="aggressive")
        assert DiversityEngine().diversify([hyp]) == [hyp]

    def test_dedup_by_fingerprint(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        engine = DiversityEngine(diversification_factor=0.5)
        doubled = engine.diversify([_hyp(), _hyp()])
        single = engine.diversify([_hyp()])
        assert [h.name for h in doubled] == [h.name for h in single]

    def test_empty_list(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        assert DiversityEngine().diversify([]) == []

    def test_fingerprint_stable(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        assert DiversityEngine.fingerprint(_hyp()) == DiversityEngine.fingerprint(_hyp())
        assert (
            DiversityEngine.fingerprint(_hyp())
            != DiversityEngine.fingerprint(_hyp(name="other"))
        )

    def test_factor_validation(self) -> None:
        from quantlab.agents.diversity_engine import DiversityEngine

        with pytest.raises(ValueError):
            DiversityEngine(diversification_factor=0)
        with pytest.raises(ValueError):
            DiversityEngine(diversification_factor=1.5)
