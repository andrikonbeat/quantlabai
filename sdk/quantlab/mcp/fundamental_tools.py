"""MCP tools wrapping the Fundamental Data providers.

Each function is registered as an MCP tool via the ``register()`` function,
which the bridge calls at startup.  Tools delegate to ``YahooFinanceProvider``
and ``FredProvider``, serialise with ``model_dump(mode="json")``, and
return JSON strings.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from quantlab.mcp.models import ErrorCode, MCPError

if TYPE_CHECKING:
    from quantlab.mcp.bridge import QuantLabMCPServer

logger = logging.getLogger(__name__)


def register(srv: QuantLabMCPServer) -> None:
    """Register all fundamental-data MCP tools on the server."""

    mcp = srv.mcp

    @mcp.tool(
        name="get_fundamental_data",
        description="Fetch fundamental stock data (OHLCV + fundamentals) from Yahoo Finance.",
    )
    async def get_fundamental_data(
        ticker: str,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        """Get OHLCV prices and fundamental metrics for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
            start: Start date in ``YYYY-MM-DD`` format (optional).
            end: End date in ``YYYY-MM-DD`` format (optional).

        Returns:
            JSON string with price data and fundamentals.
        """
        try:
            provider = srv.yahoo_provider
            data = await provider.fetch(ticker, start=start, end=end)
            return json.dumps(data, default=str)
        except Exception as exc:
            logger.exception("get_fundamental_data failed for %s", ticker)
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Yahoo Finance fetch failed: {exc}",
                details={"ticker": ticker, "start": start, "end": end},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="get_financial_ratios",
        description="Fetch key financial ratios (P/E, P/B, ROE, ROA, Debt/Equity) from Yahoo Finance.",
    )
    async def get_financial_ratios(ticker: str) -> str:
        """Compute key financial ratios for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).

        Returns:
            JSON string with financial ratios.
        """
        try:
            provider = srv.yahoo_provider
            ratios = await provider.get_ratios(ticker)
            return json.dumps(ratios, default=str)
        except Exception as exc:
            logger.exception("get_financial_ratios failed for %s", ticker)
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Financial ratios fetch failed: {exc}",
                details={"ticker": ticker},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="get_market_data",
        description="Fetch economic indicator data from FRED (GDP, unemployment, CPI, etc.).",
    )
    async def get_market_data(series_id: str = "GDP") -> str:
        """Get a FRED economic time series.

        Common series IDs: ``GDP``, ``UNRATE`` (unemployment), ``CPIAUCSL`` (CPI).

        Args:
            series_id: FRED series identifier (default ``"GDP"``).

        Returns:
            JSON string with economic observations.
        """
        try:
            provider = srv.fred_provider
            data = await provider.fetch(series_id)
            return json.dumps(data, default=str)
        except Exception as exc:
            logger.exception("get_market_data failed for series %s", series_id)
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"FRED fetch failed: {exc}",
                details={"series_id": series_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)
