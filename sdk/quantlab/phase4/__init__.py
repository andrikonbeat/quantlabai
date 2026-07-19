"""Phase 4 — Foundation: Errors, HTTP Client, Daemon, Templates.

This module exports only the Phase 4 Foundation (PR 1) components.
Phase 2/3 modules (JForex, Portfolio, Optimizer, Retester) are added
in subsequent PRs in the feature-branch-chain.

Modules (committed in PR 1):
- errors: Exception hierarchy (Phase4Error and subclasses)
- http_client: AsyncSQXClient + SQXSessionLock + version detection
- daemon: SQXDaemonManager for -gui server lifecycle
- templates: CfxTemplateBuilder for Portfolio/Optimizer/Retester CFX
"""

from quantlab.phase4.errors import (
    Phase4Error,
    JForexError,
    JForexConnectionError,
    JForexStrategyNotFoundError,
    JForexServerError,
    PortfolioError,
    StrategyNotFoundError,
    PortfolioOptimizationError,
    PortfolioStrategyLoadError,
    PortfolioSaveError,
    PortfolioMasterError,
    OptimizerError,
    OptimizerRunError,
    RetesterError,
    RetesterRunError,
    RetesterDatabankError,
    DatabankPathError,
    SQXError,
    SQXBindingError,
    UnsupportedSQXVersionError,
    SQXDaemonStartError,
    SQXSessionLockError,
)

from quantlab.phase4.http_client import (
    AsyncSQXClient,
    SQXSessionLock,
    CircuitBreaker,
)

from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.templates import CfxTemplateBuilder

__all__ = [
    # Errors
    "Phase4Error",
    "JForexError",
    "JForexConnectionError",
    "JForexStrategyNotFoundError",
    "JForexServerError",
    "PortfolioError",
    "StrategyNotFoundError",
    "PortfolioOptimizationError",
    "PortfolioStrategyLoadError",
    "PortfolioSaveError",
    "PortfolioMasterError",
    "OptimizerError",
    "OptimizerRunError",
    "RetesterError",
    "RetesterRunError",
    "RetesterDatabankError",
    "DatabankPathError",
    "SQXError",
    "SQXBindingError",
    "UnsupportedSQXVersionError",
    "SQXDaemonStartError",
    "SQXSessionLockError",
    # HTTP
    "AsyncSQXClient",
    "SQXSessionLock",
    "CircuitBreaker",
    # Daemon
    "SQXDaemonManager",
    # Templates
    "CfxTemplateBuilder",
]
