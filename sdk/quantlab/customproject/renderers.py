"""Per-task renderers (REQ-25): CustomProjectTask → BuildTask.

Each renderer produces a ``BuildTask`` populated with the existing complex
section models (AD-2) and ``unknown_sections`` raw XML for catalog tasks
without a dedicated section model. ``CfxWriter._serialise_task`` turns the
BuildTask into the per-task ``<Settings>`` XML.

Walk-Forward renders INSIDE the Retest/Optimize ``CrossChecks`` section —
never as a standalone task (REQ-25).
"""

from __future__ import annotations

from typing import Callable
from xml.sax.saxutils import escape

from quantlab.cfx.models import (
    AutomaticPortfolioBuilderConfig,
    BuildTask,
    CrossChecksConfig,
    DatabanksConfig,
    RawXmlSection,
    SettingsSection,
)
from quantlab.customproject.models import CustomProjectTask, GoToTask


def _databanks_section(task: CustomProjectTask) -> DatabanksConfig | None:
    """Per-task databank routing: only this task's own source/target databanks.

    Emits the SQX-native ``<Databanks>`` dialect (verified in the 144/2953
    golden task XMLs): ``<Databank label="Input databank" name="Input"
    value="{source}"/>`` and ``<Databank label="Output databank"
    name="Output" value="{target}"/>``. Only the task's own databanks appear,
    so no databank is shared implicitly across tasks (REQ-22 scenario 3).
    """
    entries: list[str] = []
    if task.source_databank:
        entries.append(
            f'<Databank label="Input databank" name="Input" '
            f'value="{escape(task.source_databank)}" />'
        )
    if task.target_databank:
        entries.append(
            f'<Databank label="Output databank" name="Output" '
            f'value="{escape(task.target_databank)}" />'
        )
    if not entries:
        return None
    inner = "\n".join(f"    {e}" for e in entries)
    return DatabanksConfig(raw_xml=f"<Databanks>\n{inner}\n  </Databanks>")


def _crosschecks_section(task: CustomProjectTask) -> CrossChecksConfig:
    """CrossChecks for Retest/Optimize; Walk-Forward lives here (REQ-25)."""
    enabled = "true" if "walkforward_cycles" in task.params else "false"
    cycles = task.params.get("walkforward_cycles", "5")
    return CrossChecksConfig(
        raw_xml=(
            "<CrossChecks>"
            f'<WalkForward enabled="{enabled}" cycles="{cycles}" />'
            "</CrossChecks>"
        )
    )


def _base_task(task: CustomProjectTask) -> BuildTask:
    """Common scaffolding: databank routing section for every task."""
    bt = BuildTask()
    bt.databanks_section = _databanks_section(task)
    return bt


def render_build(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    bt.options = SettingsSection(name="Options", settings={})
    bt.data = SettingsSection(name="Data", settings={})
    return bt


def render_retest(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    bt.cross_checks_section = _crosschecks_section(task)
    return bt


def render_optimize(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    bt.cross_checks_section = _crosschecks_section(task)
    return bt


def render_automatic_portfolio_builder(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    bt.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(
        raw_xml="<AutomaticPortfolioBuilder><SearchType>bruteforce</SearchType>"
        "<MinStrategies>2</MinStrategies><MaxStrategies>8</MaxStrategies>"
        "</AutomaticPortfolioBuilder>"
    )
    return bt


def render_filtering(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    conditions = task.filters.conditions if task.filters else []
    inner = "\n".join(f'  <Condition value="{escape(c)}" />' for c in conditions)
    bt.unknown_sections.append(
        RawXmlSection(name="Conditions", raw_xml=f"<Conditions>\n{inner}\n</Conditions>")
    )
    return bt


def render_goto_task(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    goto: GoToTask = task.goto or GoToTask(target="")
    attrs = f'target="{escape(goto.target)}"'
    if goto.condition:
        attrs += f' condition="{escape(goto.condition)}"'
    bt.unknown_sections.append(
        RawXmlSection(name="GoToTask", raw_xml=f"<GoToTask {attrs} />")
    )
    return bt


def render_generic(task: CustomProjectTask) -> BuildTask:
    """Generic catalog task: typed section name + minimal settings (AD-2)."""
    bt = _base_task(task)
    bt.unknown_sections.append(
        RawXmlSection(
            name=task.type,
            raw_xml=f'<{task.type} enabled="true" />',
        )
    )
    return bt


# Task types without a dedicated renderer use the generic one.
_GENERIC_TYPES = frozenset(
    {
        "AutomaticRetest",
        "LoadFromFiles",
        "SaveToFiles",
        "ClearDatabanks",
        "CreatePortfolio",
        "CustomAnalysis",
        "DeleteFile",
        "CallExternalScript",
        "LogDatabankStats",
        "NeuralNetworkTrainer",
        "Notification",
        "StopAndStart",
        "UpdateData",
        "WaitFor",
        "ApplyMassConfig",
    }
)

RENDERERS: dict[str, Callable[[CustomProjectTask], BuildTask]] = {
    "Build": render_build,
    "Retest": render_retest,
    "Optimize": render_optimize,
    "AutomaticPortfolioBuilder": render_automatic_portfolio_builder,
    "Filtering": render_filtering,
    "GoToTask": render_goto_task,
}

for _t in _GENERIC_TYPES:
    RENDERERS[_t] = render_generic

assert len(RENDERERS) == 21, f"expected 21 renderers, got {len(RENDERERS)}"
