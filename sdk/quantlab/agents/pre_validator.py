"""PreValidator — structural hypothesis checks with a validation policy.

Complements ``EconomicSenseValidator`` (which owns numeric ranges):
indicator-existence, semantic coherence and direction consistency.
Never raises except under ``validation_policy="strict"``; range checks
delegate to the economic validator so the math exists exactly once.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from quantlab.agents.economic_sense.validator import EconomicSenseValidator
from quantlab.dsl.models import HypothesisConfig

try:
    from quantlab.knowledge.sqx_doc_provider import SQXDocProvider
except ImportError:  # pragma: no cover
    SQXDocProvider = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

VALID_POLICIES = ("strict", "lenient", "off")

_DIRECTIONS = ("LONG", "SHORT", "BOTH")

# Generic (non-indicator) vocabulary: parameter words, strategy words and
# direction words that must never trigger "unknown indicator" warnings.
_GENERIC_WORDS = frozenset(
    """
    period length deviation oversold overbought fast slow signal multiplier
    threshold direction min max trades drawdown cycles ratio oot wf regime
    adaptive validation robustness mean reversion breakout trend momentum
    volatility squeeze expansion dual cross above below touch middle upper
    lower band bands filter confirmation entry exit take profit stop atr
    long short both buy sell ranging trending market params default general
    other robust walkforward oos issample
    at the a an and or in on of to for with is are was were be been by
    from as it its this that these those when than then into out over under
    go goes so such no not only also which what how all any each every can
    will would should could may might must do does did have has had if else
    while where there their they them we you he she your our my his her
    about between through during before after above below up down off again
    further once here more most other some own same too very just now
    """.split()
)

# Fallback indicator vocabulary when the SQX KB is unavailable.
_FALLBACK_INDICATORS = frozenset(
    """
    rsi bb bollinger sma ema atr macd donchian adx dmi obv vwap stoch
    stochastic cci williams keltner ichimoku sar parabolic momentum roc
    trix tema dema wma hma supertrend chandelier envelope zscore
    """.split()
)

__all__ = ["PreValidator", "VALID_POLICIES"]


class PreValidator:
    """Structural pre-validation with a configurable policy.

    Args:
        validation_policy: ``"strict"`` raises ``ValueError`` on any
            warning; ``"lenient"`` (default) returns warnings;
            ``"off"`` skips all checks.
    """

    def __init__(self, validation_policy: str = "lenient") -> None:
        if validation_policy not in VALID_POLICIES:
            raise ValueError(
                f"validation_policy must be one of {VALID_POLICIES}, "
                f"got {validation_policy!r}"
            )
        self.validation_policy = validation_policy
        self._economic = EconomicSenseValidator()

    def validate(self, hyp: HypothesisConfig) -> list[str]:
        """Check a hypothesis structurally; see class docstring for policy."""
        if self.validation_policy == "off":
            return []
        warnings: list[str] = []
        warnings.extend(self._check_indicators(hyp))
        warnings.extend(self._check_ranges(hyp))
        warnings.extend(self._check_coherence(hyp))
        if self.validation_policy == "strict" and warnings:
            raise ValueError("; ".join(warnings))
        return warnings

    # ── Checks ──────────────────────────────────────────────────────────

    def _known_indicators(self) -> frozenset[str]:
        """KB indicator names, falling back to the static set."""
        try:
            if SQXDocProvider is None:
                return _FALLBACK_INDICATORS
            provider = SQXDocProvider()
            known = getattr(provider, "_KNOWN_INDICATORS", None)
            if isinstance(known, dict) and known:
                return frozenset(str(k).lower() for k in known) | _FALLBACK_INDICATORS
        except Exception as exc:
            logger.debug("Indicator KB unavailable, using fallback: %s", exc)
        return _FALLBACK_INDICATORS

    def _check_indicators(self, hyp: HypothesisConfig) -> list[str]:
        """Warn on tokens that look like unknown indicator references."""
        known = self._known_indicators()
        tokens: set[str] = set()
        for text in (hyp.name or "", hyp.description or ""):
            tokens.update(re.findall(r"[a-z0-9]+", text.lower()))
        for key in (hyp.parameters or {}).keys():
            first = str(key).lower().split("_")[0]
            if first:
                tokens.add(first)
        warnings = []
        for token in sorted(tokens):
            if token in known or token in _GENERIC_WORDS or token.isdigit():
                continue
            warnings.append(
                f"Unknown indicator reference {token!r} in hypothesis "
                f"{hyp.name!r} (not in SQX KB, treating as informational)"
            )
        return warnings

    def _check_ranges(self, hyp: HypothesisConfig) -> list[str]:
        """Delegate numeric-range checks to the economic validator."""
        try:
            return list(self._economic.validate(hyp))
        except Exception as exc:
            logger.debug("Economic validator failed: %s", exc)
            return []

    def _check_coherence(self, hyp: HypothesisConfig) -> list[str]:
        """Name/description/direction consistency checks."""
        warnings = []
        if not (hyp.name or "").strip():
            warnings.append("Hypothesis name is empty")
        if not (hyp.description or "").strip():
            warnings.append(
                f"Hypothesis {hyp.name!r} has an empty description"
            )
        direction = (hyp.parameters or {}).get("direction")
        if direction is not None:
            upper = str(direction).upper()
            if upper not in _DIRECTIONS:
                warnings.append(
                    f"Invalid direction {direction!r} in hypothesis "
                    f"{hyp.name!r} (expected one of {list(_DIRECTIONS)})"
                )
            else:
                desc = (hyp.description or "").lower()
                if upper == "LONG" and ("short" in desc or "sell" in desc):
                    warnings.append(
                        f"Direction LONG contradicts short/sell language in "
                        f"hypothesis {hyp.name!r} description"
                    )
                elif upper == "SHORT" and ("long" in desc or "buy" in desc):
                    warnings.append(
                        f"Direction SHORT contradicts long/buy language in "
                        f"hypothesis {hyp.name!r} description"
                    )
        return warnings
