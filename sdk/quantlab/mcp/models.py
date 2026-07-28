"""MCP-specific Pydantic models for internal tool request/response."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(str, Enum):
    """Machine-readable error codes for MCP tool errors."""

    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NOT_FOUND = "NOT_FOUND"


class MCPError(BaseModel):
    """Structured error payload returned by MCP tools."""

    model_config = ConfigDict(frozen=True)

    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolRequest(BaseModel):
    """Internal representation of an incoming MCP tool invocation."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ToolResponse(BaseModel):
    """Internal result container for an MCP tool execution."""

    model_config = ConfigDict(frozen=True)

    result: dict[str, Any]
    request_id: str | None = None
    error: MCPError | None = None
