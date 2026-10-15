"""Pytest fixtures for JForex Bridge process manager — isolated to avoid import-time pytest dependency."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from quantlab.jforex_bridge.process_manager import JForexProcessManager, JForexBridgeInstance


@ pytest_asyncio.fixture(scope="function")
async def jforex_instance() -> JForexBridgeInstance:
    """Function-scoped JForex Bridge instance fixture.

    Starts a fresh JForex Bridge for each test, stops it after.
    Skips if JFOREX_INTEGRATION=1 is not set.
    """
    if not os.environ.get("JFOREX_INTEGRATION"):
        pytest.skip("JFOREX_INTEGRATION=1 not set")

    manager = JForexProcessManager()
    inst = await manager.ensure_running()
    try:
        yield inst
    finally:
        await manager.stop()


@ pytest_asyncio.fixture(scope="session")
async def jforex_session() -> JForexBridgeInstance:
    """Session-scoped JForex Bridge instance fixture.

    Starts one JForex Bridge for the entire test session, stops at end.
    Skips if JFOREX_INTEGRATION=1 is not set.
    """
    if not os.environ.get("JFOREX_INTEGRATION"):
        pytest.skip("JFOREX_INTEGRATION=1 not set")

    manager = JForexProcessManager()
    inst = await manager.ensure_running(restart_on_crash=True)
    try:
        yield inst
    finally:
        pass