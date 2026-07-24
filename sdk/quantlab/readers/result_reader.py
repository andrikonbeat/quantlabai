"""Result reader — live streaming of strategy equity from JCloud endpoints or simulation data."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from quantlab.readers.models import EquityPoint

logger = logging.getLogger(__name__)


class ResultReader:
    """Reads live strategy results from JCloud endpoints or injected data."""

    @staticmethod
    async def stream_live(
        campaign_id: str,
        equity_data: list[EquityPoint] | None = None,
        interval_seconds: float = 5.0,
        source: str = "jcloud",
        max_retries: int = 5,
        backoff_base: float = 30.0,
    ) -> AsyncGenerator[EquityPoint, None]:
        """Stream live equity data from a deployed strategy.

        When ``equity_data`` is provided, yields those points in order with
        optional ``interval_seconds`` delay between points. On a simulated
        ``ConnectionError``, retries with exponential backoff (max 5 retries,
        30s base) and continues from the last yielded point.

        Args:
            campaign_id: Identifier for the monitored strategy/campaign.
            equity_data: Optional replay buffer. When ``None``, yields a single
                sentinel point (replace with a real JCloud client in production).
            interval_seconds: Delay between points when replaying ``equity_data``.
            source: Endpoint identifier for logging.
            max_retries: Maximum reconnection attempts on ``ConnectionError``.
            backoff_base: Base delay in seconds for exponential backoff.

        Yields:
            ``EquityPoint`` objects in timestamp order.
        """
        if equity_data is None:
            logger.info(
                "ResultReader.stream_live: yielding sentinel for %s",
                campaign_id,
            )
            yield EquityPoint(timestamp=datetime.now(), equity=0.0)
            return

        retries = 0
        points = list(equity_data)
        idx = 0
        while idx < len(points):
            try:
                while idx < len(points):
                    yield points[idx]
                    idx += 1
                    if interval_seconds > 0 and idx < len(points):
                        await asyncio.sleep(interval_seconds)
                return
            except ConnectionError:
                retries += 1
                if retries > max_retries:
                    logger.error(
                        "ResultReader.stream_live: max retries exceeded for %s",
                        campaign_id,
                    )
                    raise
                delay = backoff_base * (2 ** (retries - 1))
                logger.warning(
                    "ResultReader.stream_live: connection error for %s, retrying "
                    "in %.1fs (%d/%d)",
                    campaign_id,
                    delay,
                    retries,
                    max_retries,
                )
                await asyncio.sleep(delay)
                # Backfill gap placeholder: production would fetch from JCloud
                # history endpoint. Simulation continues from last yielded index.
