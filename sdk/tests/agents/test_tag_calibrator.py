"""Tests for TagCalibrator."""

from __future__ import annotations

from unittest.mock import patch

from quantlab.agents import tag_calibrator
from quantlab.agents.tag_calibrator import TagCalibrator
from quantlab.dsl.models import HypothesisConfig


class TestTagCalibratorCache:
    """TagCalibrator must cache results by frozenset(tags)."""

    def test_caches_by_tag_set_and_avoids_recomputation(self) -> None:
        calibrator = TagCalibrator()
        query_results = [
            {
                "campaign_id": "c1",
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "tags": ["mean_reversion"],
            },
            {
                "campaign_id": "c2",
                "sharpe_ratio": 0.8,
                "win_rate": 0.40,
                "tags": ["mean_reversion"],
            },
        ]
        hypotheses = [
            HypothesisConfig(name="h1", description="mean-reversion test", confidence=0.5, parameters={"tags": ["mean_reversion"]}),
        ]
        with patch.object(tag_calibrator, "_compute_tag_stats_helper", wraps=tag_calibrator._compute_tag_stats_helper) as mock:
            tag_calibrator._compute_tag_stats_helper.cache_clear()
            calibrator.calibrate(hypotheses, query_results)
            calibrator.calibrate(hypotheses, query_results)
            assert mock.call_count == 2 and mock.cache_info().hits == 1

    def test_different_tag_set_triggers_recomputation(self) -> None:
        calibrator = TagCalibrator()
        query_results = [
            {
                "campaign_id": "c1",
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "tags": ["mean_reversion"],
            },
        ]
        h1 = HypothesisConfig(
            name="h1", description="mean-reversion", parameters={"tags": ["mean_reversion"]}
        )
        h2 = HypothesisConfig(
            name="h2", description="trend", parameters={"tags": ["trend"]}
        )
        with patch.object(tag_calibrator, "_compute_tag_stats_helper", wraps=tag_calibrator._compute_tag_stats_helper) as mock:
            tag_calibrator._compute_tag_stats_helper.cache_clear()
            calibrator.calibrate([h1], query_results)
            calibrator.calibrate([h2], query_results)
            assert mock.call_count == 2
