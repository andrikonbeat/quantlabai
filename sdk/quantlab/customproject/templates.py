"""Campaign templates for CustomProject DSL (REQ-22 extended).

Thin factory layer over the existing CustomProject DSL. Each template declares
an ordered task list, per-task databank routing, and optional CrossChecks
presets. The generated ``CustomProject`` instances are serializable via
``generate_cfx_archive`` and validatable against the 144/2953 goldens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    Filters,
    GoToTask,
)


@dataclass
class TemplateParams:
    """Shared parameters for campaign templates.

    Attributes:
        name: Project name emitted in the CFX ``<Project>`` root.
        databanks: Project-level databank registry. When empty, the generator
            derives one from the tasks' source/target databanks.
        filters: Default conditions applied to Filtering tasks when not
            overridden per-task.
    """

    name: str = "Campaign"
    databanks: list[DatabankSpec] = field(
        default_factory=lambda: [
            DatabankSpec(name="Results"),
            DatabankSpec(name="Last generation"),
            DatabankSpec(name="Initial population"),
            DatabankSpec(name="Strategies to improve"),
        ]
    )
    filters: list[str] | None = None


class CampaignTemplate:
    """Base class for campaign templates.

    Sub-classes declare a ``params`` class attribute with the template defaults
    and implement :meth:`build` to return a fully populated
    :class:`~quantlab.customproject.models.CustomProject`.
    """

    params: ClassVar[TemplateParams]

    @classmethod
    def build(cls, params: TemplateParams | None = None) -> CustomProject:
        """Return a ``CustomProject`` for this template.

        Args:
            params: Optional overrides; falls back to :attr:`params`.

        Returns:
            A complete ``CustomProject`` ready for ``generate_cfx_archive``.
        """
        raise NotImplementedError

    @classmethod
    def serialize(cls, output_path, params: TemplateParams | None = None):
        """Serialize this template to a ``.cfx`` archive.

        Args:
            output_path: Destination file path.
            params: Optional overrides; falls back to :attr:`params`.

        Returns:
            The resolved ``output_path``.
        """
        from quantlab.cfx.writer import CfxWriter
        from quantlab.customproject.generator import generate_cfx_archive

        project = cls.build(params)
        archive = generate_cfx_archive(project)
        CfxWriter.write(archive, output_path)
        return output_path


class StandardResearchTemplate(CampaignTemplate):
    """14-task standard research campaign.

    Task order:
    1. Build
    2. Filtering
    3. Retest (deep — Monte Carlo + WalkForward)
    4. GoToTask (loop back to Filtering on failure)
    5. Optimize
    6. AutomaticRetest
    7. AutomaticPortfolioBuilder
    8. CreatePortfolio
    9. CustomAnalysis
    10. LogDatabankStats
    11. SaveToFiles
    12. LoadFromFiles
    13. UpdateData
    14. WaitFor
    """

    params = TemplateParams(name="Standard Research")

    @classmethod
    def build(cls, params: TemplateParams | None = None) -> CustomProject:
        p = params or cls.params
        filters = Filters(conditions=p.filters) if p.filters else Filters(
            conditions=["NetProfit > 1000"]
        )
        return CustomProject(
            name=p.name,
            template_name="standard_research",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    source_databank="Initial population",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="Filtering",
                    name="Filtering",
                    source_databank="Results",
                    target_databank="Strategies to improve",
                    filters=filters,
                ),
                CustomProjectTask(
                    type="Retest",
                    name="Deep Retest",
                    source_databank="Results",
                    target_databank="Results",
                    params={
                        "monte_carlo_runs": "500",
                        "walkforward_cycles": "12",
                    },
                ),
                CustomProjectTask(
                    type="GoToTask",
                    name="Retest Loop",
                    goto=GoToTask(target="Filtering", condition="retest_failed"),
                ),
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    source_databank="Strategies to improve",
                    target_databank="Results",
                    params={
                        "walkforward_cycles": "10",
                        "optimize_params": "maxOptimizations=100",
                    },
                ),
                CustomProjectTask(
                    type="AutomaticRetest",
                    name="Automatic Retest",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="AutomaticPortfolioBuilder",
                    name="Auto Portfolio",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="CreatePortfolio",
                    name="Create Portfolio",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="CustomAnalysis",
                    name="Analysis",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="LogDatabankStats",
                    name="Log Stats",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="SaveToFiles",
                    name="Save",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="LoadFromFiles",
                    name="Load",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="UpdateData",
                    name="Update Data",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="WaitFor",
                    name="Wait",
                    source_databank="Results",
                    target_databank="Results",
                ),
            ],
            databanks=p.databanks,
        )


class QuickValidationTemplate(CampaignTemplate):
    """10-task quick validation campaign.

    Skips GoToTask and deep Retest for a lightweight validation run.
    """

    params = TemplateParams(name="Quick Validation")

    @classmethod
    def build(cls, params: TemplateParams | None = None) -> CustomProject:
        p = params or cls.params
        filters = Filters(conditions=p.filters) if p.filters else Filters(
            conditions=["NetProfit > 1000"]
        )
        return CustomProject(
            name=p.name,
            template_name="quick_validation",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    source_databank="Initial population",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="Filtering",
                    name="Filtering",
                    source_databank="Results",
                    target_databank="Strategies to improve",
                    filters=filters,
                ),
                CustomProjectTask(
                    type="Retest",
                    name="Retest",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    source_databank="Strategies to improve",
                    target_databank="Results",
                    params={
                        "walkforward_cycles": "5",
                        "optimize_params": "maxOptimizations=50",
                    },
                ),
                CustomProjectTask(
                    type="CustomAnalysis",
                    name="Analysis",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="LogDatabankStats",
                    name="Log Stats",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="SaveToFiles",
                    name="Save",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="LoadFromFiles",
                    name="Load",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="UpdateData",
                    name="Update Data",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="WaitFor",
                    name="Wait",
                    source_databank="Results",
                    target_databank="Results",
                ),
            ],
            databanks=p.databanks,
        )


class DeepRobustnessTemplate(CampaignTemplate):
    """14-task deep robustness campaign with double Retest configurations."""

    params = TemplateParams(name="Deep Robustness")

    @classmethod
    def build(cls, params: TemplateParams | None = None) -> CustomProject:
        p = params or cls.params
        filters = Filters(conditions=p.filters) if p.filters else Filters(
            conditions=["NetProfit > 1000"]
        )
        return CustomProject(
            name=p.name,
            template_name="deep_robustness",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    source_databank="Initial population",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="Filtering",
                    name="Filtering",
                    source_databank="Results",
                    target_databank="Strategies to improve",
                    filters=filters,
                ),
                CustomProjectTask(
                    type="Retest",
                    name="Retest Conservative",
                    source_databank="Results",
                    target_databank="Results",
                    params={
                        "monte_carlo_runs": "1000",
                        "walkforward_cycles": "15",
                    },
                ),
                CustomProjectTask(
                    type="Retest",
                    name="Retest Aggressive",
                    source_databank="Results",
                    target_databank="Results",
                    params={
                        "monte_carlo_runs": "500",
                        "walkforward_cycles": "8",
                    },
                ),
                CustomProjectTask(
                    type="GoToTask",
                    name="Retest Loop",
                    goto=GoToTask(target="Filtering", condition="retest_failed"),
                ),
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    source_databank="Strategies to improve",
                    target_databank="Results",
                    params={
                        "walkforward_cycles": "10",
                        "optimize_params": "maxOptimizations=100",
                    },
                ),
                CustomProjectTask(
                    type="AutomaticRetest",
                    name="Automatic Retest",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="AutomaticPortfolioBuilder",
                    name="Auto Portfolio",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="CreatePortfolio",
                    name="Create Portfolio",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="CustomAnalysis",
                    name="Analysis",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="LogDatabankStats",
                    name="Log Stats",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="SaveToFiles",
                    name="Save",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="UpdateData",
                    name="Update Data",
                    source_databank="Results",
                    target_databank="Results",
                ),
                CustomProjectTask(
                    type="WaitFor",
                    name="Wait",
                    source_databank="Results",
                    target_databank="Results",
                ),
            ],
            databanks=p.databanks,
        )


# ── Template Registry Integration (REQ-22 extended) ──────────────────────────

from quantlab.phase4.template_registry import TemplateDefinition, registry

registry.register(
    TemplateDefinition(
        name="standard_research",
        template_class=StandardResearchTemplate,
        profile="standard_research",
    )
)
registry.register(
    TemplateDefinition(
        name="quick_validation",
        template_class=QuickValidationTemplate,
        profile="quick_validation",
    )
)
registry.register(
    TemplateDefinition(
        name="deep_robustness",
        template_class=DeepRobustnessTemplate,
        profile="deep_robustness",
    )
)
