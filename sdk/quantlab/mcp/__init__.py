"""MCP Bridge — exposes QuantLab subsystems over the Model Context Protocol.

This package provides an ``MCPServer`` (via ``bridge.py``) that registers
tools from four domain modules: pipelines, evolution, health, and
fundamental analysis.

Usage:
    python -m quantlab.mcp
"""

from quantlab.mcp.models import ErrorCode, MCPError, ToolRequest, ToolResponse

__all__ = [
    "ErrorCode",
    "MCPError",
    "ToolRequest",
    "ToolResponse",
]
