"""TagCalibrator — adjusts hypothesis confidence based on historical tag performance."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from quantlab.dsl.models import HypothesisConfig

logger = logging.getLogger(__name__)


class TagCalibrator:
    """Calibrates hypothesis confidence using Knowledge Lake tag statistics.

    Computes per-tag Sharpe ratio percentiles and applies Bayesian smoothing
    for sparse tags. Confidence is clamped to [0.1, 1.0].
    """

    # ── Public API ──────────────────────────────────────────────────────────

    def calibrate(
        self,
        hypotheses: list[HypothesisConfig],
        query_results: list[dict[str, Any]],
    ) -> list[HypothesisConfig]:
        """Calibrate ``hypotheses`` confidence using ``query_results``.

        Args:
            hypotheses: Hypotheses to calibrate (mutated in place).
            query_results: Historical campaign dicts from Knowledge Lake.

        Returns:
            The same list of hypotheses with updated confidence scores.
        """
        if not hypotheses or not query_results:
            return hypotheses

        global_sharpes = self._extract_sharpes(query_results)
        if not global_sharpes:
            return hypotheses

        tag_stats = self._build_tag_stats(query_results)
        global_mean = sum(global_sharpes) / len(global_sharpes)

        for hyp in hypotheses:
            tags = getattr(hyp, "tags", None) or self._infer_tags(hyp)
            tag_sharpes = [
                tag_stats[tag]["avg_sharpe"] for tag in tags if tag in tag_stats
            ]

            if tag_sharpes:
                raw_mean = sum(tag_sharpes) / len(tag_sharpes)
                # Apply Bayesian smoothing for sparse tags
                smoothed = self._bayesian_smooth(
                    raw_mean, global_mean, tag_sharpes, tag_stats, tags
                )
                tag_mean = smoothed
            else:
                tag_mean = global_mean

            percentile = self._percentile_rank(tag_mean, global_sharpes)
            confidence = max(0.1, min(1.0, hyp.confidence * percentile))
            hyp.confidence = round(confidence, 2)

        return hypotheses

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_sharpes(query_results: list[dict[str, Any]]) -> list[float]:
        """Extract valid Sharpe ratios from query results."""
        sharpes: list[float] = []
        for r in query_results:
            sharpe = r.get("sharpe_ratio")
            if sharpe is not None:
                try:
                    sharpes.append(float(sharpe))
                except (TypeError, ValueError):
                    continue
        return sharpes

    @staticmethod
    def _build_tag_stats(
        query_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build per-tag statistics from query results."""
        stats: dict[str, dict[str, Any]] = {}
        for r in query_results:
            tags = r.get("tags") or []
            sharpe = r.get("sharpe_ratio")
            win_rate = r.get("win_rate")
            try:
                sharpe_f = float(sharpe) if sharpe is not None else None
            except (TypeError, ValueError):
                sharpe_f = None
            try:
                win_rate_f = float(win_rate) if win_rate is not None else None
            except (TypeError, ValueError):
                win_rate_f = None

            for tag in tags:
                if tag not in stats:
                    stats[tag] = {
                        "sharpes": [],
                        "win_rates": [],
                        "count": 0,
                    }
                if sharpe_f is not None:
                    stats[tag]["sharpes"].append(sharpe_f)
                if win_rate_f is not None:
                    stats[tag]["win_rates"].append(win_rate_f)
                stats[tag]["count"] += 1

        for tag, data in stats.items():
            data["avg_sharpe"] = (
                sum(data["sharpes"]) / len(data["sharpes"]) if data["sharpes"] else 0.0
            )
            data["avg_win_rate"] = (
                sum(data["win_rates"]) / len(data["win_rates"])
                if data["win_rates"]
                else 0.0
            )
            data["sample_count"] = data["count"]
            del data["sharpes"]
            del data["win_rates"]
            del data["count"]

        return stats

    @staticmethod
    def _infer_tags(hyp: HypothesisConfig) -> list[str]:
        """Infer tags from hypothesis name/description as a fallback."""
        tags: list[str] = []
        text = f"{hyp.name} {hyp.description}".lower()
        keywords = [
            "trend",
            "mean_reversion",
            "mean reversion",
            "breakout",
            "volatility",
            "momentum",
            "pullback",
            "support",
            "resistance",
            "divergence",
            "squeeze",
        ]
        for kw in keywords:
            if kw in text:
                tags.append(kw.replace(" ", "_"))
        return tags or ["default"]

    @staticmethod
    def _percentile_rank(value: float, distribution: list[float]) -> float:
        """Compute the percentile rank of ``value`` within ``distribution``.

        Returns a value in [0.1, 1.0].
        """
        if not distribution:
            return 1.0
        sorted_dist = sorted(distribution)
        count_less_equal = sum(1 for v in sorted_dist if v <= value)
        rank = count_less_equal / len(sorted_dist)
        return max(0.1, min(1.0, rank))

    @staticmethod
    def _bayesian_smooth(
        tag_mean: float,
        global_mean: float,
        tag_sharpes: list[float],
        tag_stats: dict[str, dict[str, Any]],
        tags: list[str],
    ) -> float:
        """Apply Bayesian smoothing for sparse tags.

        blended = (n * tag_mean + prior * global_mean) / (n + prior)
        where prior defaults to 5 (the sparse threshold).
        """
        total_samples = sum(tag_stats.get(tag, {}).get("sample_count", 0) for tag in tags)
        prior = 5.0
        if total_samples >= 5:
            return tag_mean
        return (total_samples * tag_mean + prior * global_mean) / (total_samples + prior)


__all__ = ["TagCalibrator"]
