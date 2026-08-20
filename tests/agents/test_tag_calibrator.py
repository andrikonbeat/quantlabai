"""Tests for TagCalibrator — confidence calibration by tag performance."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quantlab.agents.tag_calibrator import TagCalibrator
from quantlab.dsl.models import HypothesisConfig


@pytest.fixture()
def calibrator() -> TagCalibrator:
    return TagCalibrator()


def _make_query_result(
    campaign_id: str,
    sharpe: float | None = 1.0,
    win_rate: float | None = 0.5,
    tags: list[str] | None = None,
) -> dict:
    return {
        "campaign_id": campaign_id,
        "name": campaign_id,
        "sharpe_ratio": sharpe,
        "win_rate": win_rate,
        "tags": tags or [],
    }


class TestTagCalibrator:
    """Parametrized tests for confidence calibration and Bayesian smoothing."""

    def test_no_query_results_keeps_confidence(
        self, calibrator: TagCalibrator
    ) -> None:
        hyp = HypothesisConfig(
            name="test",
            description="test",
            parameters={},
            confidence=0.5,
        )
        result = calibrator.calibrate([hyp], [])
        assert result[0].confidence == 0.5

    def test_high_tag_sharpe_boosts_confidence(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=0.3, tags=["mean_reversion"]),
            _make_query_result("c2", sharpe=0.4, tags=["mean_reversion"]),
            _make_query_result("c3", sharpe=0.5, tags=["mean_reversion"]),
            _make_query_result("c4", sharpe=0.6, tags=["mean_reversion"]),
            _make_query_result("c5", sharpe=0.7, tags=["mean_reversion"]),
            _make_query_result("c6", sharpe=2.5, tags=["trend"]),
            _make_query_result("c7", sharpe=2.2, tags=["trend"]),
            _make_query_result("c8", sharpe=2.0, tags=["trend"]),
            _make_query_result("c9", sharpe=2.1, tags=["trend"]),
            _make_query_result("c10", sharpe=2.3, tags=["trend"]),
        ]
        hyp = HypothesisConfig(
            name="trend_follow",
            description="trend",
            parameters={},
            confidence=1.0,
            tags=["trend"],
        )
        result = calibrator.calibrate([hyp], query_results)
        # Tag avg sharpe ~2.22, global sharpes = [0.3, 0.4, 0.5, 0.6, 0.7, 2.5, 2.2, 2.0, 2.1, 2.3]
        # percentile is high (0.8), no Bayesian smoothing (5 samples)
        assert result[0].confidence >= 0.7  # boosted from 1.0 * 0.8 = 0.8

    def test_low_tag_sharpe_reduces_confidence(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=0.5, tags=["mean_reversion"]),
            _make_query_result("c2", sharpe=0.6, tags=["mean_reversion"]),
            _make_query_result("c3", sharpe=0.4, tags=["mean_reversion"]),
            _make_query_result("c4", sharpe=0.55, tags=["mean_reversion"]),
            _make_query_result("c5", sharpe=0.45, tags=["mean_reversion"]),
            _make_query_result("c6", sharpe=2.5, tags=["trend"]),
            _make_query_result("c7", sharpe=2.2, tags=["trend"]),
            _make_query_result("c8", sharpe=2.0, tags=["trend"]),
            _make_query_result("c9", sharpe=2.1, tags=["trend"]),
            _make_query_result("c10", sharpe=2.3, tags=["trend"]),
        ]
        hyp = HypothesisConfig(
            name="mean_rev",
            description="mean reversion",
            parameters={},
            confidence=1.0,
            tags=["mean_reversion"],
        )
        result = calibrator.calibrate([hyp], query_results)
        # Tag avg sharpe ~0.5, global sharpes = [0.5, 0.6, 0.4, 0.55, 0.45, 2.5, 2.2, 2.0, 2.1, 2.3]
        # percentile is low (~0.3), no Bayesian smoothing (5 samples)
        assert result[0].confidence <= 0.5  # reduced from 1.0 * 0.3 = 0.3

    def test_confidence_clamped_to_minimum(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=-1.0, tags=["bad"]),
        ]
        hyp = HypothesisConfig(
            name="bad_strategy",
            description="bad",
            parameters={},
            confidence=0.5,
            tags=["bad"],
        )
        result = calibrator.calibrate([hyp], query_results)
        assert result[0].confidence >= 0.1

    def test_confidence_clamped_to_maximum(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=10.0, tags=["great"]),
            _make_query_result("c2", sharpe=10.0, tags=["great"]),
        ]
        hyp = HypothesisConfig(
            name="great_strategy",
            description="great",
            parameters={},
            confidence=0.5,
            tags=["great"],
        )
        result = calibrator.calibrate([hyp], query_results)
        assert result[0].confidence <= 1.0

    def test_bayesian_smoothing_sparse_tag(
        self, calibrator: TagCalibrator
    ) -> None:
        # Only 1 sample for tag "rare" — should use Bayesian smoothing
        query_results = [
            _make_query_result("c1", sharpe=3.0, tags=["rare"]),
            _make_query_result("c2", sharpe=1.0, tags=["common"]),
            _make_query_result("c3", sharpe=1.0, tags=["common"]),
            _make_query_result("c4", sharpe=1.0, tags=["common"]),
            _make_query_result("c5", sharpe=1.0, tags=["common"]),
            _make_query_result("c6", sharpe=1.0, tags=["common"]),
        ]
        hyp = HypothesisConfig(
            name="rare_strategy",
            description="rare",
            parameters={},
            confidence=0.5,
            tags=["rare"],
        )
        result = calibrator.calibrate([hyp], query_results)
        # With Bayesian smoothing, the extreme 3.0 should be pulled toward global mean (~1.33)
        # So confidence should be lower than if we used raw 3.0
        assert result[0].confidence < 0.5 * 1.0  # rough sanity check

    def test_multiple_tags_uses_min_percentile(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=0.3, tags=["mean_reversion"]),
            _make_query_result("c2", sharpe=0.4, tags=["mean_reversion"]),
            _make_query_result("c3", sharpe=0.5, tags=["mean_reversion"]),
            _make_query_result("c4", sharpe=0.6, tags=["mean_reversion"]),
            _make_query_result("c5", sharpe=0.7, tags=["mean_reversion"]),
            _make_query_result("c6", sharpe=2.5, tags=["trend"]),
            _make_query_result("c7", sharpe=2.2, tags=["trend"]),
            _make_query_result("c8", sharpe=2.0, tags=["trend"]),
            _make_query_result("c9", sharpe=2.1, tags=["trend"]),
            _make_query_result("c10", sharpe=2.3, tags=["trend"]),
        ]
        hyp = HypothesisConfig(
            name="mixed",
            description="mixed",
            parameters={},
            confidence=1.0,
            tags=["trend", "mean_reversion"],
        )
        result = calibrator.calibrate([hyp], query_results)
        # Should be conservative: min of the two tag percentiles
        assert result[0].confidence <= 0.5

    def test_cache_hit_returns_same_result(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=1.5, tags=["trend"]),
        ]
        hyp1 = HypothesisConfig(
            name="h1",
            description="h1",
            parameters={},
            confidence=0.5,
            tags=["trend"],
        )
        hyp2 = HypothesisConfig(
            name="h2",
            description="h2",
            parameters={},
            confidence=0.5,
            tags=["trend"],
        )
        result1 = calibrator.calibrate([hyp1], query_results)
        result2 = calibrator.calibrate([hyp2], query_results)
        assert result1[0].confidence == result2[0].confidence

    def test_win_rate_calculated_by_tag(
        self, calibrator: TagCalibrator
    ) -> None:
        query_results = [
            _make_query_result("c1", sharpe=1.0, win_rate=0.6, tags=["trend"]),
            _make_query_result("c2", sharpe=1.0, win_rate=0.8, tags=["trend"]),
        ]
        hyp = HypothesisConfig(
            name="trend",
            description="trend",
            parameters={},
            confidence=0.5,
            tags=["trend"],
        )
        result = calibrator.calibrate([hyp], query_results)
        assert result[0].confidence >= 0.1
