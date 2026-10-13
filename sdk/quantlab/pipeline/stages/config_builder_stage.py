"""Config Builder Stage — generates CFX from ExplorationDecision (REQ-22, REQ-43/44).

This stage sits at the beginning of the orchestrated pipeline (config phase)
and translates the ExplorationDecision into a fully-parameterized CFX archive
ready for SQX execution.

Pipeline position: after hypothesis_builder, before builder (config phase).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quantlab.campaign.delegation import PhaseResult
from quantlab.customproject.param_mapper import (
    CustomProjectParamMapper,
    create_customproject_param_mapper,
)
from quantlab.customproject.generator import generate_cfx_archive
from quantlab.exploration.models import ExplorationDecision
from quantlab.pipeline.base import PipelineContext, Stage
from quantlab.pipeline.config import StageConfig

logger = logging.getLogger(__name__)


class ConfigBuilderConfig:
    """Configuration for ConfigBuilderStage."""

    def __init__(
        self,
        template_name: str = "standard_research",
        output_dir: str = "cfx_output",
        custom_rules: list[tuple] | None = None,
    ):
        self.template_name = template_name
        self.output_dir = output_dir
        self.custom_rules = custom_rules


class ConfigBuilderStage(Stage):
    """Pipeline stage that builds CFX from ExplorationDecision.

    This stage:
    1. Takes ExplorationDecision from pipeline context
    2. Uses ParamMapper to generate parameterized CustomProject
    3. Generates CFX archive via CfxWriter
    4. Stores CFX path in context for downstream stages
    """

    name = "config_builder"
    requires = ["exploration_decision"]
    provides = ["cfx_path", "project_name", "template_name"]

    def __init__(self, config: ConfigBuilderConfig | None = None):
        self._config = config or ConfigBuilderConfig()
        self._param_mapper = None  # Lazy initialization

    @property
    def config(self) -> 'ConfigBuilderConfig':
        return self._config

    @config.setter
    def config(self, value: 'ConfigBuilderConfig'):
        self._config = value

    def _get_param_mapper(self):
        """Lazy initialization of param mapper."""
        if self._param_mapper is None:
            from quantlab.customproject.param_mapper import create_customproject_param_mapper
            self._param_mapper = create_customproject_param_mapper(
                template_name=self.config.template_name,
                custom_rules=self.config.custom_rules,
            )
        return self._param_mapper

    async def _execute_impl(self, ctx: "PipelineContext") -> dict[str, Any]:
        """Internal implementation of config builder."""
        campaign_id = ctx.config.get("campaign_id", "unknown")
        logger.info("Starting config builder for campaign %s", campaign_id)

        # Extract ExplorationDecision from context artifacts
        exploration = ctx.artifacts.get("exploration_decision")
        if not exploration:
            logger.error("No ExplorationDecision found in context artifacts")
            return {"error": "No ExplorationDecision found in context"}

        # Parse ExplorationDecision if it's a dict
        if isinstance(exploration, dict):
            from quantlab.exploration.models import ExplorationDecision
            exploration = ExplorationDecision(**exploration)

        logger.info("Building CFX for campaign %s with template %s",
                    campaign_id, self.config.template_name)

        # Create output directory
        output_dir = Path(self.config.output_dir) / exploration.exploration_id
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from quantlab.customproject.param_mapper import create_customproject_param_mapper
            from quantlab.customproject.templates import TemplateSelector, TemplateParams
            from quantlab.customproject.models import DatabankSpec

            param_mapper = self._get_param_mapper()

            # Get template class
            template_class = self._get_template_class(self.config.template_name)

            # Build template params from exploration
            template_params = self._build_template_params(exploration)

            # Build base project from template
            base_project = template_class.build(template_params)

            # Map exploration to task parameters
            task_params = self._get_param_mapper().param_mapper.map(exploration, base_project.tasks)

            # Apply mapped parameters to project tasks
            for task in base_project.tasks:
                if task.name in task_params:
                    task.params = task_params[task.name]

            # Store exploration decision in guardian_state for downstream stages
            if base_project.guardian_state is None:
                base_project.guardian_state = {}
            base_project.guardian_state["exploration_decision"] = exploration.model_dump()

            # Generate CFX archive
            cfx_path = Path(self.config.output_dir) / exploration.exploration_id / f"{exploration.exploration_id}.cfx"
            cfx_path.parent.mkdir(parents=True, exist_ok=True)

            from quantlab.customproject.generator import generate_cfx_archive
            generate_cfx_archive(base_project, cfx_path)

            logger.info("CFX generated at %s", cfx_path)

            return {
                "cfx_path": str(cfx_path),
                "project_name": exploration.exploration_id,
                "template": self.config.template_name,
                "task_params": task_params,
            }

        except Exception as exc:
            logger.exception("Config builder failed for campaign %s", campaign_id)
            return {"error": str(exc)}

    def _get_template_class(self, template_name: str):
        """Get template class by name."""
        from quantlab.customproject.templates import TemplateSelector
        return TemplateSelector.select(template_name)

    def _build_template_params(self, exploration) -> 'TemplateParams':
        """Build TemplateParams from ExplorationDecision."""
        from quantlab.customproject.templates import TemplateParams
        from quantlab.customproject.models import DatabankSpec

        return TemplateParams(
            name=exploration.exploration_id,
            databanks=[
                DatabankSpec(name="Results"),
                DatabankSpec(name="Last generation"),
                DatabankSpec(name="Initial population"),
                DatabankSpec(name="Strategies to improve"),
            ],
            filters=None,
        )

    async def execute(self, ctx: "PipelineContext") -> Any:
        """Execute the config builder stage.

        This is the main entry point required by the Stage ABC.
        """
        result = await self._execute_impl(ctx)

        if "error" in result:
            from quantlab.campaign.delegation import PhaseResult
            return PhaseResult(
                phase_id="config",
                status="failed",
                executive_summary=f"Config builder failed: {result['error']}",
                artifacts={},
                next_recommended="config",
                risks=[result["error"]],
            )

        return PhaseResult(
            phase_id="config",
            status="success",
            executive_summary=f"CFX generated for campaign {ctx.config.get('campaign_id', 'unknown')}",
            artifacts=result,
            next_recommended="builder",
            risks=[],
            evidence={"task_params_count": len(result.get("task_params", {}))},
        )


def create_config_builder_stage(config: 'ConfigBuilderConfig' | None = None) -> 'ConfigBuilderStage':
    """Factory function to create a ConfigBuilderStage."""
    return ConfigBuilderStage(config)