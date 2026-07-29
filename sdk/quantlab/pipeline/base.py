"""Core pipeline abstractions: Stage ABC, PipelineContext, Pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    """Shared state flowing through pipeline stages.
    
    Config keys:
        broker_profile (str, optional): Broker identifier (``dukascopy``, ``ib``,
            ``oanda``) for cost-aware pipeline execution. Read by
            ``CostInjectionStage`` to initialise CostEngine and CostCollector.
    
    Artifact keys (set by stages):
        cost_config (dict, optional): Artifact written by ``CostInjectionStage``
            containing initialised ``CostEngine`` and ``CostCollector`` instances
            for downstream stages.
    
    Attributes:
        config: Immutable input configuration (e.g., from CampaignConfig or YAML).
            May include ``broker_profile`` for cost-aware pipelines.
        artifacts: Mutable dict; stages read from `requires`, write to `provides`.
            Includes ``cost_config`` after CostInjectionStage executes.
        metadata: Timestamps, run IDs, stage durations.
        error: Set by runner on first failure; subsequent stages skipped.
    """
    config: dict
    artifacts: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    error: Exception | None = None


class Stage(ABC):
    """Abstract base class for a pipeline stage.
    
    Each stage declares its I/O contract via `requires` and `provides`.
    The runner validates that `requires` are satisfied by upstream `provides`
    at pipeline build time.
    
    Attributes:
        name: Unique stage identifier.
        requires: Artifact keys this stage reads from `ctx.artifacts`.
        provides: Artifact keys this stage writes to `ctx.artifacts`.
    """
    name: str
    requires: list[str]
    provides: list[str]
    
    @abstractmethod
    async def execute(self, ctx: PipelineContext) -> Any:
        """Execute the stage logic.
        
        Args:
            ctx: PipelineContext with config, artifacts, metadata.
            
        Returns:
            Stage output (also stored in artifacts via `provides` keys).
        """
        ...


@dataclass
class Pipeline:
    """Ordered sequence of stages with fluent composition."""
    name: str
    stages: list[Stage] = field(default_factory=list)
    
    def then(self, stage: Stage) -> "Pipeline":
        """Add a stage to the pipeline (fluent builder)."""
        self.stages.append(stage)
        return self