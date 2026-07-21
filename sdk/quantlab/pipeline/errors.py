"""Pipeline error types."""

from __future__ import annotations

from typing import Any


class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


class ContractValidationError(PipelineError):
    """Raised when pipeline stage contracts don't match.
    
    Attributes:
        missing_keys: Dictionary mapping stage name to list of missing required keys.
        stage_names: List of stage names involved in the validation failure.
    """
    
    def __init__(
        self,
        message: str,
        missing_keys: dict[str, list[str]] | None = None,
        stage_names: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.missing_keys = missing_keys or {}
        self.stage_names = stage_names or []
    
    def __str__(self) -> str:
        base = super().__str__()
        if self.missing_keys:
            details = ", ".join(
                f"{stage}: {', '.join(keys)}" 
                for stage, keys in self.missing_keys.items()
            )
            return f"{base} — Missing: {details}"
        return base


class StageExecutionError(PipelineError):
    """Raised when a stage fails during execution."""
    
    def __init__(
        self,
        message: str,
        stage_name: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.stage_name = stage_name
        self.original_error = original_error


class GateTimeoutError(PipelineError):
    """Raised when a gate approval times out."""
    
    def __init__(
        self,
        message: str,
        gate_id: str | None = None,
        fallback_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.gate_id = gate_id
        self.fallback_action = fallback_action


class ConfigurationError(PipelineError):
    """Raised when pipeline configuration is invalid."""
    
    def __init__(
        self,
        message: str,
        config_path: str | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.config_path = config_path
        self.validation_errors = validation_errors or []