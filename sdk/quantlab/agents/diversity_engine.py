"""DiversityEngine — parametric hypothesis variants with fingerprint dedup."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from quantlab.dsl.models import HypothesisConfig

logger = logging.getLogger(__name__)

__all__ = ["DiversityEngine"]


class DiversityEngine:
    """Generates parametric variants of hypotheses to widen the search.

    For each hypothesis with numeric parameters, produces up to
    ``max_variants_per_hypothesis`` variants by scaling numeric params by
    ``±diversification_factor``. Originals are always preserved. Output is
    deduplicated by fingerprint so identical inputs never multiply.

    Args:
        diversification_factor: Fractional perturbation in (0, 1).
        max_variants_per_hypothesis: Cap on variants per hypothesis.
    """

    def __init__(
        self,
        diversification_factor: float = 0.3,
        max_variants_per_hypothesis: int = 2,
    ) -> None:
        if not 0.0 < diversification_factor < 1.0:
            raise ValueError(
                "diversification_factor must be in (0, 1), "
                f"got {diversification_factor}"
            )
        if max_variants_per_hypothesis < 0:
            raise ValueError("max_variants_per_hypothesis must be >= 0")
        self.diversification_factor = diversification_factor
        self.max_variants_per_hypothesis = max_variants_per_hypothesis

    @staticmethod
    def fingerprint(hyp: HypothesisConfig) -> str:
        """Stable fingerprint of name + sorted parameters."""
        payload = f"{hyp.name}:{sorted((hyp.parameters or {}).items())}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def diversify(
        self, hypotheses: list[HypothesisConfig]
    ) -> list[HypothesisConfig]:
        """Return originals plus deduplicated parametric variants.

        Args:
            hypotheses: Input hypotheses (never mutated).

        Returns:
            Originals in order, followed by new variants.
        """
        result: list[HypothesisConfig] = []
        seen: set[str] = set()
        for hyp in hypotheses:
            fp = self.fingerprint(hyp)
            if fp not in seen:
                seen.add(fp)
                result.append(hyp)
            for variant in self._variants(hyp):
                vfp = self.fingerprint(variant)
                if vfp not in seen:
                    seen.add(vfp)
                    result.append(variant)
        return result

    def _variants(self, hyp: HypothesisConfig) -> list[HypothesisConfig]:
        """Build up to ``max_variants_per_hypothesis`` scaled copies."""
        params = hyp.parameters or {}
        numeric_keys = [
            k for k, v in params.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if not numeric_keys:
            return []
        variants: list[HypothesisConfig] = []
        for i in range(self.max_variants_per_hypothesis):
            # Alternate + / - around the base value: +f, -f, +f/2, -f/2, ...
            magnitude = self.diversification_factor / (1 + i // 2)
            sign = 1.0 if i % 2 == 0 else -1.0
            new_params: dict[str, Any] = dict(params)
            for key in numeric_keys:
                value = params[key]
                scaled = value * (1.0 + sign * magnitude)
                new_params[key] = (
                    int(round(scaled)) if isinstance(value, int) else round(scaled, 4)
                )
            variants.append(
                HypothesisConfig(
                    name=f"{hyp.name}__var{i + 1}",
                    description=hyp.description,
                    parameters=new_params,
                    expected_outcome=hyp.expected_outcome,
                    confidence=hyp.confidence,
                )
            )
        return variants
