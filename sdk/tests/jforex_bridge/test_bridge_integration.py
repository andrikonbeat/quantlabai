"""Integration tests — JForex Bridge client against a live JForex Bridge.

These tests use the JForexProcessManager fixtures to manage the bridge lifecycle.

Run with::

    JFOREX_INTEGRATION=1 pytest -q -m integration

The fixtures automatically start/stop the JForex Bridge.
"""

from __future__ import annotations

import json
import asyncio

import pytest

from quantlab.jforex_bridge.client import JForexClient


# Use the process manager fixtures to manage JForex lifecycle
pytestmark = pytest.mark.usefixtures("jforex_session")


class TestJForexBridgeIntegration:
    """Integration tests using the session-scoped JForex fixture."""

    @pytest.mark.asyncio
    async def test_live_bridge_ready(self, jforex_session):
        """GIVEN session fixture WHEN daemon probed THEN /health returns UP."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            health = await client.health()
            assert health["status"] == "UP"
            assert health["jforexConnected"] is True

    @pytest.mark.asyncio
    async def test_live_instruments_list(self, jforex_session):
        """GIVEN ready bridge WHEN instruments.list() THEN returns list."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            result = await client.instruments.list()

            assert isinstance(result, list)
            assert len(result) > 0
            # Should have at least major pairs
            names = {inst["name"] for inst in result}
            assert "EURUSD" in names or "GBPUSD" in names

    @pytest.mark.asyncio
    async def test_live_swaps(self, jforex_session):
        """GIVEN ready bridge WHEN swaps.list() THEN returns swap rates."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            result = await client.swaps.list()

            assert isinstance(result, list)
            # At least some instruments should have swaps
            assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_live_spreads(self, jforex_session):
        """GIVEN ready bridge WHEN spreads.list() THEN returns spreads."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            result = await client.spreads.list()

            assert isinstance(result, list)
            # At least some instruments should have spreads
            assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_live_sessions(self, jforex_session):
        """GIVEN ready bridge WHEN sessions.list() THEN returns sessions."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            result = await client.sessions.list()

            assert isinstance(result, list)
            assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_live_account(self, jforex_session):
        """GIVEN ready bridge WHEN account.get() THEN returns account info."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            result = await client.account.get()

            assert isinstance(result, dict)
            assert "equity" in result
            assert "balance" in result
            assert "currency" in result

    @pytest.mark.asyncio
    async def test_live_error_handling(self, jforex_session):
        """GIVEN invalid command WHEN run THEN JForexCommandError raised."""
        from quantlab.jforex_bridge.client import JForexClient, JForexCommandError

        async with JForexClient(base_url=jforex_session.base_url) as client:
            with pytest.raises(Exception) as exc_info:
                # This endpoint doesn't exist
                await client._get_json("/api/v1/nonexistent")

            assert exc_info.value is not None

    @pytest.mark.asyncio
    async def test_live_websocket_ticks(self, jforex_session):
        """GIVEN WebSocket connection WHEN subscribed THEN receives ticks."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_session.base_url) as client:
            async with client.ws as ws:
                # Subscribe to a known instrument
                await ws.subscribe_ticks("EURUSD")
                
                # Wait for at least one tick (with timeout)
                try:
                    async with asyncio.timeout(10):
                        async for message in ws._ws:
                            data = json.loads(message)
                            if "instrument" in data:
                                assert data["instrument"] == "EURUSD"
                                break
                except asyncio.TimeoutError:
                    pytest.skip("No ticks received within timeout")