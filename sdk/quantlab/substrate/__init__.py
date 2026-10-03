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
    is_legacy_execution_enabled,
    is_unified_substrate_enabled,
    resolve_sqcli_path,
    select_dispatch_backend,
    select_dispatch_mode,
)
from quantlab.substrate.lifecycle import (
    WORK_STAGES,
    DaemonLifecycle,
    LifecycleState,
    SubstrateCheckpoint,
    can_transition,
)

__all__ = [
    "WORK_STAGES",
    "ChainSpec",
    "ChainedTask",
    "DaemonLifecycle",
    "Executor",
    "LifecycleState",
    "Phase",
    "PhaseConfig",
    "PhaseResult",
    "SubstrateCheckpoint",
    "SubstrateConfigError",
    "SubstrateError",
    "can_transition",
    "is_legacy_execution_enabled",
    "is_unified_substrate_enabled",
    "resolve_sqcli_path",
    "select_dispatch_backend",
    "select_dispatch_mode",
]
