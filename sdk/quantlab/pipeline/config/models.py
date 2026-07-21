"""Pipeline configuration models — multi-agent pipeline configuration."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


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
    fallback: str = Field(default="proceed", description="Action on timeout")
    required_approvers: int = Field(default=1, ge=1, description="Number of approvers required")
    notifiers: list[str] = Field(default_factory=list, description="Notification channels")
    config: dict[str, Any] = Field(default_factory=dict, description="Gate-specific config")


class MemoryConfig(BaseModel):
    """Agent memory configuration."""

    enabled: bool = Field(default=True, description="Whether agent memory is enabled")
    ttl_hours: float = Field(default=168.0, description="Memory TTL in hours (default 1 week)")
    max_entries: int = Field(default=1000, description="Maximum memory entries per agent")
    persistence: str = Field(default="both", description="Storage: engram, knowledge, or both")


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_portfolio_drawdown: float = Field(default=0.15, ge=0.01, le=1.0)
    max_single_strategy_risk: float = Field(default=0.03, ge=0.001, le=1.0)
    max_correlation: float = Field(default=0.7, ge=0.0, le=1.0)
    kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
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
    config: dict[str, Any] = Field(default_factory=dict, description="Agent-specific config")


class StageConfig(BaseModel):
    """Configuration for a pipeline stage."""

    name: str = Field(..., description="Stage name")
    type: str = Field(..., description="Stage type identifier")
    enabled: bool = Field(default=True)
    requires: list[str] = Field(default_factory=list, description="Required artifact keys")
    provides: list[str] = Field(default_factory=list, description="Provided artifact keys")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=5.0, description="Base retry delay in seconds")
    timeout: float = Field(default=300.0, description="Stage timeout in seconds")
    config: dict[str, Any] = Field(default_factory=dict, description="Stage-specific config")


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""

    name: str = Field(..., description="Pipeline name")
    version: str = Field(default="1.0")
    description: str = Field(default="")
    stages: list[StageConfig] = Field(default_factory=list)
    gates: list[GateConfig] = Field(default_factory=list)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    global_config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """Load pipeline configuration from YAML file.

        If the YAML doesn't contain a 'name' field, the filename (without extension)
        is used as the pipeline name.
        """
        import yaml
        from pathlib import Path
        with open(path) as f:
            data = yaml.safe_load(f)
        if "name" not in data:
            data["name"] = Path(path).stem
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        """Save pipeline configuration to YAML file."""
        import yaml
        with open(path, "w") as f:
            yaml.dump(self.model_dump(exclude_none=True, mode="json"), f, default_flow_style=False, sort_keys=False)

    def save(self, path: str) -> None:
        """Alias for to_yaml for backward compatibility."""
        self.to_yaml(path)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return self.model_dump(exclude_none=True, mode="json")


class MultiAgentPipelineConfig(BaseModel):
    """Extended pipeline configuration for multi-agent research."""

    name: str = Field(..., description="Pipeline name")
    version: str = Field(default="1.0")
    description: str = Field(default="")
    stages: list[StageConfig] = Field(default_factory=list)
    gates: list[GateConfig] = Field(default_factory=list)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    global_config: dict[str, Any] = Field(default_factory=dict)

    # Multi-agent specific
    research_objective: str = Field(default="", description="High-level research goal")
    risk: RiskConfig = Field(default_factory=RiskConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    @field_validator("stages")
    @classmethod
    def validate_stage_order(cls, v: list[StageConfig]) -> list[StageConfig]:
        """Ensure stage dependencies can be satisfied."""
        provided = set()
        for stage in v:
            for req in stage.requires:
                if req not in provided:
                    raise ValueError(f"Stage '{stage.name}' requires '{req}' which is not provided by any previous stage")
            provided.update(stage.provides)
        return v


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