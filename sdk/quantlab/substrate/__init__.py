"""Unified execution substrate (REQ-26..28, REQ-42) — PR-2.

One daemon + project lifecycle + polling + event detection + checkpoint +
export runner parameterized per phase (build/retest/optimize/portfolio),
replacing the three overlapping legacy dispatch paths behind the
``QUANTLAB_UNIFIED_SUBSTRATE`` flag (REQ-28 parity).

Public surface:
- ``Executor.execute(phase, config) -> PhaseResult`` (design contract)
- ``Executor.execute_chain(spec, config)`` — chained multi-task runs (REQ-27)
- ``resolve_sqcli_path`` / ``select_dispatch_mode`` — fail-closed sqcli selectors
"""

from quantlab.substrate.executor import (
    ChainedTask,
    ChainSpec,
    Executor,
    Phase,
    PhaseConfig,
    PhaseResult,
    SubstrateConfigError,
    SubstrateError,
    is_unified_substrate_enabled,
    resolve_sqcli_path,
    select_dispatch_mode,
)
from quantlab.substrate.lifecycle import (
    DaemonLifecycle,
    LifecycleState,
    SubstrateCheckpoint,
    WORK_STAGES,
    can_transition,
)

__all__ = [
    "Executor",
    "Phase",
    "PhaseConfig",
    "PhaseResult",
    "ChainedTask",
    "ChainSpec",
    "SubstrateError",
    "SubstrateConfigError",
    "DaemonLifecycle",
    "LifecycleState",
    "SubstrateCheckpoint",
    "WORK_STAGES",
    "can_transition",
    "is_unified_substrate_enabled",
    "resolve_sqcli_path",
    "select_dispatch_mode",
]
