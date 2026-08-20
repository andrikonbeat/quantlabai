"""EconomicSenseValidator — non-blocking range and coherence checks for indicator parameters."""

from __future__ import annotations

import logging
from typing import Any

from quantlab.dsl.models import HypothesisConfig

logger = logging.getLogger(__name__)


class EconomicSenseValidator:
    """Validates indicator parameters for economic sense.

    Performs range checks and cross-parameter coherence checks.
    Never raises — returns a list of warning strings.
    """

    # ── Human-readable labels for parameter names ──────────────────────────

    _PARAM_LABELS: dict[str, str] = {
        "rsi_period": "RSI period",
        "bb_deviation": "BB deviation",
        "bb_period": "BB period",
        "sma_period": "SMA period",
        "ema_period": "EMA period",
        "atr_period": "ATR period",
        "macd_fast_period": "MACD fast period",
        "macd_slow_period": "MACD slow period",
        "macd_signal_period": "MACD signal period",
    }

    # ── Range tables ────────────────────────────────────────────────────────

    _RANGE_RULES: dict[str, tuple[float, float]] = {
        "rsi_period": (2.0, 200.0),
        "bb_deviation": (0.1, 5.0),
        "sma_period": (2.0, 500.0),
        "ema_period": (2.0, 500.0),
        "atr_period": (2.0, 200.0),
        "macd_fast_period": (2.0, 200.0),
        "macd_slow_period": (2.0, 200.0),
        "macd_signal_period": (2.0, 100.0),
    }

    # ── Public API ──────────────────────────────────────────────────────────

    def validate(self, hypothesis: HypothesisConfig) -> list[str]:
        """Validate ``hypothesis`` parameters for economic sense.

        Args:
            hypothesis: The hypothesis to validate.

        Returns:
            List of warning strings. Never raises.
        """
        warnings: list[str] = []
        params = hypothesis.parameters or {}

        # Range checks
        for param_name, (low, high) in self._RANGE_RULES.items():
            value = params.get(param_name)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric < low or numeric > high:
                warnings.append(
                    f"{self._format_param_name(param_name)} {numeric} is out of range [{low}, {high}]"
                )

        # Cross-parameter coherence
        warnings.extend(self._check_bb_sma_coherence(params))
        warnings.extend(self._check_macd_coherence(params))

        return warnings

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _format_param_name(name: str) -> str:
        """Return a human-readable label for a parameter name."""
        return EconomicSenseValidator._PARAM_LABELS.get(name, name.replace("_", " ").title())

    def _check_bb_sma_coherence(self, params: dict[str, Any]) -> list[str]:
        """Warn if BB period vs SMA period ratio is outside [0.33, 3.0]."""
        bb_period = params.get("bb_period")
        sma_period = params.get("sma_period")

        if bb_period is None or sma_period is None:
            return []

        try:
            bb = float(bb_period)
            sma = float(sma_period)
        except (TypeError, ValueError):
            return []

        if sma <= 0:
            return []

        ratio = bb / sma
        if ratio > 3.0 or ratio < 0.33:
            return [
                f"BB/SMA period ratio {ratio:.2f} is outside recommended range [0.33, 3.0]"
            ]
        return []

    def _check_macd_coherence(self, params: dict[str, Any]) -> list[str]:
        """Warn if MACD fast period >= slow period."""
        fast = params.get("macd_fast_period")
        slow = params.get("macd_slow_period")

        if fast is None or slow is None:
            return []

        try:
            fast_f = float(fast)
            slow_f = float(slow)
        except (TypeError, ValueError):
            return []

        if fast_f >= slow_f:
            return [
                f"MACD fast period {fast_f} should be less than slow period {slow_f}"
            ]
        return []


__all__ = ["EconomicSenseValidator"]
