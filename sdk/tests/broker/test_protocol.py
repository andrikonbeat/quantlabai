"""Tests for broker adapter protocol."""

from __future__ import annotations

from quantlab.broker.protocol import BrokerAdapter


class TestBrokerAdapterProtocol:
    """Test the BrokerAdapter protocol contract."""

    def test_protocol_exists(self):
        """Test that BrokerAdapter protocol is defined."""
        assert hasattr(BrokerAdapter, "is_connected")
        assert hasattr(BrokerAdapter, "get_latency")
        assert hasattr(BrokerAdapter, "get_health_score")
        assert hasattr(BrokerAdapter, "get_recent_slippage")

    def test_concrete_class_can_implement(self):
        """Test that a concrete class can satisfy the protocol."""

        class DummyAdapter:
            def is_connected(self) -> bool:
                return True

            def get_latency(self) -> float:
                return 25.0

            def get_health_score(self) -> float:
                return 0.9

            def get_recent_slippage(self) -> float | None:
                return 1.5

        adapter = DummyAdapter()
        assert isinstance(adapter, BrokerAdapter)

    def test_missing_method_breaks_protocol(self):
        """Test that missing required methods break protocol conformance."""

        class BrokenAdapter:
            def is_connected(self) -> bool:
                return True

        adapter = BrokenAdapter()
        assert not isinstance(adapter, BrokerAdapter)
