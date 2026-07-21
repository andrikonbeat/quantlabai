"""Pipeline configuration models and loader."""

from quantlab.pipeline.config.models import (
    AgentConfig,
    GateConfig,
    MemoryConfig,
    RiskConfig,
    StageConfig,
    PipelineConfig,
    PipelineSummary,
    MultiAgentPipelineConfig,
    StageType,
    GateFallbackAction,
    GateApprovalStatus,
)
from quantlab.pipeline.config.loader import (
    load_multi_agent_pipeline_config,
    load_pipeline_config,
    save_multi_agent_pipeline_config,
    load_env_overrides,
    merge_configs,
)
from quantlab.pipeline.config.migration import migrate_config, CURRENT_VERSION

__all__ = [
    # Models
    "AgentConfig",
    "GateConfig",
    "MemoryConfig",
    "RiskConfig",
    "StageConfig",
    "PipelineConfig",
    "PipelineSummary",
    "MultiAgentPipelineConfig",
    "StageType",
    "GateFallbackAction",
    "GateApprovalStatus",
    # Loader functions
    "load_multi_agent_pipeline_config",
    "load_pipeline_config",
    "save_multi_agent_pipeline_config",
    "load_env_overrides",
    "merge_configs",
    # Migration
    "migrate_config",
    "CURRENT_VERSION",
]