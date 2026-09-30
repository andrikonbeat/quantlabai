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


class GuardianProviderError(PipelineError):
    """Raised when a guardian is constructed without a concrete data provider.

    Guardians fail closed: a missing provider is a wiring defect, not an empty
    dataset. The orchestrator raises this at construction time instead of
    substituting a silent pass-through provider.

    Attributes:
        guardian_name: Class name of the guardian with the missing provider.
        provider_name: Name of the provider slot that was ``None`` or absent.
    """

    def __init__(
        self,
        message: str,
        guardian_name: str | None = None,
        provider_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.guardian_name = guardian_name
        self.provider_name = provider_name


class PortfolioStateBlockedError(PipelineError):
    """Raised when a stage refuses to run under a blocked ``PortfolioState``.

    ``QUARANTINE`` and ``DEFENSIVE`` block downstream stages until an explicit
    human override is granted through the relevant approval gate.

    Attributes:
        portfolio_state: The blocking portfolio state value.
        stage_name: Name of the stage that refused to run.
    """

    def __init__(
        self,
        message: str,
        portfolio_state: str | None = None,
        stage_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.portfolio_state = portfolio_state
        self.stage_name = stage_name