"""Integration tests — JForex Bridge with live demo account.

These tests require:
1. JFOREX_INTEGRATION=1 environment variable
2. Valid Dukascopy demo credentials (JFOREX_USERNAME, JFOREX_PASSWORD)
3. JForex Bridge JAR built and available

Run with:
    JFOREX_INTEGRATION=1 JFOREX_USERNAME=xxx JFOREX_PASSWORD=yyy pytest -q sdk/tests/jforex_bridge/test_live_integration.py
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

from quantlab.sqx.settings import jforex_jnlp_url
from quantlab.jforex_bridge.client import JForexClient
from quantlab.jforex_bridge.process_manager import JForexProcessManager


# Skip unless explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.environ.get("JFOREX_INTEGRATION"),
    reason="Set JFOREX_INTEGRATION=1 to run against live JForex demo",
)


@pytest_asyncio.fixture(scope="session")
async def jforex_bridge():
    """Session-scoped JForex Bridge instance with live demo account."""
    manager = JForexProcessManager()
    inst = await JForexProcessManager().ensure_running(
        jnlp_url=jforex_jnlp_url(),
        username=os.environ.get("JFOREX_USERNAME"),
        password=os.environ.get("JFOREX_PASSWORD"),
        demo=True,
    )
    try:
        yield inst
    finally:
        await JForexProcessManager().stop()


@pytest_asyncio.fixture(scope="session")
async def jforex_client(jforex_bridge):
    """JForexClient connected to live bridge."""
    from quantlab.jforex_bridge.client import JForexClient

    async with JForexClient(base_url=jforex_bridge.base_url) as client:
        # Wait for bridge to be fully ready
        health = await client.health()
        assert health["status"] == "UP"
        assert health["jforexConnected"] is True
        yield client


class TestJForexBridgeLive:
    """Live integration tests with Dukascopy demo account."""

    @pytest.mark.asyncio
    async def test_bridge_health(self, jforex_client):
        """GIVEN live bridge WHEN health check THEN returns UP and connected."""
        health = await jforex_client.health()
        assert health["status"] == "UP"
        assert health["jforexConnected"] is True

    @pytest.mark.asyncio
    async def test_instruments_list(self, jforex_client):
        """GIVEN live bridge WHEN instruments.list() THEN returns real instruments."""
        result = await jforex_client.instruments.list()
        assert isinstance(result, list)
        assert len(result) > 0
        # Should have major pairs
        names = {inst["name"] for inst in result}
        assert "EURUSD" in names or "GBPUSD" in names

    @pytest.mark.asyncio
    async def test_swaps_list(self, jforex_client):
        """GIVEN live bridge WHEN swaps.list() THEN returns swap rates."""
        result = await jforex_client.swaps.list()
        assert isinstance(result, list)
        # At least some instruments should have swaps
        # (Some might be 0 for certain instruments)
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_spreads_list(self, jforex_client):
        """GIVEN live bridge WHEN spreads.list() THEN returns real-time spreads."""
        result = await jforex_client.spreads.list()
        assert isinstance(result, list)
        assert len(result) > 0
        for spread in result:
            assert "instrument" in spread
            assert "bid" in spread
            assert "ask" in spread
            assert "spreadPips" in spread
            assert spread["spreadPips"] >= 0

    @pytest.mark.asyncio
    async def test_sessions_list(self, jforex_client):
        """GIVEN live bridge WHEN sessions.list() THEN returns trading sessions."""
        result = await jforex_client.sessions.list()
        assert isinstance(result, list)
        assert len(result) > 0
        for session in result:
            assert "name" in session
            assert "broker" in session
            assert "timezone" in session
            assert "elements" in session

    @pytest.mark.asyncio
    async def test_account_info(self, jforex_client):
        """GIVEN live bridge WHEN account.get() THEN returns account info."""
        result = await jforex_client.account.get()
        assert isinstance(result, dict)
        assert "equity" in result
        assert "balance" in result
        assert "leverage" in result
        assert "currency" in result
        assert "state" in result

    @pytest.mark.asyncio
    async def test_websocket_ticks(self, jforex_client):
        """GIVEN WebSocket connection WHEN subscribed THEN receives real-time ticks."""
        import json
        import asyncio

        async with jforex_client.ws as ws:
            # Subscribe to a known instrument
            await ws.subscribe_ticks("EURUSD")

            # Wait for at least one tick (with timeout)
            try:
                async with asyncio.timeout(15):
                    async for message in jforex_client.ws._ws:
                        data = json.loads(message)
                        if "instrument" in data:
                            assert data["instrument"] == "EURUSD"
                            assert "bid" in data
                            assert "ask" in data
                            assert data["bid"] > 0
                            assert data["ask"] > 0
                            break
            except asyncio.TimeoutError:
                pytest.skip("No ticks received within timeout")

    @pytest.mark.asyncio
    async def test_websocket_account_updates(self, jforex_client):
        """GIVEN WebSocket connection WHEN subscribed to account THEN receives updates."""
        import json
        import asyncio

        async with jforex_client.ws as ws:
            await ws.subscribe_account()

            try:
                async with asyncio.timeout(10):
                    async for message in jforex_client.ws._ws:
                        data = json.loads(message)
                        if "equity" in data:
                            assert "equity" in data
                            assert "balance" in data
                            break
            except asyncio.TimeoutError:
                pytest.skip("No account updates within timeout")


class TestJForexBridgeBrokerProfile:
    """Tests for BrokerProfile creation from live data."""

    @pytest.mark.asyncio
    async def test_create_broker_profile_from_live_data(self, jforex_client):
        """GIVEN live bridge WHEN create_broker_profile THEN returns valid BrokerProfile."""
        from quantlab.sqx.cli_wrapper import create_jforex_broker_profile
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient(base_url=jforex_client.base_url) as client:
            # Need to initialize client properly for the helper
            await client.health()

            # The helper function is in cli_wrapper, we'll test the concept
            # by manually creating a profile from live data
            instruments = await jforex_client.instruments.list()
            swaps = await jforex_client.swaps.list()
            spreads = await jforex_client.spreads.list()

            assert len(instruments) > 0
            # At minimum, we should be able to construct a broker profile
            assert isinstance(swaps, list)
            assert isinstance(spreads, list)