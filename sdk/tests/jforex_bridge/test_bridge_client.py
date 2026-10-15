"""Unit tests — JForex Bridge client (HTTP + WebSocket)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.asyncio


def _make_client(handler, **kwargs):
    """Build a JForexClient backed by an httpx MockTransport."""
    from quantlab.jforex_bridge.client import JForexClient

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://test")
    return JForexClient(base_url="http://localhost:8082", client=http, **kwargs)


def _ok(text: str) -> httpx.Response:
    return httpx.Response(200, text=text)


class TestErrorHierarchy:
    """Error types — structured exceptions with context."""

    def test_base_error_exists(self):
        """GIVEN the client module WHEN imported THEN JForexError is an Exception."""
        from quantlab.jforex_bridge.client import JForexError

        assert issubclass(JForexError, Exception)

    def test_command_error_carries_context(self):
        """GIVEN a failed command WHEN JForexCommandError raised THEN command+response stored."""
        from quantlab.jforex_bridge.client import JForexCommandError, JForexError

        err = JForexCommandError("-instrument list", "Error: not found")
        assert isinstance(err, JForexError)
        assert err.command == "-instrument list"
        assert err.response == "Error: not found"
        assert "-instrument list" in str(err)

    def test_timeout_not_ready_parse_errors(self):
        """GIVEN subclasses WHEN raised THEN all inherit JForexError."""
        from quantlab.jforex_bridge.client import (
            JForexError,
            JForexNotReady,
            JForexParseError,
            JForexTimeout,
        )

        assert issubclass(JForexTimeout, JForexError)
        assert issubclass(JForexNotReady, JForexError)
        assert issubclass(JForexParseError, JForexError)


class TestClientInit:
    """Client construction — defaults, normalization, injection."""

    def test_default_base_url(self):
        """GIVEN no args WHEN instantiated THEN points at the bridge port."""
        from quantlab.jforex_bridge.client import JForexClient

        client = JForexClient()
        assert client.base_url == "http://localhost:8082"

    def test_trailing_slash_stripped(self):
        """GIVEN base_url with trailing slash WHEN instantiated THEN normalized."""
        from quantlab.jforex_bridge.client import JForexClient

        assert JForexClient(base_url="http://x:8082/").base_url == "http://x:8082"

    def test_default_timeout_and_retries(self):
        """GIVEN no tuning args WHEN instantiated THEN sane defaults."""
        from quantlab.jforex_bridge.client import JForexClient

        client = JForexClient()
        assert client.timeout == 30.0
        assert client.max_retries == 3

    async def test_context_manager_closes_owned_client(self):
        """GIVEN async-with WHEN block exits THEN owned httpx client closed."""
        from quantlab.jforex_bridge.client import JForexClient

        async with JForexClient() as client:
            assert client.base_url == "http://localhost:8082"


class TestCommandEncoding:
    """Wire format — must match the bridge."""

    async def test_instruments_list_url_encoding(self):
        """GIVEN instruments.list WHEN sent THEN URL keeps '=' raw, spaces encoded."""
        from quantlab.jforex_bridge.client import JForexClient

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, json=[{"name": "EURUSD"}])

        client = _make_client(handler)
        await client.instruments.list()
        await client.aclose()
        assert len(seen) == 1
        assert seen[0].startswith("http://localhost:8082/api/v1/instruments")

    async def test_swaps_url_encoding(self):
        """GIVEN swaps.list WHEN sent THEN URL encoded."""
        from quantlab.jforex_bridge.client import JForexClient

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, json=[{"instrument": "EURUSD"}])

        client = _make_client(handler)
        await client.swaps.list()
        await client.aclose()
        assert len(seen) == 1
        assert seen[0].startswith("http://localhost:8082/api/v1/swaps")

    async def test_spreads_url_encoding(self):
        """GIVEN spreads.list WHEN sent THEN URL encoded."""
        from quantlab.jforex_bridge.client import JForexClient

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, json=[{"instrument": "EURUSD"}])

        client = _make_client(handler)
        await client.spreads.list()
        await client.aclose()
        assert len(seen) == 1
        assert seen[0].startswith("http://localhost:8082/api/v1/spreads")


class TestInstrumentNamespace:
    """``/api/v1/instruments`` endpoints."""

    async def test_instrument_list_returns_models(self):
        """GIVEN instrument list output WHEN parsed THEN models extracted."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[
                {"name": "EURUSD", "pipValue": 10.0, "pipScale": 4},
                {"name": "GBPUSD", "pipValue": 10.0, "pipScale": 4},
            ])

        from quantlab.jforex_bridge.client import JForexClient

        client = _make_client(handler)
        result = await client.instruments.list()
        await client.aclose()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "EURUSD"
        assert result[1]["name"] == "GBPUSD"

    async def test_instrument_get_single(self):
        """GIVEN single instrument WHEN requested THEN returns that instrument."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"name": "EURUSD", "pipValue": 10.0})

        from quantlab.jforex_bridge.client import JForexClient

        client = _make_client(handler)
        result = await client.instruments.get("EURUSD")
        await client.aclose()
        assert result["name"] == "EURUSD"
        assert result["pipValue"] == 10.0


class TestSwapNamespace:
    """``/api/v1/swaps`` endpoints."""

    async def test_swaps_list(self):
        """GIVEN swap list WHEN parsed THEN returns swap rates."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[
                {"instrument": "EURUSD", "longSwap": -0.5, "shortSwap": 0.2},
            ])

        from quantlab.jforex_bridge.client import JForexClient

        client = _make_client(handler)
        result = await client.swaps.list()
        await client.aclose()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["instrument"] == "EURUSD"