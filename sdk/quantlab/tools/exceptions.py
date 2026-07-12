"""QuantLab error hierarchy.

All SDK errors inherit from QuantLabError, enabling catch-all handling
while allowing specific error types to be caught individually.

Usage:
    try:
        ...
    except QuantLabError as e:
        log.error("SDK error: %s", e.detail)
"""

from typing import Any


class QuantLabError(BaseException):
    """Base exception for all QuantLab SDK errors."""

    def __init__(self, detail: str = "", *, cause: BaseException | None = None) -> None:
        self.detail = detail
        self.cause = cause
        super().__init__(detail)

    def __str__(self) -> str:
        parts = [self.detail]
        if self.cause:
            parts.append(f" (caused by: {self.cause})")
        return "".join(parts)


class ParseError(QuantLabError):
    """Raised when parsing structured data fails (YAML, CSV, XLSX)."""


class ValidationError(QuantLabError):
    """Raised when semantic validation of models fails."""


class TranslationError(QuantLabError):
    """Raised when DSL-to-CFX translation fails."""


class SQXNotFoundError(QuantLabError):
    """Raised when sqcli.exe cannot be located in real-execution mode."""


class TimeoutError(QuantLabError):
    """Raised when a subprocess exceeds the configured timeout."""


class InsufficientDataError(QuantLabError):
    """Raised when a computation requires non-empty data."""
