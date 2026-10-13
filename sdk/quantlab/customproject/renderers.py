"""Per-task renderers (REQ-25): CustomProjectTask → BuildTask.

Each renderer produces a ``BuildTask`` populated with the existing complex
section models (AD-2) and ``unknown_sections`` raw XML for catalog tasks
without a dedicated section model. ``CfxWriter._serialise_task`` turns the
BuildTask into the per-task ``<Settings>`` XML.

Walk-Forward renders INSIDE the Retest/Optimize ``CrossChecks`` section —
never as a standalone task (REQ-25).
"""

from __future__ import annotations

from collections.abc import Callable
from xml.sax.saxutils import escape

from quantlab.cfx.models import (
    AdvancedRankingCondition,
    AutomaticPortfolioBuilderConfig,
    BuildTask,
    CrossChecksConfig,
    DatabanksConfig,
    RankingsConfig,
    RawXmlSection,
    RetesterDataConfig,
    SettingsSection,
)
from quantlab.cfx.patcher import build_conditions_xml
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
    """Render Build task with full SQX 144/2953 dialect."""
    bt = _base_task(task)
    
    # Calibration inside Blocks
    cal_parts = []
    cal_attrs = []
    cal_attrs.append(f'calibrateBeforeStart=\"{escape(task.params.get("calibrateBeforeStart", "false"))}\"')
    cal_attrs.append(f'useMaxSteps=\"{escape(task.params.get("useMaxSteps", "false"))}\"')
    cal_attrs.append(f'maxSteps=\"{escape(task.params.get("maxSteps", "0"))}\"')
    cal_xml = f"<Blocks><Calibration {' '.join(cal_attrs)} /></Blocks>"
    
    # Options -> BuildTradingOptions -> Params
    options_raw = task.params.get("options", "")
    if options_raw:
        param_parts = []
        for chunk in options_raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" in chunk:
                key, _, value = chunk.partition("=")
                key = key.strip()
                value = value.strip()
                param_parts.append(f'    <Param key=\"{escape(key)}\" className=\"{escape(key)}\">{escape(value)}</Param>')
        params_xml = "\n".join(param_parts)
        options_xml = f"<Options><BuildTradingOptions><Params>\n{params_xml}\n</Params></BuildTradingOptions></Options>"
    else:
        options_xml = "<Options><BuildTradingOptions><Params /></BuildTradingOptions></Options>"
    
    # WhatToBuild
    wtb_attrs = []
    # Map strategyType param to type attribute
    strategy_type = task.params.get("strategyType", "")
    if strategy_type:
        wtb_attrs.append(f'type=\"{escape(strategy_type)}\"')
    for attr in ["additionalCharts", "templateFile", "improveType", "strategyFile", "improveDatabank"]:
        val = task.params.get(attr, "")
        if val:
            wtb_attrs.append(f'{attr}=\"{escape(val)}\"')
    wtb_xml = f"<WhatToBuild><StrategyType {' '.join(wtb_attrs)} /></WhatToBuild>" if wtb_attrs else "<WhatToBuild><StrategyType /></WhatToBuild>"
    
    # RiskMoneyManagement
    initial_capital = task.params.get("initialCapital", "10000")
    mm_method = task.params.get("moneyManagementMethod", "")
    mm_params_raw = task.params.get("moneyManagementParams", "")
    rm_method = task.params.get("riskManagementMethod", "")
    rm_params_raw = task.params.get("riskManagementParams", "")
    
    mm_parts = [f"    <InitialCapital>{escape(initial_capital)}</InitialCapital>"]
    if mm_method:
        mm_attrs = [f'type=\"{escape(mm_method)}\"', 'use=\"true\"']
        mm_param_parts = []
        if mm_params_raw:
            for chunk in mm_params_raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if "=" in chunk:
                    key, _, value = chunk.partition("=")
                    key = key.strip()
                    value = value.strip()
                    mm_param_parts.append(f'    <Param key=\"{escape(key)}\" className=\"{escape(key)}\">{escape(value)}</Param>')
        mm_params_xml = "\n".join(mm_param_parts) if mm_param_parts else ""
        mm_parts.append(f"    <Method {' '.join(mm_attrs)}><Params>\n{mm_params_xml}\n</Params></Method>")
    mm_xml = "\n".join(mm_parts)
    
    rm_parts = []
    if rm_method:
        rm_attrs = [f'type=\"{escape(rm_method)}\"', 'use=\"true\"']
        rm_param_parts = []
        if rm_params_raw:
            for chunk in rm_params_raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if "=" in chunk:
                    key, _, value = chunk.partition("=")
                    key = key.strip()
                    value = value.strip()
                    rm_param_parts.append(f'    <Param key=\"{escape(key)}\" className=\"{escape(key)}\">{escape(value)}</Param>')
        rm_params_xml = "\n".join(rm_param_parts) if rm_param_parts else ""
        rm_parts.append(f"    <Method {' '.join(rm_attrs)}><Params>\n{rm_params_xml}\n</Params></Method>")
    rm_xml = "\n".join(rm_parts) if rm_parts else ""
    
    rmm_xml = f"<RiskMoneyManagement><MoneyManagement>\n{mm_xml}\n</MoneyManagement>\n<RiskManagement>\n{rm_xml}\n</RiskManagement></RiskMoneyManagement>"
    
    # Combine all sections into Build unknown_section
    inner = f"{cal_xml}\n{options_xml}\n{wtb_xml}\n{rmm_xml}"
    bt.unknown_sections.append(
        RawXmlSection(name="Build", raw_xml=f"<Build>\n{inner}\n</Build>")
    )
    return bt


def render_advanced_rankings(
    conditions: list[AdvancedRankingCondition],
    *,
    extra_elements: str = "",
) -> RankingsConfig:
    """Build a ``<Rankings>`` section carrying nested ``<Conditions>`` filters.

    ``extra_elements`` is inserted before ``<Conditions>`` so a caller that also
    needs ``<MinTrades>``/``<ConfidenceLevel>`` keeps SQX's native ordering. The
    conditions themselves come from :func:`build_conditions_xml` — the same
    renderer the patcher uses — because this dialect is verified SQX evidence
    and a second implementation could drift from it unnoticed.
    """
    body = "\n".join(
        part for part in (extra_elements, build_conditions_xml(conditions)) if part
    )
    return RankingsConfig(raw_xml=f"<Rankings>\n{body}\n</Rankings>")


def render_retest(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    bt.cross_checks_section = _crosschecks_section(task)
    if task.advanced_ranking_filters:
        bt.rankings_section = render_advanced_rankings(task.advanced_ranking_filters)
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
    '<Condition use="true">'
    '<Left-Side valueType="column">'
    '<Column-Value column="NetProfit" columnType="0" format="Decimal2PL" resultType="OptProfileSysParamPermutation" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="NetProfit" />'
    "</Left-Side>"
    '<Comparator value="&gt;" />'
    '<Right-Side valueType="numeric">'
    '<Numeric-Value value="0" />'
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
    # Parsed per call so the section is typed (dialect plus sub-models) while
    # each child keeps its original markup, keeping the rendered XML unchanged.
    # Parsing per call avoids sharing one mutable model across renders.
    bt.cross_checks_section = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_CROSSCHECKS)
    bt.rankings_section = RankingsConfig(raw_xml=_AUTOMATIC_RETEST_RANKINGS)
    bt.retester_data = RetesterDataConfig(raw_xml=_AUTOMATIC_RETEST_RETESTER_DATA)
    return bt


def render_filtering(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    conditions = task.filters.conditions if task.filters else []
    inner = "\n".join(f'  <Condition value="{escape(c)}" />' for c in conditions)
    bt.unknown_sections.append(
        RawXmlSection(
            name="Conditions", raw_xml=f"<Conditions>\n{inner}\n</Conditions>"
        )
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


def render_create_portfolio(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    max_strategies = task.params.get("maxStrategies", "100")
    bt.unknown_sections.append(
        RawXmlSection(
            name="CreatePortfolio",
            raw_xml=f"<CreatePortfolio><MaxStrategies>{escape(max_strategies)}</MaxStrategies></CreatePortfolio>",
        )
    )
    return bt


def render_custom_analysis(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    fields = [
        ("PerStrategy1", task.params.get("perStrategy1", "")),
        ("PerStrategy2", task.params.get("perStrategy2", "")),
        ("FullDatabank1", task.params.get("fullDatabank1", "")),
        ("FullDatabank2", task.params.get("fullDatabank2", "")),
        ("Filter", task.params.get("filter", "")),
        ("InputArgsPerStrategy1", task.params.get("inputArgsPerStrategy1", "")),
        ("InputArgsPerStrategy2", task.params.get("inputArgsPerStrategy2", "")),
        ("InputArgsFullDatabank1", task.params.get("inputArgsFullDatabank1", "")),
        ("InputArgsFullDatabank2", task.params.get("inputArgsFullDatabank2", "")),
    ]
    inner = "\n".join(f"    <{name}>{escape(val)}</{name}>" for name, val in fields if val)
    bt.unknown_sections.append(
        RawXmlSection(name="CustomAnalysis", raw_xml=f"<CustomAnalysis>\n{inner}\n</CustomAnalysis>")
    )
    return bt


def render_log_databank_stats(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    databank = task.params.get("databank", "Results")
    log_stats_list = task.params.get("logStats", [])
    parts = [f"    <Databank>{escape(databank)}</Databank>"]
    for ls in log_stats_list:
        if not isinstance(ls, dict):
            continue
        ls_type = ls.get("type", "sum")
        column = ls.get("column", "")
        conditions = ls.get("conditions", "")
        col_xml = f"<Column>{escape(column)}</Column>" if column else ""
        cond_xml = f"<Conditions>{escape(conditions)}</Conditions>" if conditions else ""
        parts.append(f"    <LogStats type=\"{escape(ls_type)}\">{col_xml}{cond_xml}</LogStats>")
    inner = "\n".join(parts)
    bt.unknown_sections.append(
        RawXmlSection(name="LogDatabankStats", raw_xml=f"<LogDatabankStats>\n{inner}\n</LogDatabankStats>")
    )
    return bt


def render_save_to_files(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    # Simple child text fields
    simple_fields = [
        "destDirectorySqx",
        "destDirectoryStr",
        "destDirectoryDatabank",
        "destDirectoryTrades",
        "destDirectoryHtml",
        "destDirectoryPdf",
        "destDirectorySC",
        "saveInSqxFormat",
        "saveInStrFormat",
        "exportDatabank",
        "exportTrades",
        "saveInHtmlFormat",
        "saveInPdfFormat",
        "overwriteFiles",
        "mnActive",
        "mnValue",
        "data",
        "format",
        "useComma",
        "setNoteActive",
        "setNoteType",
        "setNoteCustom",
    ]
    # Mapping from param key to XML element name (per harvest evidence)
    key_to_xml = {
        "destDirectorySqx": "DestDirectorySqx",
        "destDirectoryStr": "DestDirectoryStr",
        "destDirectoryDatabank": "DestDirectoryDatabank",
        "destDirectoryTrades": "DestDirectoryTrades",
        "destDirectoryHtml": "DestDirectoryHtml",
        "destDirectoryPdf": "DestDirectoryPdf",
        "destDirectorySC": "DestDirectorySC",
        "saveInSqxFormat": "SaveInSqxFormat",
        "saveInStrFormat": "SaveInStrFormat",
        "exportDatabank": "ExportDatabank",
        "exportTrades": "ExportTrades",
        "saveInHtmlFormat": "SaveInHtmlFormat",
        "saveInPdfFormat": "SaveInPdfFormat",
        "overwriteFiles": "OverwriteFiles",
        "mnActive": "MNActive",
        "mnValue": "MNValue",
        "data": "Data",
        "format": "Format",
        "useComma": "UseComma",
        "setNoteActive": "SetNoteActive",
        "setNoteType": "SetNoteType",
        "setNoteCustom": "SetNoteCustom",
    }
    parts = []
    for key, xml_name in key_to_xml.items():
        val = task.params.get(key)
        if val is not None:
            parts.append(f"    <{xml_name}>{escape(str(val))}</{xml_name}>")
    # SaveSourceCode with attributes
    ssc_val = task.params.get("saveSourceCode")
    if ssc_val is not None:
        ssc_type = task.params.get("saveSourceCodeType", "source")
        ssc_format = task.params.get("saveSourceCodeFormat", "text")
        parts.append(
            f'    <SaveSourceCode type=\"{escape(ssc_type)}\" format=\"{escape(ssc_format)}\">{escape(str(ssc_val))}</SaveSourceCode>'
        )
    inner = "\n".join(parts)
    bt.unknown_sections.append(
        RawXmlSection(name="SaveToFiles", raw_xml=f"<SaveToFiles>\n{inner}\n</SaveToFiles>")
    )
    return bt


def render_load_from_files(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    key_to_xml = {
        "sourceDirectory": "SourceDirectory",
        "includeSubdirectories": "IncludeSubdirectories",
        "unrecognizedInstrumentAction": "UnrecognizedInstrumentAction",
        "unrecognizedInstrumentValue": "UnrecognizedInstrumentValue",
    }
    parts = []
    for key, xml_name in key_to_xml.items():
        val = task.params.get(key)
        if val is not None:
            parts.append(f"    <{xml_name}>{escape(str(val))}</{xml_name}>")
    inner = "\n".join(parts)
    bt.unknown_sections.append(
        RawXmlSection(name="LoadFromFiles", raw_xml=f"<LoadFromFiles>\n{inner}\n</LoadFromFiles>")
    )
    return bt


def render_update_data(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    type_val = task.params.get("type", "project")
    bt.unknown_sections.append(
        RawXmlSection(
            name="UpdateData",
            raw_xml=f"<UpdateData><Type>{escape(type_val)}</Type></UpdateData>",
        )
    )
    return bt


def render_wait_for(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    file_val = task.params.get("file", "")
    action_val = task.params.get("action", "user")
    parts = []
    if file_val:
        parts.append(f"    <File>{escape(file_val)}</File>")
    parts.append(f"    <Action>{escape(action_val)}</Action>")
    inner = "\n".join(parts)
    bt.unknown_sections.append(
        RawXmlSection(name="WaitFor", raw_xml=f"<WaitFor>\n{inner}\n</WaitFor>")
    )
    return bt


def render_delete_file(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    file_val = task.params.get("file", "")
    bt.unknown_sections.append(
        RawXmlSection(
            name="DeleteFile",
            raw_xml=f"<DeleteFile><File>{escape(file_val)}</File></DeleteFile>",
        )
    )
    return bt


def render_notification(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    type_val = task.params.get("type", "email")
    email_val = task.params.get("email", "")
    wait_val = task.params.get("wait", "false")
    bt.unknown_sections.append(
        RawXmlSection(
            name="Notification",
            raw_xml=f"<Notification><Type>{escape(type_val)}</Type><Email>{escape(email_val)}</Email><Wait>{escape(wait_val)}</Wait></Notification>",
        )
    )
    return bt


def render_call_external_script(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    file_val = task.params.get("file", "")
    params_val = task.params.get("params", "")
    waitfor_val = task.params.get("waitfor", "end")
    hours_val = task.params.get("hours", "0")
    minutes_val = task.params.get("minutes", "0")
    bt.unknown_sections.append(
        RawXmlSection(
            name="CallExternalScript",
            raw_xml=f"<CallExternalScript><File params=\"{escape(params_val)}\">{escape(file_val)}</File><WaitFor hours=\"{escape(hours_val)}\" minutes=\"{escape(minutes_val)}\">{escape(waitfor_val)}</WaitFor></CallExternalScript>",
        )
    )
    return bt


def render_stop_and_start(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    project_name = task.params.get("projectName", "")
    start_another = task.params.get("startAnother", "false")
    skip_to_first = task.params.get("skipToFirstProject", "true")
    bt.unknown_sections.append(
        RawXmlSection(
            name="StopAndStart",
            raw_xml=f"<StopAndStart><StartProject use=\"{escape(start_another)}\" skipToFirstProject=\"{escape(skip_to_first)}\">{escape(project_name)}</StartProject><Conditions /></StopAndStart>",
        )
    )
    return bt


def render_clear_databanks(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    databanks = task.params.get("databanks", ["Results"])
    if isinstance(databanks, str):
        databanks = [d.strip() for d in databanks.split(",") if d.strip()]
    parts = [f'    <Databank name=\"{escape(db)}\" />' for db in databanks]
    inner = "\n".join(parts)
    bt.unknown_sections.append(
        RawXmlSection(name="ClearDatabanks", raw_xml=f"<ClearDatabanks>\n{inner}\n</ClearDatabanks>")
    )
    return bt


def render_apply_mass_config(task: CustomProjectTask) -> BuildTask:
    bt = _base_task(task)
    load_from_type = task.params.get("loadFromType", "project")
    load_from_file = task.params.get("loadFromFile", "")
    load_from_task = task.params.get("loadFromTask", "")
    what_to_apply = task.params.get("whatToApply", {})
    target_tasks = task.params.get("targetTasks", "")
    
    load_from_xml = f"<LoadFrom><Type>{escape(load_from_type)}</Type><File>{escape(load_from_file)}</File><Task>{escape(load_from_task)}</Task></LoadFrom>"
    
    wta_parts = []
    if isinstance(what_to_apply, dict):
        for key, val in what_to_apply.items():
            # Capitalize first letter for XML element name per SQX dialect
            xml_name = key[:1].upper() + key[1:] if key else key
            wta_parts.append(f"    <{xml_name}>{escape(str(val))}</{xml_name}>")
    what_to_apply_xml = "<WhatToApply>\n" + "\n".join(wta_parts) + "\n</WhatToApply>" if wta_parts else "<WhatToApply />"
    
    inner = f"{load_from_xml}\n{what_to_apply_xml}\n    <TargetTasks>{escape(target_tasks)}</TargetTasks>"
    bt.unknown_sections.append(
        RawXmlSection(name="ApplyMassConfig", raw_xml=f"<ApplyMassConfig>\n{inner}\n</ApplyMassConfig>")
    )
    return bt


def render_generic(task: CustomProjectTask) -> BuildTask:
    """Fallback for types not yet implemented (NeuralNetworkTrainer)."""
    bt = _base_task(task)
    bt.unknown_sections.append(
        RawXmlSection(
            name=task.type,
            raw_xml=f'<{task.type} />',
        )
    )
    return bt


# Task types without a dedicated renderer use the generic one.
_GENERIC_TYPES = frozenset(
    {
        "NeuralNetworkTrainer",
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
    "CreatePortfolio": render_create_portfolio,
    "CustomAnalysis": render_custom_analysis,
    "LogDatabankStats": render_log_databank_stats,
    "SaveToFiles": render_save_to_files,
    "LoadFromFiles": render_load_from_files,
    "UpdateData": render_update_data,
    "WaitFor": render_wait_for,
    "DeleteFile": render_delete_file,
    "Notification": render_notification,
    "CallExternalScript": render_call_external_script,
    "StopAndStart": render_stop_and_start,
    "ClearDatabanks": render_clear_databanks,
    "ApplyMassConfig": render_apply_mass_config,
}

for _t in _GENERIC_TYPES:
    RENDERERS[_t] = render_generic

assert len(RENDERERS) == 21, f"expected 21 renderers, got {len(RENDERERS)}"
