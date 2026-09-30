"""Frame model — serializable perception-layer aggregator.

Aggregates regime, regime_confidence, sentiment, technical_context,
risk, capital, timeframe, edge, instruments, and guardian_hints.
Serializable to JSON/YAML. Schema versioned.

Primed for SDD 5 guardian-orchestrator consumption.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Frame(BaseModel):
    """Market analysis frame aggregating perception-layer outputs."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    regime: str | None = None
    regime_confidence: float | None = None
    sentiment: float | None = None
    technical_context: Any | None = None
    risk: Any | None = None
    capital: Any | None = None
    timeframe: str | None = None
    edge: str | None = None
    instruments: list[str] | None = None
    guardian_hints: dict[str, Any] | None = None
    data_quality: str = "full"

    def to_json(self) -> str:
        """Serialize frame to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> Frame:
        """Deserialize frame from JSON string."""
        return cls.model_validate_json(raw)

    @classmethod
    def default_guardian_hints(cls) -> dict[str, dict[str, Any]]:
        """Return the canonical guardian_hints structure for SDD 5.

        Each hint contains:
        - ``detected``: whether the signal is active
        - ``confidence``: float in [0, 1]
        - ``recommended_action``: suggested action string or "none"
        """
        return {
            "regime_shift": {
                "detected": False,
                "confidence": 0.0,
                "recommended_action": "none",
            },
            "sentiment_shift": {
                "detected": False,
                "confidence": 0.0,
                "recommended_action": "none",
            },
            "volatility_expansion": {
                "detected": False,
                "confidence": 0.0,
                "recommended_action": "none",
            },
        }
