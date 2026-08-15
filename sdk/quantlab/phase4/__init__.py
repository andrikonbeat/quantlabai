"""Phase 4 — Foundation, JForex, Portfolio, Optimizer, Retester, Orchestrator.

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

Modules (committed in PR 3 — Optimizer + Retester):
- optimizer: Optimizer for walk-forward optimization via sqcli
- retester: Retester for Monte Carlo / Walk-Forward robustness testing via sqcli
- campaign_orchestrator: End-to-end Campaign Orchestrator (requires pipeline framework)
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

# Phase 3 — Optimizer + Retester
from quantlab.phase4.optimizer import Optimizer, OptimizerConfig, OptimizationResult, WalkForwardCycle
from quantlab.phase4.retester import (
    Retester,
    RetesterConfig,
    RetestResult,
    MonteCarloResult,
    WalkForwardResult,
)

# Phase 3 shared models
from quantlab.phase4.models import CampaignPhase, PhaseResult, PhaseStatus

# Phase 3 — Campaign Orchestrator (guarded: requires pipeline framework)
# Imported lazily (PEP 562) so importing any phase4 submodule — e.g. daemon or
# retester, which the pipeline package pulls in during its own initialization —
# does not trigger campaign_orchestrator -> quantlab.pipeline while the pipeline
# package may still be partially initialized (circular import). The names stay
# importable from ``quantlab.phase4`` and resolve to None only when the pipeline
# framework is genuinely unavailable.
_ORCHESTRATOR_IMPORTED = False


def __getattr__(name: str):
    global _ORCHESTRATOR_IMPORTED
    if name in {
        "CampaignOrchestrator",
        "CampaignConfig",
        "CampaignResult",
        "run_campaign",
        "CampaignCheckpoint",
        "CheckpointManager",
    }:
        if not _ORCHESTRATOR_IMPORTED:
            try:
                from quantlab.phase4.campaign_orchestrator import (
                    CampaignOrchestrator,
                    CampaignConfig,
                    CampaignResult,
                    run_campaign,
                )
                from quantlab.phase4.checkpoint import (
                    CampaignCheckpoint,
                    CheckpointManager,
                )
            except ImportError:
                CampaignOrchestrator = None  # type: ignore[assignment]
                CampaignConfig = None
                CampaignResult = None
                run_campaign = None
                CampaignCheckpoint = None
                CheckpointManager = None
            globals().update(
                CampaignOrchestrator=CampaignOrchestrator,
                CampaignConfig=CampaignConfig,
                CampaignResult=CampaignResult,
                run_campaign=run_campaign,
                CampaignCheckpoint=CampaignCheckpoint,
                CheckpointManager=CheckpointManager,
                _ORCHESTRATOR_IMPORTED=True,
            )
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
    # Phase 3 — Optimizer
    "Optimizer",
    "OptimizerConfig",
    "OptimizationResult",
    "WalkForwardCycle",
    # Phase 3 — Retester
    "Retester",
    "RetesterConfig",
    "RetestResult",
    "MonteCarloResult",
    "WalkForwardResult",
    # Phase 3 — Campaign Orchestrator
    "CampaignOrchestrator",
    "CampaignConfig",
    "CampaignResult",
    "CampaignPhase",
    "PhaseStatus",
    "PhaseResult",
    "run_campaign",
    # Checkpoint
    "CampaignCheckpoint",
    "CheckpointManager",
]
