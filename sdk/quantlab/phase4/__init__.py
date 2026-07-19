"""Phase 4 — JForex, Portfolio, Optimizer, Retester Automation.

Unified SDK package for end-to-end SQX automation pipeline.

Modules:
- errors: Exception hierarchy (Phase4Error and subclasses)
- http_client: AsyncSQXClient + SQXSessionLock + version detection
- daemon: SQXDaemonManager for -gui server lifecycle
- templates: CfxTemplateBuilder for Portfolio/Optimizer/Retester CFX
- jforex_deploy: JForexDeployer for .java export + indicator deployment
- portfolio_composer: PortfolioComposer for weight optimization
- portfolio_master: PortfolioMaster for genetic portfolio building
- optimizer: Optimizer for walk-forward optimization
- retester: Retester for Monte Carlo / Walk-Forward retesting
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

from quantlab.phase4.portfolio_composer import (
    PortfolioComposer,
    PortfolioWeightResult,
    WeightResult,
)

from quantlab.phase4.portfolio_master import (
    PortfolioMaster,
    PortfolioMasterResult,
    SelectedStrategy,
)

from quantlab.phase4.optimizer import Optimizer, OptimizerConfig, OptimizationResult, WalkForwardCycle

from quantlab.phase4.retester import (
    Retester,
    RetesterConfig,
    RetestResult,
    MonteCarloResult,
    WalkForwardResult,
)

from quantlab.phase4.campaign_orchestrator import (
    CampaignOrchestrator,
    CampaignConfig,
    CampaignResult,
    CampaignPhase,
    PhaseStatus,
    PhaseResult,
    run_campaign,
)

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
    # JForex
    "JForexDeployer",
    # Portfolio
    "PortfolioComposer",
    "PortfolioWeightResult",
    "WeightResult",
    "PortfolioMaster",
    "PortfolioMasterResult",
    "SelectedStrategy",
    # Optimizer
    "Optimizer",
    "OptimizerConfig",
    "OptimizationResult",
    "WalkForwardCycle",
    # Retester
    "Retester",
    "RetesterConfig",
    "RetestResult",
    "MonteCarloResult",
    "WalkForwardResult",
    # Campaign Orchestrator
    "CampaignOrchestrator",
    "CampaignConfig",
    "CampaignResult",
    "CampaignPhase",
    "PhaseStatus",
    "PhaseResult",
    "run_campaign",
    # Command Dispatcher
    "CommandDispatcher",
    "CampaignStatus",
]