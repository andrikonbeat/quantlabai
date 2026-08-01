"""RefutationConfig — Pydantic model for RefutationLayer settings.

Controls whether the refutation layer is active and provides
configuration for strategy thresholds.
"""

from __future__ import annotations

from pydantic import BaseModel


class RefutationConfig(BaseModel):
    """Configuration for the RefutationLayer.

    Attributes:
        enabled: When ``False``, the layer returns empty verdicts without
            executing any strategy (RF-9).
    """

    enabled: bool = True

    model_config = {"extra": "forbid"}


__all__ = ["RefutationConfig"]
