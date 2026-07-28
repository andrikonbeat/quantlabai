"""Tests for SEG MCP tools."""

import json
import pytest

from quantlab.mcp.bridge import QuantLabMCPServer
from quantlab.mcp.seg_tools import get_generator


def test_generator_lazy_init():
    gen = get_generator()
    assert gen is not None
    assert hasattr(gen, "generate")


def test_seg_tool_registered():
    server = QuantLabMCPServer()
    tools = server.mcp._tool_manager.list_tools()
    tool_names = [t.name for t in tools]
    assert "generate_strategy" in tool_names


@pytest.mark.asyncio
async def test_generate_strategy_with_minimal_intent():
    gen = get_generator()
    candidates = await gen.generate({
        "market": "forex",
        "timeframe": "H1",
        "risk_profile": "moderate",
        "objective": "trend_following",
        "count": 3,
        "mode": "generative_only",
    })
    # May be empty if NoveltyGenerator has no real implementation to run
    # but should not raise exceptions
    assert isinstance(candidates, list)


def test_list_strategies_empty():
    gen = get_generator()
    strategies = gen.list_strategies()
    assert isinstance(strategies, list)
