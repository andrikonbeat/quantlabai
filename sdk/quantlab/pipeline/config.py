"""Pipeline configuration models for YAML-based pipeline definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


@dataclass
class StageConfig:
    """Configuration for a single pipeline stage."""

    name: str
    type: Literal["builtin", "custom"]
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Complete pipeline configuration loaded from YAML."""

    name: str
    description: str = ""
    stages: list[StageConfig] = field(default_factory=list)
    version: str = "1.0"

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PipelineConfig":
        """Load pipeline configuration from a YAML file."""
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        stages = [StageConfig(**s) for s in data.get("stages", [])]
        return cls(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            stages=stages,
            version=data.get("version", "1.0"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "stages": [
                {"name": s.name, "type": s.type, "config": s.config}
                for s in self.stages
            ],
        }

    def save(self, path: Path | str) -> None:
        """Save pipeline configuration to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)


class PipelineSummary(BaseModel):
    """Summary view of a pipeline for listing."""

    name: str = Field(..., description="Pipeline name")
    stage_count: int = Field(..., description="Number of stages in the pipeline")
    description: str = Field(default="", description="Pipeline description")
    version: str = Field(default="1.0", description="Pipeline version")


class PipelineConfigModel(BaseModel):
    """Pydantic model for pipeline configuration validation."""

    name: str
    stages: list[dict[str, Any]] = Field(default_factory=list)
    description: str = ""

    def to_pipeline_config(self) -> PipelineConfig:
        """Convert to PipelineConfig dataclass."""
        stages = [StageConfig(**s) for s in self.stages]
        return PipelineConfig(
            name=self.name,
            stages=stages,
            description=self.description,
        )