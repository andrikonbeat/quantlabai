"""Campaign orchestration primitives (REQ-01, REQ-37).

``flow`` owns the canonical 14-phase lifecycle constant and the
flow-integrity assertion enforced at campaign start and after any
harness change (REQ-37).

``delegation`` provides the per-phase sub-agent dispatch glue (REQ-801..REQ-804,
REQ-809): ``PhaseDirective``, ``PhaseResult``, ``PHASE_AGENTS``, and
``execute_phase()``.
"""

from quantlab.campaign.delegation import (
    PHASE_AGENTS,
    PRODUCTION_EXECUTORS,
    AuthorityViolationError,
    LongOpSpec,
    PhaseDirective,
    PhaseExecutor,
    PhaseNotFoundError,
    PhaseResult,
    execute_phase,
    validate_phase_result,
)
from quantlab.campaign.flow import (
    PHASES,
    STAGE_FOR_PHASE,
    FlowIntegrityError,
    assert_flow,
    missing_flow_stages,
)
from quantlab.campaign.gatekeeper import (
    GatekeeperError,
    GatekeeperHalt,
    run_post_phase_gatekeeper,
)

__all__ = [
    # Flow integrity (REQ-37)
    "PHASES",
    "STAGE_FOR_PHASE",
    "FlowIntegrityError",
    "assert_flow",
    "missing_flow_stages",
    # Delegation glue (REQ-801..REQ-804, REQ-809, REQ-815)
    "PhaseDirective",
    "PhaseResult",
    "PHASE_AGENTS",
    "PRODUCTION_EXECUTORS",
    "PhaseExecutor",
    "execute_phase",
    "validate_phase_result",
    "PhaseNotFoundError",
    "AuthorityViolationError",
    "LongOpSpec",
    # Post-phase gatekeeper (REQ-01)
    "run_post_phase_gatekeeper",
    "GatekeeperError",
    "GatekeeperHalt",
]
