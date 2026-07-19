"""Phase 4 — Custom exception hierarchy.

All Phase 4 exceptions inherit from Phase4Error for easy catching.
"""

from __future__ import annotations

from typing import Optional


class Phase4Error(Exception):
    """Base exception for all Phase 4 errors."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message}: {self.detail}"
        return self.message


# ── JForex Deploy ────────────────────────────────────────────────────────────

class JForexError(Phase4Error):
    """Base for JForex deployment errors."""


class JForexConnectionError(JForexError):
    """Raised when SQX HTTP server connection fails."""

    def __init__(self, host: str, port: int, detail: Optional[str] = None):
        msg = f"Cannot connect to SQX server at {host}:{port}"
        super().__init__(msg, detail)
        self.host = host
        self.port = port


class JForexStrategyNotFoundError(JForexError):
    """Raised when a strategy ID is not found in SQX."""

    def __init__(self, strategy_id: str, detail: Optional[str] = None):
        msg = f"Strategy '{strategy_id}' not found in SQX"
        super().__init__(msg, detail)
        self.strategy_id = strategy_id


class JForexServerError(JForexError):
    """Raised when SQX HTTP server returns 5xx error."""

    def __init__(self, status_code: int, response_body: Optional[str] = None):
        msg = f"SQX server error: HTTP {status_code}"
        super().__init__(msg, response_body)
        self.status_code = status_code
        self.response_body = response_body


# ── Portfolio Composer / Master ──────────────────────────────────────────────

class PortfolioError(Phase4Error):
    """Base for portfolio errors."""


class StrategyNotFoundError(PortfolioError):
    """Raised when a strategy ID is not found in SQX session (Portfolio Composer)."""

    def __init__(self, strategy_id: str, detail: Optional[str] = None):
        msg = f"Strategy '{strategy_id}' not found in SQX session"
        super().__init__(msg, detail)
        self.strategy_id = strategy_id


class PortfolioOptimizationError(PortfolioError):
    """Raised when portfolio weight optimization fails."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Portfolio optimization failed"
        super().__init__(msg, detail)


class PortfolioStrategyLoadError(PortfolioError):
    """Raised when loading strategies into Portfolio Composer fails."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Portfolio strategy load failed"
        super().__init__(msg, detail)


class PortfolioSaveError(PortfolioError):
    """Raised when saving portfolio fails."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Portfolio save failed"
        super().__init__(msg, detail)


class PortfolioMasterError(PortfolioError):
    """Raised when Portfolio Master build fails."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Portfolio Master build failed"
        super().__init__(msg, detail)


# ── Optimizer ────────────────────────────────────────────────────────────────

class OptimizerError(Phase4Error):
    """Base for optimizer errors."""


class OptimizerRunError(OptimizerError):
    """Raised when optimizer execution fails (sqcli, CFX, etc.)."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Optimizer run failed"
        super().__init__(msg, detail)


# ── Retester ──────────────────────────────────────────────────────────────────

class RetesterError(Phase4Error):
    """Base for retester errors."""


class RetesterRunError(RetesterError):
    """Raised when retester execution fails."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Retester run failed"
        super().__init__(msg, detail)


class RetesterDatabankError(RetesterError):
    """Raised when databank configuration is invalid."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Retester databank configuration error"
        super().__init__(msg, detail)


class DatabankPathError(RetesterError):
    """Raised when databank path validation fails."""

    def __init__(self, databank: str, detail: Optional[str] = None):
        msg = f"Invalid databank path: '{databank}'"
        super().__init__(msg, detail)
        self.databank = databank


# ── SQX Daemon / Session ─────────────────────────────────────────────────────

class SQXError(Phase4Error):
    """Base for SQX daemon/session errors."""


class SQXBindingError(SQXError):
    """Raised when SQX daemon binds to non-localhost address."""

    def __init__(self, bind_address: str, detail: Optional[str] = None):
        msg = f"SQX daemon must bind to 127.0.0.1 for security, got '{bind_address}'"
        super().__init__(msg, detail)
        self.bind_address = bind_address


class UnsupportedSQXVersionError(SQXError):
    """Raised when SQX version is not in supported list."""

    def __init__(self, version: str, supported: list[str]):
        msg = f"Unsupported SQX version: {version}. Supported: {supported}"
        super().__init__(msg)
        self.version = version
        self.supported = supported


class SQXDaemonStartError(SQXError):
    """Raised when SQX daemon fails to start."""

    def __init__(self, detail: Optional[str] = None):
        msg = "SQX daemon failed to start"
        super().__init__(msg, detail)


# ── SQX Session Lock ──────────────────────────────────────────────────────────

class SQXSessionLockError(Phase4Error):
    """Raised when SQX session lock cannot be acquired."""

    def __init__(self, detail: Optional[str] = None):
        msg = "Could not acquire SQX session lock (another operation in progress?)"
        super().__init__(msg, detail)