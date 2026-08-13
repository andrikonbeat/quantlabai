"""Pipeline Registry — stage registry and pipeline configuration discovery.

The ``StageRegistry`` maps stage type names to their concrete classes,
supporting both SQX built-in stages and multi-agent stages (agent + gate types).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from quantlab.pipeline.base import Pipeline, Stage as PipelineStage
from quantlab.pipeline.config import PipelineConfig, PipelineSummary, StageConfig
from quantlab.pipeline.stages.agent_stages import (
    BuilderStage,
    DeployStage,
    MonitorStage,
    PortfolioStage,
    ResearchStage,
    ReviewStage,
    StatisticsStage,
)
from quantlab.pipeline.stages.gate_interceptor import GateInterceptorStage
from quantlab.pipeline.stages.monte_carlo_stage import MonteCarloStage
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage
from quantlab.pipeline.stages.optimizer_stage import OptimizerStage
from quantlab.pipeline.stages.retester_stage import RetesterStage

logger = logging.getLogger(__name__)


class StageRegistry:
    """Registry mapping stage type strings to concrete stage classes.

    Supports three stage types:
        - ``builtin``: SQX pipeline stages (validate, translate, daemon_start, etc.)
        - ``agent``: Multi-agent stages (research, builder, statistics, etc.)
        - ``gate``: Gate interceptor stages (human approval gates)

    Allows dynamic pipeline construction from configuration by looking up
    the appropriate stage implementation for each stage name.
    """

    def __init__(self) -> None:
        """Initialize registry with all builtin SQX stages and agent stages."""
        self._stage_map: dict[str, type[PipelineStage]] = {}

        # Register builtin SQX stages (tries to import from phase4, falls back to abstract)
        self._register_builtin_stages()

        # Register agent stages (abstract base classes — concrete in PR 2/3/4/5)
        self._register_agent_stages()

    def _register_builtin_stages(self) -> None:
        """Register the 11 SQX builtin stages from phase4, or fall back to abstract."""
        try:
            from quantlab.phase4.stages import (
                SQXComputeStatsStage,
                SQXDaemonStartStage,
                SQXExportStage,
                SQXKnowledgeStoreStage,
                SQXLoadConfigStage,
                SQXPollCampaignStage,
                SQXReadStage,
                SQXReportStage,
                SQXRunCampaignStage,
                SQXTranslateStage,
                SQXValidateStage,
            )
            # Also import SQXCampaignStage — the combined stage
            from quantlab.phase4.stages import SQXCampaignStage  # type: ignore[no-redef]

            try:
                from quantlab.phase4.stages import SQXCostInjectionStage
            except ImportError:
                from quantlab.pipeline._stages import CostInjectionStage as SQXCostInjectionStage

            self._stage_map.update({
                "validate": SQXValidateStage,
                "translate": SQXTranslateStage,
                "cost_injection": SQXCostInjectionStage,
                "daemon_start": SQXDaemonStartStage,
                "load_config": SQXLoadConfigStage,
                "run_campaign": SQXRunCampaignStage,
                "poll_campaign": SQXPollCampaignStage,
                "campaign": SQXCampaignStage,
                "export": SQXExportStage,
                "read": SQXReadStage,
                "compute_stats": SQXComputeStatsStage,
                "knowledge_store": SQXKnowledgeStoreStage,
                "report": SQXReportStage,
            })
        except ImportError:
            # Fall back to abstract base stages from pipeline.stages
            from quantlab.pipeline.stages import (
                ValidateStage,
                TranslateStage,
                CostInjectionStage,
                DaemonStartStage,
                LoadConfigStage,
                RunCampaignStage,
                PollCampaignStage,
                CampaignStage,
                ExportStage,
                ReadStage,
                ComputeStatsStage,
                KnowledgeStoreStage,
                ReportStage,
            )

            self._stage_map.update({
                "validate": ValidateStage,
                "translate": TranslateStage,
                "cost_injection": CostInjectionStage,
                "daemon_start": DaemonStartStage,
                "load_config": LoadConfigStage,
                "run_campaign": RunCampaignStage,
                "poll_campaign": PollCampaignStage,
                "campaign": CampaignStage,
                "export": ExportStage,
                "read": ReadStage,
                "compute_stats": ComputeStatsStage,
                "knowledge_store": KnowledgeStoreStage,
                "report": ReportStage,
            })
            logger.debug("SQX phase4 stages not available — using abstract base stages")

    def _register_agent_stages(self) -> None:
        """Register the 7 multi-agent stage classes plus gate interceptor."""
        # Concrete agent implementations from quantlab.agents
        from quantlab.agents.research_agent import ResearchAgent
        from quantlab.agents.builder_agent import BuilderAgent
        from quantlab.agents.statistics_agent import StatisticsAgent
        from quantlab.agents.analysis_agent import AnalysisAgent
        from quantlab.agents.reviewer_agent import ReviewerAgent
        from quantlab.agents.monitoring_agent import MonitoringAgent

        # Stage wrappers for agents that don't inherit from Stage ABC
        from quantlab.pipeline.stages.agent_stages import (
            LLMResearchStage, AnalysisStage, ResearchStage, BuilderStage, StatisticsStage,
            ReviewStage, PortfolioStage, DeployStage, MonitorStage,
            HypothesisBuilderStage, RefutationStage, GuardianEvaluationStage,
            GuardianEvaluationAgentStage,
        )
        # Post-optimize orchestrated stages (PR 6): concrete REQ-01 phase
        # implementations. Aliased so they don't shadow the abstract anchors
        # imported above (the anchors still drive the legacy wrapper classes).
        from quantlab.pipeline.stages.archiver_stage import ArchiverStage
        from quantlab.pipeline.stages.archive_stage import ArchiveStage
        from quantlab.pipeline.stages.compile_stage import CompileStage
        from quantlab.pipeline.stages.execution_monitor_stage import ExecutionMonitorStage
        from quantlab.pipeline.stages.live_ops_stage import LiveOpsStage
        from quantlab.pipeline.stages.demo_stage import DemoStage
        from quantlab.pipeline.stages.deploy_stage import DeployStage as DeployPackageStage
        from quantlab.pipeline.stages.indicator_export_stage import IndicatorExportStage
        from quantlab.pipeline.stages.portfolio_stage import (
            PortfolioStage as PortfolioComposeStage,
        )

        class ResearchAgentStage(ResearchStage):
            """Wrapper: adapts ResearchAgent.run() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                self._agent = ResearchAgent()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                return await self._agent.run(ctx)

        class BuilderAgentStage(BuilderStage):
            """Wrapper: adapts BuilderAgent.run() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                self._agent = BuilderAgent()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                return await self._agent.run(ctx)

        class AnalysisAgentStage(AnalysisStage):
            """Wrapper: adapts AnalysisAgent.run() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                self._agent = AnalysisAgent()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                return await self._agent.run(ctx)

        class HypothesisBuilderAgentStage(HypothesisBuilderStage):
            """Wrapper: adapts HypothesisBuilder.build() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                from quantlab.agents.hypothesis_builder import HypothesisBuilder
                self._builder = HypothesisBuilder()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                from quantlab.dsl.models import HypothesisConfig

                raw_hypotheses = ctx.artifacts.get("hypotheses", [])
                hypotheses: list[HypothesisConfig] = [
                    HypothesisConfig(**h) if isinstance(h, dict) else h
                    for h in raw_hypotheses
                ]
                market_context = ctx.artifacts.get("market_context")
                mode = None
                if ctx.config:
                    mode = ctx.config.get("hypothesis_builder_mode")

                building_blocks, strategies = await self._builder.build(
                    hypotheses=hypotheses,
                    market_context=market_context,
                    mode=mode,
                )

                # Convert to serialisable dicts for context
                bb_dicts = [b.model_dump(mode="json") for b in building_blocks]
                strat_dicts = [s.model_dump(mode="json") for s in strategies]

                ctx.artifacts["building_blocks"] = bb_dicts
                ctx.artifacts["strategies"] = strat_dicts

                return {
                    "building_blocks": bb_dicts,
                    "strategies": strat_dicts,
                }

        class LLMResearchAgentStage(LLMResearchStage):
            """Wrapper: adapts LLMResearchAgent.generate_config() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                from quantlab.agents.llm_research_agent import LLMResearchAgent
                self._agent = LLMResearchAgent()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                config = ctx.config or {}
                objectives: list[str] = config.get("objectives", ["Research"])
                if isinstance(objectives, str):
                    objectives = [objectives]
                market_context: dict[str, Any] | None = config.get("market_context")

                # Build LLMConfig from config dict if present
                raw_llm_config = config.get("llm_config")
                llm_config = None
                if raw_llm_config is not None and not isinstance(raw_llm_config, dict):
                    llm_config = raw_llm_config
                elif isinstance(raw_llm_config, dict):
                    from quantlab.dsl.models import LLMConfig
                    llm_config = LLMConfig(**raw_llm_config)

                # Generate config with optional LLM (falls back to classic on failure)
                research_config = await self._agent.generate_config(
                    objectives=objectives,
                    market_context=market_context,
                    llm_config=llm_config,
                )

                # Serialize for context artifacts
                research_config_dict = research_config.model_dump(mode="json")
                hypotheses_dict = [
                    h.model_dump(mode="json") for h in research_config.hypotheses
                ]
                iteration_config_dict = (
                    research_config.iteration_config.model_dump(mode="json")
                )
                gate_policies_dict = [
                    g.model_dump(mode="json") for g in research_config.gate_policies
                ]

                # Write to context artifacts
                ctx.artifacts["research_config"] = research_config_dict
                ctx.artifacts["objectives"] = objectives
                ctx.artifacts["hypotheses"] = hypotheses_dict
                ctx.artifacts["iteration_config"] = iteration_config_dict
                ctx.artifacts["gate_policies"] = gate_policies_dict

                return {
                    "research_config": research_config_dict,
                    "objectives": objectives,
                    "hypotheses": hypotheses_dict,
                    "iteration_config": iteration_config_dict,
                    "gate_policies": gate_policies_dict,
                }

        class RefutationAgentStage(RefutationStage):
            """Wrapper: adapts RefutationLayer.refute() to Stage.execute()."""

            def __init__(self, **kwargs: Any) -> None:
                from quantlab.agents.refutation import RefutationLayer
                self._layer = RefutationLayer()
                super().__init__(**kwargs)

            async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
                from quantlab.dsl.models import HypothesisConfig

                raw_hypotheses = ctx.artifacts.get("hypotheses", [])
                hypotheses: list[HypothesisConfig] = [
                    HypothesisConfig(**h) if isinstance(h, dict) else h
                    for h in raw_hypotheses
                ]
                building_blocks = ctx.artifacts.get("building_blocks", [])
                strategies = ctx.artifacts.get("strategies", [])
                market_context = ctx.artifacts.get("market_context")

                result = await self._layer.refute(
                    hypotheses=hypotheses,
                    building_blocks=building_blocks,
                    market_context=market_context,
                )
                ctx.artifacts["falsation_results"] = result
                return {"falsation_results": result}

        self._stage_map.update({
            # Agent stages — concrete implementations
            "research_llm": LLMResearchAgentStage,
            "research": ResearchAgentStage,
            "hypothesis_builder": HypothesisBuilderAgentStage,
            "refutation": RefutationAgentStage,
            "builder": BuilderAgentStage,
            "analysis": AnalysisAgentStage,
            "statistics": StatisticsAgent,
            "review": ReviewerAgent,
            "monitor": MonitoringAgent,
            # Guardian evaluation
            "guardian_evaluate": GuardianEvaluationAgentStage,
            # Monte Carlo simulation
            "monte_carlo": MonteCarloStage,
            # Orchestrated flow stages (PR 3, REQ-17): concrete stages with no
            # separate agent wrapper — registered following the research_llm
            # precedent so build_from_config can instantiate them by name.
            "config_review": ConfigReviewStage,
            "retester": RetesterStage,
            "optimizer": OptimizerStage,
            "dispatch": DispatchStage,
            # Post-optimize orchestrated stages (PR 6, REQ-01 phases 9-13):
            # portfolio/compile/deploy/demo/archive. These concrete stages
            # supersede the legacy PortfolioAgent/DeployAgentStage wrappers —
            # the 14-phase flow routes through the phase engines directly.
            "portfolio": PortfolioComposeStage,
            "compile": CompileStage,
            "deploy": DeployPackageStage,
            # Ciclo 4 (REQ-05): inject IndicatorExporter into .jfx after compile.
            "indicator_export": IndicatorExportStage,
            "demo": DemoStage,
            "archive": ArchiveStage,
            # Live-ops monitoring & archive adapters (PR 3/4): execution_monitor
            # provides monitor_result for the live-ops loop; archiver builds the
            # maintenance/replacement runbook from guardian_state (REQ-33).
            "execution_monitor": ExecutionMonitorStage,
            "archiver": ArchiverStage,
            # Canonical live-ops phase (REQ-01 phase 14): starts live monitoring
            # from the archive state after the archive phase (REQ-6).
            "live_ops": LiveOpsStage,
            # Gate interceptor
            "gate": GateInterceptorStage,
            # Aliases for gate names
            "gate_human_review_objectives": GateInterceptorStage,
            "gate_human_approve_iteration": GateInterceptorStage,
            "gate_human_approve_portfolio": GateInterceptorStage,
            "gate_human_approve_deploy": GateInterceptorStage,
            "gate_human_review_performance": GateInterceptorStage,
        })

    def register(self, name: str, stage_class: type[PipelineStage]) -> None:
        """Register a stage class under a given name.

        Args:
            name: Stage name key.
            stage_class: Stage class to register.
        """
        self._stage_map[name] = stage_class
        logger.debug(f"Registered stage '{name}' -> {stage_class.__name__}")

    def get_stage_class(self, stage_name: str) -> type[PipelineStage] | None:
        """Return the stage class for a given stage name.

        Args:
            stage_name: The stage name (e.g., "validate", "research", "gate").

        Returns:
            The corresponding stage class, or None if unknown.
        """
        stage_class = self._stage_map.get(stage_name)
        if stage_class is None:
            logger.warning(
                "Unknown stage type '%s'. Available: %s",
                stage_name,
                ", ".join(sorted(self._stage_map.keys())),
            )
        return stage_class

    def list_stage_names(self) -> list[str]:
        """Return all registered stage names."""
        return list(self._stage_map.keys())

    def list_stage_names_by_type(self, stage_type: str) -> list[str]:
        """Return stage names filtered by type prefix.

        Args:
            stage_type: "builtin", "agent", or "gate".

        Returns:
            List of matching stage names.
        """
        builtin_names = {
            "validate", "translate", "cost_injection", "daemon_start", "load_config",
            "run_campaign", "poll_campaign", "campaign", "export",
            "read", "compute_stats", "knowledge_store", "report",
        }
        agent_names = {
            "research", "research_llm", "builder", "analysis", "statistics", "review",
            "portfolio", "deploy", "monitor",
        }
        gate_names = {
            "gate", "gate_human_review_objectives", "gate_human_approve_iteration",
            "gate_human_approve_portfolio", "gate_human_approve_deploy",
            "gate_human_review_performance",
        }

        if stage_type == "builtin":
            return sorted(n for n in self._stage_map if n in builtin_names)
        elif stage_type == "agent":
            return sorted(n for n in self._stage_map if n in agent_names)
        elif stage_type == "gate":
            return sorted(n for n in self._stage_map if n in gate_names)
        else:
            return sorted(self._stage_map.keys())

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
            if stage_config.type not in ("builtin", "agent", "gate"):
                raise ValueError(
                    f"Unknown stage type '{stage_config.type}' for stage '{stage_config.name}'. "
                    f"Supported types: builtin, agent, gate."
                )

            stage_class = self.get_stage_class(stage_config.name)
            if stage_class is None:
                raise ValueError(
                    f"Unknown stage '{stage_config.name}'. "
                    f"Available: {', '.join(sorted(self._stage_map.keys()))}"
                )

            # Instantiate stage with any config parameters
            stage = stage_class()
            pipeline = pipeline.then(stage)

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
