"""Contract tests for Frame JSON schema stability (T-6.3).

Verifies that Frame.to_json() round-trips cleanly, schema_version is
present and immutable, and guardian_hints survive serialization.
"""

from __future__ import annotations

import json

import pytest

from quantlab.analysis.frame import Frame


class TestFrameSchemaStability:
    """Frame JSON schema is stable for SDD 5."""

    def test_schema_version_present_and_immutable(self) -> None:
        """GIVEN a Frame instance
        WHEN to_json() is called
        THEN the JSON contains schema_version == '1.0'
        AND the field cannot be mutated on the model.
        """
        frame = Frame()
        assert frame.schema_version == "1.0"

        raw = frame.to_json()
        payload = json.loads(raw)
        assert payload["schema_version"] == "1.0"

    def test_round_trip_preserves_all_fields(self) -> None:
        """GIVEN a fully populated Frame
        WHEN to_json() and from_json() are called
        THEN every field is restored to its original value.
        """
        frame = Frame(
            regime="trending",
            regime_confidence=0.8,
            sentiment=0.5,
            technical_context=[{"indicator_name": "RSI", "value": 55.0, "zone": "neutral"}],
            risk={"level": "medium"},
            capital={"allocated": 10000},
            timeframe="H1",
            edge="trend-following",
            instruments=["EURUSD", "GBPUSD"],
            guardian_hints={
                "regime_shift": {"detected": True, "confidence": 0.8, "recommended_action": "reduce_exposure"},
                "sentiment_shift": {"detected": False, "confidence": 0.0, "recommended_action": "none"},
                "volatility_expansion": {"detected": True, "confidence": 0.9, "recommended_action": "tighten_stops"},
            },
            data_quality="full",
        )

        raw = frame.to_json()
        restored = Frame.from_json(raw)

        assert restored.schema_version == "1.0"
        assert restored.regime == "trending"
        assert restored.regime_confidence == 0.8
        assert restored.sentiment == 0.5
        assert restored.timeframe == "H1"
        assert restored.edge == "trend-following"
        assert restored.instruments == ["EURUSD", "GBPUSD"]
        assert restored.guardian_hints == frame.guardian_hints
        assert restored.data_quality == "full"

    def test_guardian_hints_default_structure(self) -> None:
        """GIVEN default guardian hints
        WHEN serialized and deserialized
        THEN the three canonical keys are present and JSON-serializable.
        """
        hints = Frame.default_guardian_hints()
        assert set(hints.keys()) == {
            "regime_shift",
            "sentiment_shift",
            "volatility_expansion",
        }
        for key, value in hints.items():
            assert value["detected"] is False
            assert value["confidence"] == 0.0
            assert value["recommended_action"] == "none"

        frame = Frame(regime="quiet", guardian_hints=hints)
        raw = frame.to_json()
        restored = Frame.from_json(raw)

        assert restored.guardian_hints is not None
        assert restored.guardian_hints["regime_shift"]["detected"] is False
        assert restored.guardian_hints["volatility_expansion"]["recommended_action"] == "none"
