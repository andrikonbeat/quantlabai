"""Shared fixtures for the execution-substrate test suite (PR-2, REQ-26..28/42).

The mock SQX server is a process-wide singleton; fixtures here guarantee a
clean slate between tests (``MockSQXServer.reset()``) and unique campaign ids
so per-campaign exports never collide.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from quantlab.sqx.mock_sqx_server import MockSQXServer


@pytest.fixture(autouse=True)
def _clean_mock_server():
    """Reset the mock server singleton before every substrate test."""
    MockSQXServer.reset()
    yield
    MockSQXServer.reset()


@pytest.fixture
def campaign_id() -> str:
    """Unique campaign id per test — avoids mock-server state collisions."""
    return f"substrate-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_base_url() -> str:
    """Start the mock SQX server in normal mode and return its base URL."""
    import httpx

    base_url = "http://127.0.0.1:5050"
    try:
        resp = httpx.get(f"{base_url}/call?cmd=-h", timeout=2.0)
        if resp.status_code == 200:
            return base_url
    except Exception:
        pass

    MockSQXServer.instance(port=5050, mode="normal").start()
    return base_url
