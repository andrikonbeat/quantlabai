"""Template-aware Parameter Mapper for CustomProject (REQ-22, REQ-43/44).

This module bridges the ExplorationDecision → CustomProject parameter mapping
with template-aware logic. It takes an ExplorationDecision and a template,
and produces a fully-parameterized CustomProject ready for CFX generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quantlab.customproject.models import CustomProject, CustomProjectTask
from quantlab.exploration.models import ExplorationDecision
from quantlab.exploration.param_mapper import ParamMapper, create_param_mapper
from quantlab.exploration.params_schema import TaskType
from quantlab.customproject.templates import PortfolioState


@dataclass
class MappingResult:
    """Result of parameter mapping for a CustomProject."""
    project: 'CustomProject'
    task_params: dict[str, dict[str, Any]]  # task_name -> {param: value}
    warnings: list[str] = field(default_factory=list)


class CustomProjectParamMapper:
    """Template-aware parameter mapper for CustomProject.

    Takes an ExplorationDecision and a portfolio state, applies the ParamMapper
    to each task in the template, and returns a fully-parameterized CustomProject.
    """

    def __init__(
        self,
        portfolio_state: PortfolioState = PortfolioState.NORMAL,
        custom_rules: list[tuple] | None = None,
    ):
        from quantlab.customproject.templates import TemplateSelector
        template_class = TemplateSelector.select(portfolio_state)
        template_name = template_class.build().template_name or "standard_research"
        
        self.param_mapper = create_param_mapper(
            template_name=template_name,
            custom_rules=custom_rules,
        )
        self.portfolio_state = portfolio_state

    def map_exploration_to_project(
        self,
        exploration: ExplorationDecision,
        params: dict[str, Any] | None = None,
    ) -> MappingResult:
        """Map ExplorationDecision to a fully-parameterized CustomProject.

        Args:
            exploration: The ExplorationDecision artifact from Bloque B
            params: Optional template parameter overrides (TemplateParams)

        Returns:
            MappingResult with parameterized CustomProject and per-task params
        """
        from quantlab.customproject.templates import TemplateParams, TemplateSelector
        from quantlab.customproject.models import CustomProject

        # Get template class
        template_class = TemplateSelector.select(self.portfolio_state)
        template_params = params or TemplateParams()

        # Build base project from template
        base_project = template_class.build(params)

        # Map exploration to per-task parameters
        task_params = self.param_mapper.map(exploration, base_project.tasks)

        # Apply mapped parameters to project tasks
        warnings = []
        for task in base_project.tasks:
            if task.name in task_params:
                task.params = task_params[task.name]
            else:
                # Task not in mapping - use defaults
                pass

        # Store exploration decision in guardian_state for downstream stages
        if base_project.guardian_state is None:
            base_project.guardian_state = {}
        base_project.guardian_state["exploration_decision"] = exploration.model_dump()

        return MappingResult(
            project=base_project,
            task_params=task_params,
            warnings=[],
        )

    def map_exploration_to_dict(
        self,
        exploration: ExplorationDecision,
    ) -> dict[str, dict[str, Any]]:
        """Map ExplorationDecision to per-task parameter dict (for inspection/testing).

        Args:
            exploration: The ExplorationDecision artifact

        Returns:
            Dict mapping task_name -> {param: value}
        """
        # Create a temporary project from template to get task structure
        from quantlab.customproject.templates import TemplateSelector, TemplateParams
        template_class = TemplateSelector.select(self.portfolio_state)
        base_project = template_class.build(TemplateParams())

        return self.param_mapper.map(exploration, base_project.tasks)


def create_customproject_param_mapper(
    portfolio_state = None,
    custom_rules: list[tuple] | None = None,
) -> CustomProjectParamMapper:
    """Factory function to create a CustomProjectParamMapper."""
    from quantlab.customproject.templates import PortfolioState
    if portfolio_state is None:
        portfolio_state = PortfolioState.NORMAL
    return CustomProjectParamMapper(
        portfolio_state=portfolio_state,
        custom_rules=custom_rules,
    )


# Convenience function for direct mapping
def map_exploration_to_customproject(
    exploration: ExplorationDecision,
    portfolio_state = None,
    custom_rules: list[tuple] | None = None,
) -> 'CustomProject':
    """One-shot function to map ExplorationDecision to parameterized CustomProject.

    Args:
        exploration: The ExplorationDecision artifact
        portfolio_state: Portfolio state (NORMAL, VIGILANCE, RECOVERY, DEFENSIVE, QUARANTINE)
        custom_rules: Optional custom mapping rules

    Returns:
        Fully parameterized CustomProject ready for CFX generation
    """
    from quantlab.customproject.templates import PortfolioState
    if portfolio_state is None:
        portfolio_state = PortfolioState.NORMAL
    mapper = create_customproject_param_mapper(portfolio_state, custom_rules)
    result = mapper.map_exploration_to_project(exploration)
    return result.project