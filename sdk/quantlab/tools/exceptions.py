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


class QuantLabError(Exception):
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


class LicenseError(QuantLabError):
    """Raised when SQX license validation fails."""

    def __init__(self, detail: str = "", *, cause: BaseException | None = None, license_path: str | None = None) -> None:
        super().__init__(detail, cause=cause)
        self.license_path = license_path


class CampaignError(QuantLabError):
    """Raised when a campaign execution fails."""

    def __init__(
        self, detail: str = "", *, cause: BaseException | None = None, phase: str | None = None, campaign_name: str | None = None
    ) -> None:
        if campaign_name:
            prefix = f"[{campaign_name}] "
            if not detail.startswith(prefix):
                detail = prefix + detail
        super().__init__(detail, cause=cause)
        self.phase = phase
        self.campaign_name = campaign_name


class TimeoutError(QuantLabError):
    """Raised when a subprocess exceeds the configured timeout."""


class InsufficientDataError(QuantLabError):
    """Raised when a computation requires non-empty data."""


# ─── Pipeline Exceptions ──────────────────────────────────────────────────────


class PipelineError(QuantLabError):
    """Base exception for pipeline execution errors."""

    def __init__(self, detail: str = "", *, cause: BaseException | None = None, stage_name: str | None = None) -> None:
        super().__init__(detail, cause=cause)
        self.stage_name = stage_name


class StageExecutionError(PipelineError):
    """Raised when a pipeline stage fails during execution."""

    def __init__(
        self, detail: str = "", *, cause: BaseException | None = None, stage_name: str | None = None, original_error: BaseException | None = None
    ) -> None:
        super().__init__(detail, cause=cause, stage_name=stage_name)
        self.original_error = original_error


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid."""

    def __init__(self, detail: str = "", *, cause: BaseException | None = None, config_field: str | None = None) -> None:
        super().__init__(detail, cause=cause)
        self.config_field = config_field
