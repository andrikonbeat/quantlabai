"""Pipeline Registry — stage registry and pipeline configuration discovery."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from quantlab.pipeline.base import Pipeline, Stage as PipelineStage
from quantlab.pipeline.config import PipelineConfig, PipelineSummary, StageConfig

logger = logging.getLogger(__name__)


class StageRegistry:
    """Registry mapping stage type strings to SQX concrete stage classes.

    Allows dynamic pipeline construction from configuration by looking up
    the appropriate stage implementation for each stage name.
    """

    # Map of stage name -> SQX concrete stage class
    _stage_map: dict[str, type[PipelineStage]] = {}

    def __init__(self) -> None:
        """Initialize registry with all 11 SQX stage implementations."""
        # Import all 11 SQX stages
        from quantlab.phase4.stages import (
            SQXValidateStage,
            SQXTranslateStage,
            SQXDaemonStartStage,
            SQXLoadConfigStage,
            SQXRunCampaignStage,
            SQXPollCampaignStage,
            SQXExportStage,
            SQXReadStage,
            SQXComputeStatsStage,
            SQXKnowledgeStoreStage,
            SQXReportStage,
            SQXCampaignStage,
        )

        # Map stage type names to concrete SQX stage implementations.
        # The logical phase5f-i pipeline stages (optimize, walkforward, montecarlo,
        # portfolio, risk, history, finalize) are composed from these granular
        # SQX daemon stages that map to actual SQX CLI operations.
        self._stage_map = {
            "validate": SQXValidateStage,
            "translate": SQXTranslateStage,
            "optimize": SQXRunCampaignStage,
            "walkforward": SQXPollCampaignStage,
            "montecarlo": SQXPollCampaignStage,
            "portfolio": SQXCampaignStage,
            "risk": SQXReadStage,
            "report": SQXReportStage,
            "knowledge_store": SQXKnowledgeStoreStage,
            "history": SQXExportStage,
            "finalize": SQXDaemonStartStage,
            "daemon_start": SQXDaemonStartStage,
            "load_config": SQXLoadConfigStage,
            "run_campaign": SQXRunCampaignStage,
            "poll_campaign": SQXPollCampaignStage,
            "export": SQXExportStage,
            "read": SQXReadStage,
            "compute_stats": SQXComputeStatsStage,
        }

    def get_stage_class(self, stage_name: str) -> type[PipelineStage] | None:
        """Return the stage class for a given stage name.

        Args:
            stage_name: The stage name (e.g., "validate", "translate", etc.)

        Returns:
            The corresponding SQX stage class, or None if unknown.
        """
        stage_class = self._stage_map.get(stage_name)
        if stage_class is None:
            logger.warning(f"Unknown stage type '{stage_name}'. Available: {', '.join(sorted(self._stage_map.keys()))}")
        return stage_class

    def create_pipeline(self, config: PipelineConfig) -> Pipeline:
        """Build a Pipeline from PipelineConfig by instantiating each stage.

        Args:
            config: PipelineConfig containing list of StageConfig objects.

        Returns:
            Configured Pipeline instance with all stages added in order.

        Raises:
            ValueError: If a stage type is not "builtin" or stage name is unknown.
        """
        pipeline = Pipeline(config.name)

        for stage_config in config.stages:
            if stage_config.type != "builtin":
                raise ValueError(
                    f"Unknown stage type '{stage_config.type}' for stage '{stage_config.name}'. "
                    f"Only 'builtin' stages are currently supported."
                )

            stage_class = self.get_stage_class(stage_config.name)
            if stage_class is None:
                raise ValueError(
                    f"Unknown builtin stage '{stage_config.name}'. "
                    f"Available: {', '.join(sorted(self._stage_map.keys()))}"
                )

            # Instantiate stage with any config parameters
            stage = stage_class()
            pipeline.then(stage)

        return pipeline


class PipelineRegistry:
    """Registry for discovering and loading pipeline configurations.

    Scans configured directories for *.yaml/*.yml files, parses them as
    pipeline configurations, and provides lookup by name.
    """

    def __init__(self, config_dirs: list[str] | list[Path] | None = None) -> None:
        """Initialize the registry with configuration directories.

        Args:
            config_dirs: List of directories to scan for pipeline YAML files.
                        Defaults to ["pipelines"] relative to CWD.
        """
        self._config_dirs: list[Path] = [
            Path(d).resolve() for d in (config_dirs or ["pipelines"])
        ]
        self._pipelines: dict[str, PipelineConfig] = {}
        self._discovered: bool = False

    def _ensure_discovered(self) -> None:
        """Lazily discover pipelines on first access."""
        if not self._discovered:
            self.discover()

    def discover(self) -> list[PipelineSummary]:
        """Scan all config directories for pipeline YAML files.

        Returns:
            List of PipelineSummary objects for each discovered pipeline.
        """
        self._pipelines.clear()
        summaries: list[PipelineSummary] = []

        for config_dir in self._config_dirs:
            if not config_dir.exists():
                logger.debug(f"Config directory does not exist: {config_dir}")
                continue

            for yaml_path in config_dir.rglob("*.yaml"):
                self._load_pipeline(yaml_path, summaries)
            for yaml_path in config_dir.rglob("*.yml"):
                self._load_pipeline(yaml_path, summaries)

        self._discovered = True
        return summaries

    def _load_pipeline(self, yaml_path: Path, summaries: list[PipelineSummary]) -> None:
        """Load a single pipeline from YAML file."""
        try:
            config = PipelineConfig.from_yaml(yaml_path)

            # Check for duplicate names
            if config.name in self._pipelines:
                logger.warning(
                    f"Duplicate pipeline name '{config.name}' in {yaml_path}; "
                    f"overwriting previous from {self._pipelines[config.name]}"
                )

            self._pipelines[config.name] = config
            summaries.append(
                PipelineSummary(
                    name=config.name,
                    stage_count=len(config.stages),
                    description=config.description,
                )
            )
            logger.debug(f"Loaded pipeline '{config.name}' from {yaml_path}")
        except Exception as e:
            logger.warning(f"Failed to load pipeline from {yaml_path}: {e}")

    def get(self, name: str) -> PipelineConfig:
        """Load and return full pipeline configuration by name.

        Args:
            name: Pipeline name to retrieve.

        Returns:
            PipelineConfig object.

        Raises:
            KeyError: If pipeline with given name is not found.
        """
        self._ensure_discovered()
        if name not in self._pipelines:
            available = ", ".join(sorted(self._pipelines.keys()))
            raise KeyError(
                f"Pipeline '{name}' not found. Available: {available or '(none)'}"
            )
        return self._pipelines[name]

    def list(self) -> list[PipelineSummary]:
        """Return all discovered pipelines as summaries."""
        self._ensure_discovered()
        return [
            PipelineSummary(
                name=config.name,
                stage_count=len(config.stages),
                description=config.description,
            )
            for config in self._pipelines.values()
        ]

    def names(self) -> list[str]:
        """Return list of discovered pipeline names."""
        self._ensure_discovered()
        return sorted(self._pipelines.keys())

    def reload(self) -> list[PipelineSummary]:
        """Force re-discovery of pipelines."""
        self._discovered = False
        return self.discover()

    def build_pipeline(
        self, name: str, context: dict[str, Any] | None = None
    ) -> Pipeline:
        """Build a Pipeline object from a named configuration.

        Creates concrete Stage instances based on stage type and config.

        Args:
            name: Pipeline name.
            context: Additional context passed to stage constructors.

        Returns:
            Configured Pipeline instance ready to run.

        Raises:
            KeyError: If pipeline not found.
            ValueError: If stage type is unknown.
        """
        config = self.get(name)
        registry = StageRegistry()
        return registry.create_pipeline(config)