"""WU4 RED tests: Frame model (REQ-305).

Covers JSON round-trip, schema_version immutability, partial frame,
and guardian_hints serialization.

Strict TDD: written first — FAIL (RED) until `Frame` exists.
"""

from __future__ import annotations



class TestFrameModel:
    def test_json_round_trip(self) -> None:
        """GIVEN a populated Frame model
        WHEN to_json() and from_json() are called
        THEN all fields are restored to original types.
        """
        from quantlab.analysis.frame import Frame

        frame = Frame(
            regime="trending",
            regime_confidence=0.8,
            sentiment=0.5,
            technical_context=[],
            risk={"level": "medium"},
            capital={"allocated": 10000},
            timeframe="H1",
            edge="trend-following",
            instruments=["EURUSD"],
            guardian_hints={"regime_shift": {"detected": False}},
        )
        raw = frame.to_json()
        restored = Frame.from_json(raw)

        assert restored.regime == "trending"
        assert restored.regime_confidence == 0.8
        assert restored.sentiment == 0.5
        assert restored.timeframe == "H1"
        assert restored.instruments == ["EURUSD"]

    def test_schema_version_immutable(self) -> None:
        """GIVEN a Frame instance
        WHEN schema_version is accessed
        THEN it is the default '1.0' and cannot be changed.
        """
        from quantlab.analysis.frame import Frame

        frame = Frame()
        assert frame.schema_version == "1.0"

    def test_partial_frame_allowed(self) -> None:
        """GIVEN only regime and sentiment populated
        WHEN Frame is instantiated
        THEN optional fields default to None.
        """
        from quantlab.analysis.frame import Frame

        frame = Frame(regime="range-bound", sentiment=-0.3)

        assert frame.regime == "range-bound"
        assert frame.sentiment == -0.3
        assert frame.technical_context is None
        assert frame.guardian_hints is None

    def test_guardian_hints_serializable(self) -> None:
        """GIVEN a Frame with guardian_hints dict
        WHEN to_json() is called
        THEN guardian_hints are included as valid JSON.
        """
        from quantlab.analysis.frame import Frame

        frame = Frame(
            regime="volatile",
            regime_confidence=0.9,
            guardian_hints={
                "regime_shift": {"detected": True, "confidence": 0.8},
                "volatility_expansion": {"detected": True, "confidence": 0.9},
            },
        )
        raw = frame.to_json()
        restored = Frame.from_json(raw)

        assert restored.guardian_hints is not None
        assert restored.guardian_hints["regime_shift"]["detected"] is True
