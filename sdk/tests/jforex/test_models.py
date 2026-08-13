"""Tests for JForex live feed models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quantlab.jforex.models import OrderEvent


class TestOrderEvent:
    """Test the OrderEvent model."""

    def test_order_event_creation(self):
        """Test that OrderEvent can be created with required fields."""
        event = OrderEvent(
            order_id="ORD-001",
            timestamp=datetime(2026, 8, 12, 10, 30, 0, tzinfo=timezone.utc),
            side="BUY",
            lots=0.1,
            price=1.1234,
            status="FILLED",
        )

        assert event.order_id == "ORD-001"
        assert event.side == "BUY"
        assert event.lots == 0.1
        assert event.price == 1.1234
        assert event.status == "FILLED"

    def test_order_event_defaults(self):
        """Test that OrderEvent works with minimal valid data."""
        now = datetime.now(timezone.utc)
        event = OrderEvent(
            order_id="ORD-002",
            timestamp=now,
            side="SELL",
            lots=1.0,
            price=100.0,
            status="PENDING",
        )

        assert event.timestamp == now
        assert event.side == "SELL"

    def test_order_event_validation_negative_lots(self):
        """Test that negative lots raise validation error."""
        with pytest.raises(ValueError):
            OrderEvent(
                order_id="ORD-003",
                timestamp=datetime.now(timezone.utc),
                side="BUY",
                lots=-0.1,
                price=1.1234,
                status="FILLED",
            )

    def test_order_event_validation_negative_price(self):
        """Test that negative price raises validation error."""
        with pytest.raises(ValueError):
            OrderEvent(
                order_id="ORD-004",
                timestamp=datetime.now(timezone.utc),
                side="SELL",
                lots=0.1,
                price=-1.0,
                status="FILLED",
            )

    def test_order_event_model_dump(self):
        """Test that OrderEvent can be serialized."""
        event = OrderEvent(
            order_id="ORD-005",
            timestamp=datetime(2026, 8, 12, 10, 30, 0, tzinfo=timezone.utc),
            side="BUY",
            lots=0.5,
            price=1.5678,
            status="CANCELLED",
        )
        data = event.model_dump()

        assert data["order_id"] == "ORD-005"
        assert data["side"] == "BUY"
        assert data["lots"] == 0.5
        assert data["status"] == "CANCELLED"
