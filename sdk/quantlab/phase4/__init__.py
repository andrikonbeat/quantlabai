"""Phase 4 — Foundation, JForex, Portfolio, CommandDispatcher.

Modules (committed in PR 1 — Foundation):
- errors: Exception hierarchy (Phase4Error and subclasses)
- http_client: AsyncSQXClient + SQXSessionLock + version detection
- daemon: SQXDaemonManager for -gui server lifecycle
- templates: CfxTemplateBuilder for Portfolio/Optimizer/Retester CFX

Modules (committed in PR 2 — JForex + Portfolio):
- jforex_deploy: JForexDeployer for strategy export and indicator deployment
- portfolio_composer: PortfolioComposer for weight optimization via SQX HTTP API
- portfolio_master: PortfolioMaster for genetic portfolio building via sqcli
- command_dispatcher: CommandDispatcher with CLI-based campaign operations
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

from quantlab.phase4.jforex_deploy import JForexDeployer
from quantlab.phase4.portfolio_composer import PortfolioComposer, PortfolioWeightResult, WeightResult
from quantlab.phase4.portfolio_master import PortfolioMaster, PortfolioMasterResult, SelectedStrategy
from quantlab.phase4.command_dispatcher import CommandDispatcher, CampaignStatus

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
    # Phase 2 — JForex Deploy
    "JForexDeployer",
    # Phase 2 — Portfolio
    "PortfolioComposer",
    "PortfolioMaster",
    "WeightResult",
    "PortfolioWeightResult",
    "SelectedStrategy",
    "PortfolioMasterResult",
    # Phase 2 — CommandDispatcher
    "CommandDispatcher",
    "CampaignStatus",
]
