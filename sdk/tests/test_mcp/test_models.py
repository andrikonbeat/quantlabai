"""Tests for MCP Pydantic models."""

import pytest
from quantlab.mcp.models import ErrorCode, MCPError, ToolRequest, ToolResponse


def test_error_code_values():
    assert ErrorCode.INVALID_REQUEST == "INVALID_REQUEST"
    assert ErrorCode.NOT_FOUND == "NOT_FOUND"
    assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"
    assert ErrorCode.TIMEOUT == "TIMEOUT"
    assert ErrorCode.PROVIDER_ERROR == "PROVIDER_ERROR"


def test_mcp_error():
    err = MCPError(code=ErrorCode.NOT_FOUND, message="Strategy not found")
    assert err.code == ErrorCode.NOT_FOUND
    assert err.message == "Strategy not found"
    assert err.details == {}


def test_mcp_error_with_details():
    err = MCPError(
        code=ErrorCode.RATE_LIMITED,
        message="Too fast",
        details={"retry_after": 30},
    )
    assert err.details == {"retry_after": 30}


def test_tool_request_defaults():
    req = ToolRequest(name="run_backtest")
    assert req.name == "run_backtest"
    assert req.arguments == {}
    assert req.request_id is None


def test_tool_request_with_args():
    req = ToolRequest(name="run_backtest", arguments={"symbol": "AAPL"})
    assert req.arguments == {"symbol": "AAPL"}


def test_tool_request_with_request_id():
    req = ToolRequest(name="run_backtest", arguments={}, request_id="req-1")
    assert req.request_id == "req-1"


def test_tool_response():
    resp = ToolResponse(result={"status": "ok"})
    assert resp.result == {"status": "ok"}
    assert resp.error is None
    assert resp.request_id is None


def test_tool_response_with_error():
    err = MCPError(code=ErrorCode.NOT_FOUND, message="Not found")
    resp = ToolResponse(result={}, error=err)
    assert resp.error is not None
    assert resp.error.code == ErrorCode.NOT_FOUND


def test_tool_response_json_serializable():
    resp = ToolResponse(result={"nested": {"value": 42}})
    dumped = resp.model_dump(mode="json")
    assert dumped["result"]["nested"]["value"] == 42


def test_frozen_models():
    req = ToolRequest(name="test", arguments={})
    with pytest.raises(Exception):
        req.name = "changed"
