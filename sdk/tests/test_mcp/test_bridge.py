"""Tests for QuantLabMCPServer bridge."""

import pytest
from quantlab.mcp.bridge import QuantLabMCPServer


def test_server_initializes():
    server = QuantLabMCPServer()
    assert server.mcp is not None


def test_server_name():
    server = QuantLabMCPServer()
    assert server.mcp.name == "quantlab-mcp"


def test_tool_registration():
    server = QuantLabMCPServer()
    tools = server.mcp._tool_manager.list_tools()
    tool_names = [t.name for t in tools]
    assert "run_backtest" in tool_names
    assert "list_pipelines" in tool_names
    assert "get_pipeline_run" in tool_names
    assert "generate_candidates" in tool_names
    assert "query_pool" in tool_names
    assert "promote_candidate" in tool_names
    assert "evaluate_strategy" in tool_names
    assert "get_health_metrics" in tool_names
    assert "compute_fitness" in tool_names
    assert "get_fundamental_data" in tool_names
    assert "get_financial_ratios" in tool_names


def test_tool_descriptions():
    server = QuantLabMCPServer()
    tools = server.mcp._tool_manager.list_tools()
    for tool in tools:
        assert tool.description, f"Tool {tool.name} has no description"
