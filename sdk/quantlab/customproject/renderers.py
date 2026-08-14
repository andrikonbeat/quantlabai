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
    RankingsConfig,
    RawXmlSection,
    RetesterDataConfig,
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


def _param_attrs(raw: str) -> str:
    """Turn ``key=value`` pairs into quoted XML attributes (REQ-44).

    ``"maxOptimizations=100,population=50"`` →
    ``maxOptimizations="100" population="50"``
    """
    parts: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            parts.append(f'{key.strip()}="{value.strip()}"')
        else:
            parts.append(chunk)
    return " ".join(parts)


def _crosschecks_section(task: CustomProjectTask) -> CrossChecksConfig:
    """CrossChecks for Retest/Optimize (REQ-25, REQ-43/44).

    Walk-Forward always renders here — never as a standalone task (REQ-25).
    Monte Carlo (Retest, REQ-43) renders enabled only when ``monte_carlo_runs``
    is configured; parameter ranges (Optimize, REQ-44) render from
    ``optimize_params``. Disabled elements stay present so a harness change
    can never silently drop a cross-check.
    """
    enabled = "true" if "walkforward_cycles" in task.params else "false"
    cycles = task.params.get("walkforward_cycles", "5")
    parts = ["<CrossChecks>"]

    mc_runs = task.params.get("monte_carlo_runs")
    mc_attr = 'enabled="false"'
    if mc_runs is not None:
        mc_attr = f'enabled="true" simulations="{mc_runs}"'
    parts.append(f"<MonteCarlo {mc_attr} />")

    opt = task.params.get("optimize_params")
    if opt is not None:
        parts.append(f'<Parameters enabled="true" {_param_attrs(opt)} />')
    else:
        parts.append('<Parameters enabled="false" />')

    parts.append(f'<WalkForward enabled="{enabled}" cycles="{cycles}" />')
    parts.append("</CrossChecks>")
    return CrossChecksConfig(raw_xml="".join(parts))


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


# ── AutomaticRetest dedicated renderer (WU-2) ────────────────────────────────
#
# The CrossChecks / Rankings / RetesterData XML below is the verified SQX
# 144/2953 AutomaticRetest dialect (mirrors the sections the Adaptive Retest
# Agent applies at runtime). Generic <MonteCarlo>/<WalkForward> standalone
# elements must NOT appear — AutomaticRetest uses the RetestWithHigherPrecision
# / MonteCarloRetest / WalkForwardOptimization family instead.

_AUTOMATIC_RETEST_CROSSCHECKS = (
    '<CrossChecks use="true">'
    '<RetestWithHigherPrecision use="false">'
    "<Settings><Precision>4</Precision><Spread>2</Spread></Settings>"
    "<AcceptanceSettings><Conditions /></AcceptanceSettings>"
    "</RetestWithHigherPrecision>"
    '<MonteCarloRetest use="false">'
    "<Settings>"
    "<Methods>"
    '<Method use="true" type="RandomizeHistoryData">'
    "<Params>"
    '<Param key="Probability" type="Integer">20</Param>'
    '<Param key="MaxChange" type="Integer">10</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomizeMinDistance">'
    "<Params>"
    '<Param key="Min" type="Double">0.0</Param>'
    '<Param key="Max" type="Double">10.0</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomizeSlippage">'
    "<Params>"
    '<Param key="Min" type="Double">0.0</Param>'
    '<Param key="Max" type="Double">5.0</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomizeSpread">'
    "<Params>"
    '<Param key="Min" type="Double">1.0</Param>'
    '<Param key="Max" type="Double">5.0</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomizeStartingBar">'
    "<Params>"
    '<Param key="MaxChange" type="Integer">100</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomizeStrategyParameters">'
    "<Params>"
    '<Param key="Probability" type="Integer">10</Param>'
    '<Param key="MaxChange" type="Integer">20</Param>'
    '<Param key="Symmetric" type="Boolean">true</Param>'
    "</Params>"
    "</Method>"
    "</Methods>"
    "<NumberOfSimulations>100</NumberOfSimulations>"
    "</Settings>"
    "<AcceptanceSettings><Conditions/></AcceptanceSettings>"
    "</MonteCarloRetest>"
    '<MonteCarloManipulation use="false">'
    "<Settings>"
    "<Methods>"
    '<Method use="true" type="RandomizeTradesOrder">'
    "<Params>"
    '<Param key="Method" type="String">resampling</Param>'
    "</Params>"
    "</Method>"
    '<Method use="true" type="RandomlySkipTrades">'
    "<Params>"
    '<Param key="Probability" type="Integer">10</Param>'
    "</Params>"
    "</Method>"
    "</Methods>"
    "<NumberOfSimulations>100</NumberOfSimulations>"
    "</Settings>"
    "<AcceptanceSettings><Conditions /></AcceptanceSettings>"
    "</MonteCarloManipulation>"
    '<RetestOnAdditionalMarkets use="false">'
    "<Settings><Setups/></Settings>"
    "<AcceptanceSettings><Conditions /></AcceptanceSettings>"
    "</RetestOnAdditionalMarkets>"
    '<WalkForwardOptimization use="false">'
    "<Settings>"
    '<WalkForward type="1" period="20" optimization="15">'
    '<Param1 value="18" /><Param2 value="10" />'
    "</WalkForward>"
    "<OptimizePeriods>true</OptimizePeriods>"
    "<OptimizeExitTypes>true</OptimizeExitTypes>"
    "</Settings>"
    "<AcceptanceSettings>"
    '<Conditions CrossCheck="WalkForwardOptimization" thresholdPct="50" />'
    "</AcceptanceSettings>"
    "</WalkForwardOptimization>"
    '<WalkForwardMatrix use="false">'
    "<Settings>"
    '<WalkForward type="1" period="20" optimization="25">'
    '<Param1 value="undefined" start="10" stop="40" step="10" />'
    '<Param2 value="undefined" start="5" stop="20" step="5" />'
    "</WalkForward>"
    "<OptimizePeriods>true</OptimizePeriods>"
    "<OptimizeExitTypes>true</OptimizeExitTypes>"
    "</Settings>"
    "<AcceptanceSettings>"
    '<Conditions thresholdPct="50" CrossCheck="WalkForwardMatrix" />'
    "</AcceptanceSettings>"
    "</WalkForwardMatrix>"
    '<OptProfileSysParamPermutation use="false">'
    "<Settings>"
    "<MaxTests>1000</MaxTests>"
    '<WhatToParametrize type="0" symmetricVariables="false">'
    "<Recommended>true</Recommended>"
    "<Periods>false</Periods>"
    "<Shifts>false</Shifts>"
    "<Constants>false</Constants>"
    "<OtherParams>false</OtherParams>"
    "<EntryParams>false</EntryParams>"
    "<EntryLogic>false</EntryLogic>"
    "<ExitParamsUsed>false</ExitParamsUsed>"
    "<ExitParamsUnused>false</ExitParamsUnused>"
    "<BooleanParams>false</BooleanParams>"
    "</WhatToParametrize>"
    "</Settings>"
    "<AcceptanceSettings>"
    "<ProfitOptPct>30</ProfitOptPct>"
    "<AvgProfit>0</AvgProfit>"
    "<UniformDistrChanges>5</UniformDistrChanges>"
    "<StdevAvgProfit>1</StdevAvgProfit>"
    "<EvalProfitOptCheck>true</EvalProfitOptCheck>"
    "<EvalAvgProfitCheck>true</EvalAvgProfitCheck>"
    "<EvalUniformDistrCheck>true</EvalUniformDistrCheck>"
    "<EvalTopProfitCheck>true</EvalTopProfitCheck>"
    "<Conditions>"
    "<Condition use=\"true\">"
    "<Left-Side valueType=\"column\">"
    '<Column-Value column="NetProfit" columnType="0" format="Decimal2PL" resultType="OptProfileSysParamPermutation" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="NetProfit" />'
    "</Left-Side>"
    "<Comparator value=\"&gt;\" />"
    "<Right-Side valueType=\"numeric\">"
    "<Numeric-Value value=\"0\" />"
    "</Right-Side>"
    "</Condition>"
    "</Conditions>"
    "</AcceptanceSettings>"
    "</OptProfileSysParamPermutation>"
    "</CrossChecks>"
)

_AUTOMATIC_RETEST_RANKINGS = (
    "<Rankings>"
    "<MaxStrategies>100</MaxStrategies>"
    '<FitnessCriteria method="ComputeFromStrategyResult">'
    "<Settings>"
    '<Ranking type="ReturnDDRatio" />'
    "</Settings>"
    "</FitnessCriteria>"
    "<ConditionsType>1</ConditionsType>"
    "<Conditions />"
    "<AutomaticDismissal>"
    '<Problem code="1" dismiss="false" />'
    '<Problem code="4" dismiss="false" />'
    '<Problem code="1024" dismiss="false" />'
    '<Problem code="16" dismiss="false" />'
    '<Problem code="32" dismiss="false" />'
    '<Problem code="64" dismiss="false" />'
    '<Problem code="256" dismiss="false" />'
    '<Problem code="2" dismiss="false" />'
    '<Problem code="512" dismiss="false" />'
    '<Problem code="8" dismiss="false" />'
    "</AutomaticDismissal>"
    '<StopCondition type="never" passedStrategies="1000" restartCount="5" days="0" hours="0" minutes="0" />'
    "</Rankings>"
)

_AUTOMATIC_RETEST_RETESTER_DATA = (
    "<RetesterData>"
    "<MonteCarloRuns>500</MonteCarloRuns>"
    "<WalkForwardCycles>10</WalkForwardCycles>"
    "<ConfidenceLevel>0.95</ConfidenceLevel>"
    "<MinTrades>30</MinTrades>"
    "<MCPercentile>95</MCPercentile>"
    "<Databanks>"
    '<Databank label="Input databank" name="Input" value="Results" />'
    '<Databank label="Output databank" name="Output" value="Results" />'
    "</Databanks>"
    "</RetesterData>"
)


def render_automatic_retest(task: CustomProjectTask) -> BuildTask:
    """Render an AutomaticRetest task with its dedicated sections (WU-2).

    Produces the SQX 144/2953 AutomaticRetest dialect: CrossChecks with the
    RetestWithHigherPrecision / MonteCarloRetest / WalkForwardOptimization
    family (never standalone ``<MonteCarlo>``/``<WalkForward>`` elements),
    Rankings, and RetesterData.
    """
    bt = _base_task(task)
    bt.cross_checks_section = CrossChecksConfig(raw_xml=_AUTOMATIC_RETEST_CROSSCHECKS)
    bt.rankings_section = RankingsConfig(raw_xml=_AUTOMATIC_RETEST_RANKINGS)
    bt.retester_data = RetesterDataConfig(raw_xml=_AUTOMATIC_RETEST_RETESTER_DATA)
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
    "AutomaticRetest": render_automatic_retest,
    "AutomaticPortfolioBuilder": render_automatic_portfolio_builder,
    "Filtering": render_filtering,
    "GoToTask": render_goto_task,
}

for _t in _GENERIC_TYPES:
    RENDERERS[_t] = render_generic

assert len(RENDERERS) == 21, f"expected 21 renderers, got {len(RENDERERS)}"
