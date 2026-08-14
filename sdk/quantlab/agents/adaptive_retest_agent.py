"""Adaptive Retest Agent — selects retest mode from CFX runtime signals.

Reads CFX archives, extracts runtime signals, and applies adaptive mutations
to switch between ``AutomaticRetest`` and full ``Retest`` configurations via
``CfxWriter`` round-trips.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from quantlab.cfx.models import (
    BuildTask,
    CfxArchive,
    CrossChecksConfig,
    DatabanksConfig,
    RankingsConfig,
    RetesterDataConfig,
)
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter


class RetestMode(str, Enum):
    """Retest mode variants."""

    AUTOMATIC_RETEST = "AutomaticRetest"
    RETEST = "Retest"


@dataclass
class RetestSignals:
    """Runtime signals extracted from a CFX archive."""

    last_run_status: str | None = None
    trade_count: int | None = None
    monte_carlo_passed: bool | None = None
    walkforward_passed: bool | None = None
    databank_coverage: float | None = None


def inspect_cfx_signals(cfx_path: Path) -> RetestSignals:
    """Read a .cfx archive and extract runtime signals WITHOUT modifying it.

    Inspection is strictly read-only: the archive file hash is unchanged after
    this call.

    Args:
        cfx_path: Path to the .cfx archive.

    Returns:
        ``RetestSignals`` with extracted values. Missing optional signals are
        ``None``.
    """
    archive = CfxReader.read(cfx_path)
    config = archive.config

    signals = RetestSignals()

    # Project metadata → last_run_status (checked before task so it works
    # even for archives with no tasks).
    if hasattr(config, "metadata") and config.metadata:
        signals.last_run_status = config.metadata.get("last_run_status")

    if hasattr(config, "task"):
        task = config.task
    elif hasattr(config, "tasks") and config.tasks:
        task = next(iter(config.tasks.values()))
    else:
        task = None

    if task is None:
        return signals

    # RetesterData → trade_count (via MinTrades as closest proxy)
    retester_data = task.retester_data
    if retester_data and retester_data.raw_xml:
        signals.trade_count = _extract_trade_count(retester_data.raw_xml)

    # CrossChecks → monte_carlo_passed / walkforward_passed
    cross_checks = task.cross_checks_section or task.cross_checks
    if cross_checks and cross_checks.raw_xml:
        signals.monte_carlo_passed = _extract_mc_passed(cross_checks.raw_xml)
        signals.walkforward_passed = _extract_wf_passed(cross_checks.raw_xml)

    # Databanks → databank_coverage
    databanks_section = task.databanks_section or task.databanks
    if databanks_section and databanks_section.raw_xml:
        signals.databank_coverage = _extract_databank_coverage(databanks_section.raw_xml)

    # Project metadata → last_run_status
    if hasattr(config, "metadata") and config.metadata:
        signals.last_run_status = config.metadata.get("last_run_status")

    return signals


# ── Private extractors ─────────────────────────────────────────────────────────


def _extract_trade_count(raw_xml: str) -> int | None:
    match = re.search(r"<MinTrades[^>]*value=\"(\d+)\"", raw_xml)
    if match:
        return int(match.group(1))
    return None


def _extract_mc_passed(raw_xml: str) -> bool | None:
    match = re.search(r"<MonteCarlo[^>]*enabled=\"([^\"]+)\"", raw_xml)
    if match:
        return match.group(1).lower() == "true"
    return None


def _extract_wf_passed(raw_xml: str) -> bool | None:
    match = re.search(r"<WalkForward[^>]*enabled=\"([^\"]+)\"", raw_xml)
    if match:
        return match.group(1).lower() == "true"
    return None


def _extract_databank_coverage(raw_xml: str) -> float | None:
    enabled = len(re.findall(r'<Databank\s[^>]*enabled="true"', raw_xml))
    total = len(re.findall(r"<Databank\s", raw_xml))
    if total > 0:
        return enabled / total
    return None


# ── Mode selection ────────────────────────────────────────────────────────────


def select_retest_mode(
    signals: RetestSignals,
    metadata: dict | None = None,
) -> RetestMode:
    """Select retest mode based on CFX signals and optional metadata override.

    Decision rules (applied in precedence order):
    1. CFX metadata override wins when ``metadata["retest_mode"]`` is present.
    2. ``trade_count < 50`` → ``AutomaticRetest``.
    3. ``monte_carlo_passed is False`` → ``Retest``.
    4. ``walkforward_passed is False`` → ``Retest``.
    5. ``databank_coverage < 0.8`` → ``Retest``.
    6. Default when no signals are present → ``AutomaticRetest``.

    Args:
        signals: Extracted runtime signals.
        metadata: Optional CFX metadata dict. When it contains
            ``retest_mode`` it overrides all signal-based heuristics.

    Returns:
        The selected ``RetestMode``.
    """
    # 1. Metadata override takes precedence
    if metadata and "retest_mode" in metadata:
        mode = metadata["retest_mode"]
        if mode in (RetestMode.AUTOMATIC_RETEST, RetestMode.RETEST):
            return mode

    # 2. No signals → default
    if (
        signals.trade_count is None
        and signals.monte_carlo_passed is None
        and signals.walkforward_passed is None
        and signals.databank_coverage is None
    ):
        return RetestMode.AUTOMATIC_RETEST

    # 3. Rule: low trade count
    if signals.trade_count is not None and signals.trade_count < 50:
        return RetestMode.AUTOMATIC_RETEST

    # 4. Rule: failed Monte Carlo
    if signals.monte_carlo_passed is False:
        return RetestMode.RETEST

    # 5. Rule: failed Walk-Forward
    if signals.walkforward_passed is False:
        return RetestMode.RETEST

    # 6. Rule: low databank coverage
    if signals.databank_coverage is not None and signals.databank_coverage < 0.8:
        return RetestMode.RETEST

    return RetestMode.AUTOMATIC_RETEST


# ── Mutation application ──────────────────────────────────────────────────────


def apply_adaptive_mutations(cfx_path: Path, mode: RetestMode) -> Path:
    """Apply adaptive retest configuration mutations to a .cfx archive.

    Mutations are scoped to the retest task: its ``CrossChecks``, ``Rankings``,
    and ``RetesterData`` sections are updated to match the selected mode. All
    other CFX content (Build, Filtering, Optimize, etc.) is preserved.

    Args:
        cfx_path: Path to the .cfx archive.
        mode: Selected retest mode.

    Returns:
        The path to the mutated archive.
    """
    archive = CfxReader.read(cfx_path)
    config = archive.config

    if hasattr(config, "task"):
        task = config.task
    elif hasattr(config, "tasks") and config.tasks:
        task = next(iter(config.tasks.values()))
    else:
        raise ValueError("No task found in CFX archive")

    if mode == RetestMode.AUTOMATIC_RETEST:
        _apply_automatic_retest(task)
    else:
        _apply_retest(task)

    CfxWriter.write(archive, cfx_path)
    return cfx_path


def _apply_automatic_retest(task: BuildTask) -> None:
    """Replace retest sections with AutomaticRetest-specific variants."""
    task.cross_checks_section = CrossChecksConfig(
        raw_xml=(
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
    )
    task.rankings_section = RankingsConfig(
        raw_xml=(
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
    )
    task.retester_data = RetesterDataConfig(
        raw_xml=(
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
    )


def _apply_retest(task: BuildTask) -> None:
    """Replace retest sections with full Retest variants."""
    task.cross_checks_section = CrossChecksConfig(
        raw_xml=(
            "<CrossChecks>"
            '<MonteCarlo enabled="true" runs="100" percentile="95" />'
            '<WalkForward enabled="true" cycles="5" />'
            "<ConfidenceLevel>0.95</ConfidenceLevel>"
            "</CrossChecks>"
        )
    )
    task.rankings_section = RankingsConfig(
        raw_xml=(
            "<Rankings>"
            "<MinTrades>30</MinTrades>"
            "<ConfidenceLevel>0.95</ConfidenceLevel>"
            "</Rankings>"
        )
    )
    task.retester_data = RetesterDataConfig(
        raw_xml=(
            "<RetesterData>"
            "<MonteCarloRuns>100</MonteCarloRuns>"
            "<WalkForwardCycles>5</WalkForwardCycles>"
            "<ConfidenceLevel>0.95</ConfidenceLevel>"
            "<MinTrades>30</MinTrades>"
            "<MCPercentile>95</MCPercentile>"
            "<Databanks>"
            '<Databank label="Input databank" name="Input" value="Results" />'
            '<Databank label="Output databank" name="Output" value="Results" />'
            "</Databanks>"
            "</RetesterData>"
        )
    )
