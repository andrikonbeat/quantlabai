"""
JForex Bridge Python Client.

Async HTTP + WebSocket client for the JForex Bridge service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from quantlab.sqx.settings import jforex_bridge_base_url, jforex_bridge_ws_url, jforex_jnlp_url
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import websockets

logger = logging.getLogger(__name__)


@dataclass
class JForexConfig:
    """Configuration for JForex Bridge client."""
    base_url: str = "http://localhost:8082"
    ws_url: str = "ws://localhost:8082/ws"
    timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 0.5


class JForexError(Exception):
    """Base error for JForex Bridge client."""
    pass


class JForexCommandError(JForexError):
    """Command failed (HTTP error or JForex error)."""
    def __init__(self, command: str, response: str):
        self.command = command
        self.response = response
        super().__init__(f"JForex command failed [{command}]: {response[:200]}")


class JForexTimeout(JForexError):
    """Request timed out."""
    def __init__(self, command: str, timeout: float):
        self.command = command
        self.timeout = timeout
        super().__init__(f"JForex command timed out after {timeout:g}s: {command}")


class JForexNotReady(JForexError):
    """JForex bridge not ready."""
    def __init__(self, command: str):
        self.command = command
        super().__init__(f"JForex bridge not ready for: {command}")


class JForexParseError(JForexError):
    """Response could not be parsed."""
    def __init__(self, command: str, response: str, detail: str = ""):
        self.command = command
        self.response = response
        suffix = f" ({detail})" if detail else ""
        super().__init__(f"Cannot parse JForex response for [{command}]{suffix}")


class JForexClient:
    """
    Async client for JForex Bridge HTTP + WebSocket API.

    Usage:
        async with JForexClient() as client:
            instruments = await client.instruments.list()
            async for tick in client.ws.subscribe_ticks("EURUSD"):
                print(tick)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8082",
        ws_url: str = "ws://localhost:8082/ws",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client = client
        self._owns_client = client is None
        self._ws = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> JForexClient:
        await self._get_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ------------------------------------------------------------------------
    # Core HTTP send
    # ------------------------------------------------------------------------

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        logger.debug("JForex HTTP %s %s", method, url)

        attempts = 1 + max(0, self.max_retries)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                client = await self._get_client()
                resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    # Client error - don't retry
                    raise
                last_error = e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_error = e

            if attempt < attempts:
                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.info("JForex retry %d/%d after %s (%.2fs)", attempt, attempts - 1, type(last_error).__name__, delay)
                await asyncio.sleep(delay)

        assert last_error is not None
        if isinstance(last_error, httpx.TimeoutException):
            raise JForexTimeout("HTTP", self.timeout) from last_error
        raise last_error

    async def _get_json(self, path: str) -> dict:
        resp = await self._send("GET", path)
        return resp.json()

    async def _post_json(self, path: str, json_data: dict) -> dict:
        resp = await self._send("POST", path, json=json_data)
        return resp.json()

    # ------------------------------------------------------------------------
    # Namespaces
    # ------------------------------------------------------------------------

    @property
    def instruments(self) -> "InstrumentNamespace":
        if not hasattr(self, "_instruments"):
            self._instruments = InstrumentNamespace(self)
        return self._instruments

    @property
    def swaps(self) -> "SwapNamespace":
        if not hasattr(self, "_swaps"):
            self._swaps = SwapNamespace(self)
        return self._swaps

    @property
    def spreads(self) -> "SpreadNamespace":
        if not hasattr(self, "_spreads"):
            self._spreads = SpreadNamespace(self)
        return self._spreads

    @property
    def sessions(self) -> "SessionNamespace":
        if not hasattr(self, "_sessions"):
            self._sessions = SessionNamespace(self)
        return self._sessions

    @property
    def account(self) -> "AccountNamespace":
        if not hasattr(self, "_account"):
            self._account = AccountNamespace(self)
        return self._account

    @property
    def ws(self) -> "WebSocketClient":
        if not hasattr(self, "_ws_client"):
            self._ws_client = WebSocketClient(self)
        return self._ws_client

    # Utility commands
    async def health(self) -> dict:
        """Health check."""
        return await self._get_json("/api/v1/health")

    async def shutdown(self) -> dict:
        """Graceful shutdown."""
        return await self._post_json("/api/v1/health/shutdown", {})


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

class InstrumentNamespace:
    """``/api/v1/instruments`` - instrument specifications."""

    def __init__(self, client: JForexClient) -> None:
        self._c = client

    async def list(self) -> List[Dict]:
        return await self._c._get_json("/api/v1/instruments")

    async def get(self, name: str) -> Dict:
        return await self._c._get_json(f"/api/v1/instruments/{name}")


class SwapNamespace:
    """``/api/v1/swaps`` - swap rates."""

    def __init__(self, client: JForexClient) -> None:
        self._c = client

    async def list(self) -> List[Dict]:
        return await self._c._get_json("/api/v1/swaps")

    async def get(self, instrument: str) -> Dict:
        return await self._c._get_json(f"/api/v1/swaps/{instrument}")


class SpreadNamespace:
    """``/api/v1/spreads`` - real-time spreads."""

    def __init__(self, client: JForexClient) -> None:
        self._c = client

    async def list(self) -> List[Dict]:
        return await self._c._get_json("/api/v1/spreads")

    async def get(self, instrument: str) -> Dict:
        return await self._c._get_json(f"/api/v1/spreads/{instrument}")


class SessionNamespace:
    """``/api/v1/sessions`` - trading sessions."""

    def __init__(self, client: JForexClient) -> None:
        self._c = client

    async def list(self) -> List[Dict]:
        return await self._c._get_json("/api/v1/sessions")

    async def get(self, instrument: str) -> Dict:
        return await self._c._get_json(f"/api/v1/sessions/{instrument}")


class AccountNamespace:
    """``/api/v1/account`` - account info."""

    def __init__(self, client: JForexClient) -> None:
        self._c = client

    async def get(self) -> Dict:
        return await self._c._get_json("/api/v1/account")


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

class WebSocketClient:
    """WebSocket client for real-time market data."""

    def __init__(self, http_client: JForexClient) -> None:
        self.http_client = http_client
        self._ws = None
        self._connected = False
        self._callbacks: Dict[str, List[callable]] = {}

    async def connect(self) -> None:
        """Connect to WebSocket."""
        if self._connected:
            return

        try:
            self._ws = await websockets.connect(self.http_client.ws_url)
            self._connected = True
            logger.info("JForex WebSocket connected")
            # Start listener task
            asyncio.create_task(self._listen())
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            raise

    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        if self._ws:
            await self._ws.close()
            self._connected = False

    async def _listen(self) -> None:
        """Listen for incoming messages."""
        try:
            async for message in self._ws:
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            self._connected = False
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error("WebSocket error: %s", e)
            self._connected = False

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            # Route to appropriate callback based on destination
            # For simplicity, broadcast to all registered callbacks
            for callbacks in self._callbacks.values():
                for cb in callbacks:
                    try:
                        await cb(data) if asyncio.iscoroutinefunction(cb) else cb(data)
                    except Exception as e:
                        logger.error("Callback error: %s", e)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from WebSocket: %s", message[:100])

    def on_ticks(self, callback: callable) -> None:
        """Register callback for tick data."""
        self._callbacks.setdefault("ticks", []).append(callback)

    def on_bars(self, callback: callable) -> None:
        """Register callback for bar data."""
        self._callbacks.setdefault("bars", []).append(callback)

    def on_account(self, callback: callable) -> None:
        """Register callback for account updates."""
        self._callbacks.setdefault("account", []).append(callback)

    async def subscribe_ticks(self, instrument: str) -> None:
        """Subscribe to tick data for an instrument."""
        if self._ws:
            await self._ws.send(json.dumps({"destination": "/app/subscribe/ticks", "body": instrument}))

    async def unsubscribe_ticks(self, instrument: str) -> None:
        """Unsubscribe from tick data."""
        if self._ws:
            await self._ws.send(json.dumps({"destination": "/app/unsubscribe/ticks", "body": instrument}))

    async def subscribe_bars(self, instrument: str, period: str, side: str = "ASK") -> None:
        """Subscribe to bar data."""
        if self._ws:
            payload = f"{instrument},{period},{side}"
            await self._ws.send(json.dumps({"destination": "/app/subscribe/bars", "body": payload}))

    async def subscribe_account(self) -> None:
        """Subscribe to account updates."""
        if self._ws:
            await self._ws.send(json.dumps({"destination": "/app/subscribe/account", "body": ""}))

    async def __aenter__(self) -> "WebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()