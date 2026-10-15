"""Pytest fixtures for SQX process manager — isolated to avoid import-time pytest dependency.

Usage:
    import pytest
    from quantlab.sqx.process_manager import SQXProcessManager
    from quantlab.tests.sqx.fixtures import sqx_instance, sqx_session  # noqa: F401
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from quantlab.sqx.process_manager import SQXInstance, SQXProcessManager


@ pytest_asyncio.fixture(scope="function")
async def sqx_instance() -> SQXInstance:
    """Function-scoped SQX instance fixture.

    Starts a fresh SQX daemon for each test, stops it after.
    Skips if SQX_INTEGRATION=1 is not set.
    """
    if not os.environ.get("SQX_INTEGRATION"):
        pytest.skip("SQX_INTEGRATION=1 not set")

    manager = SQXProcessManager()
    inst = await manager.ensure_running()
    try:
        yield inst
    finally:
        await manager.stop()


@ pytest_asyncio.fixture(scope="session")
async def sqx_session() -> SQXInstance:
    """Session-scoped SQX instance fixture.

    Starts one SQX daemon for the entire test session, stops at end.
    Skips if SQX_INTEGRATION=1 is not set.
    """
    if not os.environ.get("SQX_INTEGRATION"):
        pytest.skip("SQX_INTEGRATION=1 not set")

    manager = SQXProcessManager()
    inst = await manager.ensure_running(restart_on_crash=True)
    try:
        yield inst
    finally:
        # Note: session fixture cleanup happens after all tests
        pass