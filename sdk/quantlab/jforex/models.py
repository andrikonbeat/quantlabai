"""Pydantic models for JForex4 live feed data."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class OrderEvent(BaseModel):
    """A single order event from the JForex4 live feed.

    Attributes:
        order_id: Unique order identifier assigned by JForex4.
        timestamp: Time the order event occurred (UTC).
        side: Order direction — ``"BUY"`` or ``"SELL"``.
        lots: Order size in lots (must be positive).
        price: Execution price in account currency.
        status: Current order status — ``"FILLED"``, ``"PENDING"``,
            ``"CANCELLED"``, or ``"REJECTED"``.
    """

    order_id: str = Field(..., description="Unique order identifier")
    timestamp: datetime = Field(..., description="Order event timestamp (UTC)")
    side: Literal["BUY", "SELL"] = Field(..., description="Order direction")
    lots: float = Field(..., gt=0, description="Order size in lots")
    price: float = Field(..., gt=0, description="Execution price")
    status: Literal["FILLED", "PENDING", "CANCELLED", "REJECTED"] = Field(
        ..., description="Current order status"
    )
