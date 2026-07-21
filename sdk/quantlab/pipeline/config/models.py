"""Pipeline configuration models — multi-agent pipeline configuration.

Provides ``MultiAgentPipelineConfig`` as the primary configuration model with
sections for pipeline stages, agents, gates, memory, and risk settings.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class StageType(str, Enum):
    """Type of pipeline stage."""

    BUILTIN = "builtin"
    AGENT = "agent"
    GATE = "gate"


class GateApprovalStatus(str, Enum):
    """Status of a gate approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"


class GateDecision(str, Enum):
    """Decision made at a human gate."""

    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class GateConfig(BaseModel):
    """Configuration for a human approval gate."""

    name: str = Field(..., description="Unique gate identifier")
    type: str = Field(default="human_approval", description="Gate type (human_approval, auto)")
    timeout_hours: float = Field(default=24.0, ge=0.1, description="Gate timeout in hours")
    fallback: str = Field(default="CONTINUE", description="Action on timeout (ABORT, CONTINUE, ESCALATE)")
    escalate_to: str = Field(default="", description="Contact or channel for escalation on timeout")
    required_approvers: int = Field(default=1, ge=1, description="Number of approvers required")
    notifications: list[str] = Field(default_factory=list, description="Notification channels")
    after_stage: str = Field(default="", description="Stage name after which this gate executes")
    gate_id: str = Field(default="", description="Gate identifier (e.g. HUMAN_REVIEW_OBJECTIVES)")
    requires: list[str] = Field(default_factory=list, description="Artifact keys the gate reads")
    config: dict[str, Any] = Field(default_factory=dict, description="Gate-specific config")

    @model_validator(mode="after")
    def _sync_name_and_gate_id(self) -> "GateConfig":
        if not self.gate_id and self.name:
            self.gate_id = self.name
        if not self.name and self.gate_id:
            self.name = self.gate_id
        return self


class MemoryConfig(BaseModel):
    """Agent memory configuration."""

    enabled: bool = Field(default=True, description="Whether agent memory is enabled")
    topic_prefix: str = Field(default="quantlab/agent", description="Engram topic prefix")
    ttl_hours: float = Field(default=168.0, description="Memory TTL in hours (default 1 week)")
    max_entries: int = Field(default=1000, description="Maximum memory entries per agent")
    retention_days: int = Field(default=365, description="Memory retention in days")
    cross_agent_sharing: bool = Field(default=True, description="Allow cross-agent memory queries")
    persistence: str = Field(default="both", description="Storage: engram, knowledge, or both")


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_portfolio_drawdown: float = Field(default=0.15, ge=0.01, le=1.0)
    max_single_strategy_risk: float = Field(default=0.03, ge=0.001, le=1.0)
    max_strategy_correlation: float = Field(default=0.7, ge=0.0, le=1.0)
    max_single_strategy_weight: float = Field(default=0.4, ge=0.01, le=1.0)
    kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
    kelly_fraction_cap: float = Field(default=0.25, ge=0.0, le=1.0)
    var_confidence: float = Field(default=0.95, ge=0.5, le=0.999)
    max_open_positions: int = Field(default=10, ge=1)


class AgentConfig(BaseModel):
    """Configuration for a pipeline agent."""

    name: str = Field(..., description="Agent name")
    type: str = Field(..., description="Agent type")
    enabled: bool = Field(default=True)
    model: str = Field(default="gpt-4", description="LLM model to use")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=100, le=32000)
    system_prompt: str = Field(default="", description="Custom system prompt")
    tools: list[str] = Field(default_factory=list, description="Available tools")
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    max_retries: int = Field(default=2, ge=0, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=3600, ge=1, description="Agent timeout in seconds")
    config: dict[str, Any] = Field(default_factory=dict, description="Agent-specific config")


class StageConfig(BaseModel):
    """Configuration for a pipeline stage."""

    name: str = Field(..., description="Stage name")
    type: str = Field(..., description="Stage type identifier")
    agent: str = Field(default="", description="Agent name (for agent stages)")
    enabled: bool = Field(default=True)
    requires: list[str] = Field(default_factory=list, description="Required artifact keys")
    provides: list[str] = Field(default_factory=list, description="Provided artifact keys")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=5.0, description="Base retry delay in seconds")
    timeout: float = Field(default=300.0, description="Stage timeout in seconds")
    gate_after: str = Field(default="", description="Gate ID to trigger after this stage")
    config: dict[str, Any] = Field(default_factory=dict, description="Stage-specific config")


class PipelineSection(BaseModel):
    """Nested ``pipeline`` section containing name, description, version, and stages."""

    name: str = Field(..., description="Pipeline name")
    description: str = Field(default="")
    version: str = Field(default="1.0.0")
    stages: list[StageConfig] = Field(default_factory=list)


class MultiAgentPipelineConfig(BaseModel):
    """Extended pipeline configuration for multi-agent research.

    Supports both flat format (stages at top level) and nested format
    (stages under ``pipeline.*``) for backward compatibility.

    Sections:
        pipeline : PipelineSection — name, description, version, stages
        agents   : dict[str, AgentConfig] — per-agent configuration
        gates    : list[GateConfig] — gate definitions
        memory   : MemoryConfig — Engram integration settings
        risk     : RiskConfig — portfolio-level risk limits
    """

    name: str = Field(default="", description="Pipeline name")
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    stages: list[StageConfig] = Field(default_factory=list)
    gates: list[GateConfig] = Field(default_factory=list)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    global_config: dict[str, Any] = Field(default_factory=dict)

    # Multi-agent specific
    research_objective: str = Field(default="", description="High-level research goal")
    risk: RiskConfig = Field(default_factory=RiskConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    @model_validator(mode="before")
    @classmethod
    def _unpack_pipeline_section(cls, data: Any) -> Any:
        """Support nested ``pipeline.*`` format by unpacking into top-level fields."""
        if isinstance(data, dict):
            pipeline = data.get("pipeline")
            if pipeline and isinstance(pipeline, dict):
                # Merge pipeline fields into top level if not already set
                for key in ("name", "description", "version", "stages"):
                    if key not in data or not data.get(key):
                        if key in pipeline:
                            data[key] = pipeline[key]
        return data

    @field_validator("stages")
    @classmethod
    def validate_stage_order(cls, v: list[StageConfig]) -> list[StageConfig]:
        """Ensure stage dependencies can be satisfied by order."""
        provided = set()
        for stage in v:
            for req in stage.requires:
                if req not in provided:
                    raise ValueError(
                        f"Stage '{stage.name}' requires '{req}' "
                        f"which is not provided by any previous stage"
                    )
            provided.update(stage.provides)
        return v

    @classmethod
    def load(cls, path: str | Path) -> "MultiAgentPipelineConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            Validated MultiAgentPipelineConfig instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValidationError: If the YAML data fails schema validation.
        """
        from quantlab.pipeline.config.loader import load_multi_agent_pipeline_config
        return load_multi_agent_pipeline_config(str(path))

    def save(self, path: str | Path) -> None:
        """Save configuration to YAML file."""
        import yaml
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(exclude_none=True, mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def to_yaml(self, path: str | Path) -> None:
        """Alias for save()."""
        self.save(path)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return self.model_dump(exclude_none=True, mode="json")


class PipelineConfig(BaseModel):
    """Simple pipeline configuration (backward compatible)."""

    name: str = Field(..., description="Pipeline name")
    version: str = Field(default="1.0")
    description: str = Field(default="")
    stages: list[StageConfig] = Field(default_factory=list)
    gates: list[GateConfig] = Field(default_factory=list)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    global_config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Load pipeline configuration from YAML file."""
        import yaml
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "name" not in data:
            data["name"] = path.stem
        return cls(**data)

    def to_yaml(self, path: str | Path) -> None:
        """Save pipeline configuration to YAML file."""
        import yaml
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(exclude_none=True, mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def save(self, path: str | Path) -> None:
        """Alias for to_yaml."""
        self.to_yaml(path)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, mode="json")


class PipelineSummary(BaseModel):
    """Lightweight pipeline summary for listing."""

    name: str
    version: str = "1.0"
    stage_count: int = 0
    gate_count: int = 0
    agent_count: int = 0
    estimated_duration_minutes: float = 0.0
    description: str = ""


class PipelineAgentConfig(BaseModel):
    """Legacy pipeline configuration (backward compatible)."""

    name: str
    description: str = ""
    version: str = "1.0"
    stages: list[StageConfig] = Field(default_factory=list)
