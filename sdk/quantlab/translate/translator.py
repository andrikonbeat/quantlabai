"""DSL-to-CFX archive translator using cfx-editor models.

Generates StrategyQuant X ``.cfx`` archives from a validated ``ResearchConfig``
model using CfxArchive, CfxPatcher, and CfxWriter from quantlab.cfx.
"""

from __future__ import annotations

from quantlab.cfx import (
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    CfxPatcher,
    CfxWriter,
    SettingsSection,
    add_ranking_condition,
    add_timeframe,
    enable_block,
    enable_crosscheck,
    set_date_range,
    set_genetic,
    set_market,
)
from quantlab.cfx.models import (
    AutomaticPortfolioBuilderConfig,
    PortfolioSettingsConfig,
    OptimizationConfig,
    OptimizationParametersConfig,
    WalkForwardConfig,
    DatabanksConfig,
    RankingsConfig,
    CrossChecksConfig,
    RetesterDataConfig,
)
from quantlab.dsl.models import (
    AcceptanceCriterion,
    BuildingBlock,
    Market,
    ResearchConfig,
    Strategy,
    Timeframe,
)
from quantlab.tools.exceptions import TranslationError, ValidationError


# Timeframes that SQX supports natively
SUPPORTED_TIMEFRAMES: set[str] = {
    "M1",
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
    "MN",
}


def _validate_dsl_config(config: ResearchConfig) -> None:
    """Validate DSL config has required fields for CFX translation."""
    if config.market is None:
        raise TranslationError("Market is required for CFX generation")

    if config.timeframe is None:
        raise TranslationError("Timeframe is required for CFX generation")

    if config.timeframe.value not in SUPPORTED_TIMEFRAMES:
        raise ValidationError(
            f"Unsupported timeframe '{config.timeframe.value}'. "
            f"Supported timeframes: {', '.join(sorted(SUPPORTED_TIMEFRAMES))}"
        )

    if not config.strategies:
        raise TranslationError("At least one strategy is required for CFX generation")


def _build_base_task(config: ResearchConfig) -> BuildTask:
    """Create a base BuildTask with standard sections populated from DSL config."""
    task = BuildTask()

    # Options section
    task.options = SettingsSection(
        name="Options",
        settings={
            "Campaign@name": config.campaign,
            "Campaign@description": "",
        },
    )

    # WhatToBuild section
    task.what_to_build = SettingsSection(
        name="WhatToBuild",
        settings={
            "BuildType@value": "Strategy",
            "UseGenetic@value": "false",
            "Generations@value": "50",
            "Population@value": "100",
        },
    )

    # RiskMoneyManagement section
    task.risk_money_mgmt = SettingsSection(
        name="RiskMoneyManagement",
        settings={
            "AccountSize@value": "10000",
            "RiskPercent@value": "2",
            "MaxPositions@value": "1",
        },
    )

    # Data section - will be populated by patcher
    task.data = SettingsSection(name="Data", settings={})

    # Rankings section
    task.rankings = SettingsSection(name="Rankings", settings={})

    # PartsToImprove section
    task.parts_to_improve = SettingsSection(name="PartsToImprove", settings={})

    # CrossChecks section
    task.cross_checks = SettingsSection(name="CrossChecks", settings={})

    # Notes section
    task.notes = SettingsSection(name="Notes", settings={})

    return task


def generate_cfx_archive(config: ResearchConfig) -> CfxArchive:
    """Translate a validated ``ResearchConfig`` into a CfxArchive model.

    Uses CfxPatcher to apply domain-level modifications (market, timeframe,
    building blocks, genetic settings, etc.) to a base CFX archive.

    Args:
        config: A validated ``ResearchConfig`` instance.

    Returns:
        A ``CfxArchive`` ready to be written via ``CfxWriter``.

    Raises:
        TranslationError: Required fields (market, timeframe, strategies) missing.
        ValidationError: Unsupported timeframe or invalid config.
    """
    # Validate input
    _validate_dsl_config(config)

    # Create base archive with a single config task
    base_task = _build_base_task(config)
    cfx_config = CfxConfig(task=base_task, schema_version="141.2219")
    archive = CfxArchive(config=cfx_config, task_files={"Build-Task1.xml": base_task})

    # Apply DSL configuration via CfxPatcher
    patcher = CfxPatcher(archive)

    # Set market
    set_market(archive, config.market.value)

    # Add timeframe
    add_timeframe(archive, config.timeframe.value)

    # Enable building blocks
    for block in config.building_blocks:
        enable_block(archive, block.name, weight=100)

    # Note: Building block indicator/rule details would need raw_xml manipulation
    # in the Blocks section, which is a complex section. For now we enable by name.

    # Add acceptance criteria
    for criterion in config.criteria:
        add_ranking_condition(archive, criterion.metric, criterion.operator, criterion.value)

    return archive


def generate_cfx_xml(config: ResearchConfig) -> str:
    """Translate a validated ``ResearchConfig`` into a CFX XML string (legacy compatibility).

    This function maintains backward compatibility with code expecting XML string output.
    For new code, use ``generate_cfx_archive()`` + ``CfxWriter``.

    Args:
        config: A validated ``ResearchConfig`` instance.

    Returns:
        Pretty-printed XML string representing the primary task file.

    Raises:
        TranslationError: Required fields (market, timeframe) are missing.
        ValidationError: An unsupported timeframe was provided.
    """
    archive = generate_cfx_archive(config)

    # Use dry_run to get JSON, but we want XML
    # For backward compat, serialize the primary task to XML via writer
    # Actually, let's just use the writer's internal serialization
    from quantlab.cfx.writer import _serialise_task

    task = _get_primary_task(archive)
    xml_bytes = _serialise_task(task)

    # Pretty print
    from xml.dom import minidom

    raw_xml = xml_bytes.decode("utf-8")
    dom = minidom.parseString(raw_xml)
    pretty: str = dom.toprettyxml(indent="  ", encoding=None)

    return pretty


def _get_primary_task(archive: CfxArchive) -> BuildTask:
    """Get the primary BuildTask from an archive."""
    config = archive.config
    if hasattr(config, "task"):
        return config.task
    elif hasattr(config, "tasks") and config.tasks:
        return next(iter(config.tasks.values()))
    from quantlab.cfx.models import BuildTask

    return BuildTask()


# ── Phase 4 — Portfolio / Optimizer / Retester generators ─────────────


def generate_portfolio_cfx_archive(
    strategies: list[str],
    *,
    generations: int = 50,
    population: int = 200,
    fitness: str = "NetProfit",
    min_strategies: int = 2,
    max_strategies: int = 10,
    rebalance: str = "Monthly",
) -> CfxArchive:
    """Generate a Portfolio Master CFX archive.

    Args:
        strategies: List of strategy IDs to include in the portfolio.
        generations: Genetic algorithm generations.
        population: Population size.
        fitness: Fitness function (e.g. NetProfit, SharpeRatio).
        min_strategies: Minimum number of strategies in the portfolio.
        max_strategies: Maximum number of strategies in the portfolio.
        rebalance: Rebalancing period (Monthly, Quarterly, etc.).

    Returns:
        A ``CfxArchive`` ready to be written via ``CfxWriter``.
    """
    if not strategies:
        raise TranslationError("At least one strategy is required for portfolio generation")
    if generations <= 0:
        raise TranslationError("generations must be positive")
    if population <= 0:
        raise TranslationError("population must be positive")
    if not fitness or not fitness.strip():
        raise TranslationError("fitness must not be empty")
    if min_strategies <= 0:
        raise TranslationError("min_strategies must be positive")
    if max_strategies is not None and max_strategies < min_strategies:
        raise TranslationError("max_strategies must be >= min_strategies")

    task = BuildTask()
    task.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(
        raw_xml=f"""<AutomaticPortfolioBuilder>
  <Generations value="{generations}"/>
  <PopulationSize value="{population}"/>
  <FitnessFunction value="{fitness}"/>
  <MinStrategies value="{min_strategies}"/>
  <MaxStrategies value="{max_strategies}"/>
  <RebalancingPeriod value="{rebalance}"/>
</AutomaticPortfolioBuilder>"""
    )
    task.portfolio_settings = PortfolioSettingsConfig(
        raw_xml=f"""<PortfolioSettings>
  <MinStrategies value="{min_strategies}"/>
  <MaxStrategies value="{max_strategies}"/>
  <RebalancingPeriod value="{rebalance}"/>
</PortfolioSettings>"""
    )

    archive = CfxArchive(
        config=CfxProject(
            name="Portfolio Master",
            tasks={"Portfolio-Task1.xml": task},
            schema_version="144.2953",
        ),
        task_files={"Portfolio-Task1.xml": task},
    )
    return archive


def generate_optimizer_cfx_archive(
    strategy_id: str,
    *,
    method: str = "Genetic",
    objective: str = "SharpeRatio",
    walkforward_cycles: int = 10,
    walkforward_oot_ratio: float = 0.3,
    population: int = 100,
    generations: int = 50,
    crossover: float = 0.8,
    mutation: float = 0.1,
    databanks: list[str] | None = None,
) -> CfxArchive:
    """Generate an Optimizer CFX archive.

    Args:
        strategy_id: Strategy identifier to optimize.
        method: Optimization method (Genetic, BruteForce, Grid).
        objective: Objective function (SharpeRatio, NetProfit, etc.).
        walkforward_cycles: Number of walk-forward cycles.
        walkforward_oot_ratio: Out-of-sample ratio (0 < ratio < 1).
        population: GA population size.
        generations: GA generations.
        crossover: Crossover rate.
        mutation: Mutation rate.
        databanks: Optional list of databank symbols (e.g. ["EURUSD_H1"]).

    Returns:
        A ``CfxArchive`` ready to be written via ``CfxWriter``.
    """
    if not strategy_id or not strategy_id.strip():
        raise TranslationError("strategy_id is required for optimizer generation")
    valid_methods = {"Genetic", "BruteForce", "Grid"}
    if method not in valid_methods:
        raise TranslationError(
            f"Invalid method '{method}'. Valid: {', '.join(sorted(valid_methods))}"
        )
    if not objective or not objective.strip():
        raise TranslationError("objective must not be empty")
    if walkforward_cycles <= 0:
        raise TranslationError("walkforward_cycles must be positive")
    if not (0 < walkforward_oot_ratio < 1):
        raise TranslationError("walkforward_oot_ratio must be in (0, 1)")
    if population <= 0:
        raise TranslationError("population must be positive")
    if generations <= 0:
        raise TranslationError("generations must be positive")
    if not (0 < crossover <= 1):
        raise TranslationError("crossover must be in (0, 1]")
    if not (0 < mutation <= 1):
        raise TranslationError("mutation must be in (0, 1]")

    task = BuildTask()
    task.optimization = OptimizationConfig(
        raw_xml=f"""<Optimization>
  <Method value="{method}"/>
  <ObjectiveFunction value="{objective}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
  <OOTRatio value="{walkforward_oot_ratio}"/>
</Optimization>"""
    )
    task.optimization_parameters = OptimizationParametersConfig(
        raw_xml=f"""<OptimizationParameters>
  <Parameter name="PopulationSize" min="{population}" max="{population}" step="1"/>
  <Parameter name="Generations" min="{generations}" max="{generations}" step="1"/>
  <Parameter name="CrossoverRate" min="{crossover}" max="{crossover}" step="0.1"/>
  <Parameter name="MutationRate" min="{mutation}" max="{mutation}" step="0.01"/>
</OptimizationParameters>"""
    )
    task.walk_forward = WalkForwardConfig(
        raw_xml=f"""<WalkForward>
  <Cycles value="{walkforward_cycles}"/>
  <OOTRatio value="{walkforward_oot_ratio}"/>
  <Anchored value="false"/>
</WalkForward>"""
    )

    if databanks:
        db_lines = []
        for i, db in enumerate(databanks, 1):
            db_lines.append(f'<Databank index="{i}" name="{db}" enabled="true"/>')
        task.databanks_section = DatabanksConfig(
            raw_xml=f"<Databanks>\n{chr(10).join('  ' + l for l in db_lines)}\n</Databanks>"
        )

    archive = CfxArchive(
        config=CfxConfig(
            task=task,
            schema_version="144.2953",
        ),
        task_files={"Optimizer-Task1.xml": task},
    )
    return archive


def generate_retester_cfx_archive(
    strategy_id: str,
    *,
    databanks: list[str],
    mc_runs: int = 100,
    mc_percentile: int = 95,
    walkforward_cycles: int = 5,
    min_trades: int = 30,
    confidence_level: float = 0.95,
) -> CfxArchive:
    """Generate a Retester CFX archive.

    Args:
        strategy_id: Strategy identifier to retest.
        databanks: List of databank symbols (e.g. ["EURUSD_H1"]).
        mc_runs: Monte Carlo simulation runs.
        mc_percentile: MC percentile for confidence bands.
        walkforward_cycles: Number of walk-forward cycles.
        min_trades: Minimum trades for acceptance.
        confidence_level: Confidence level (0.5 < level < 0.99).

    Returns:
        A ``CfxArchive`` ready to be written via ``CfxWriter``.
    """
    if not strategy_id or not strategy_id.strip():
        raise TranslationError("strategy_id is required for retester generation")
    if not databanks:
        raise TranslationError("databanks must not be empty")
    if mc_runs <= 0:
        raise TranslationError("mc_runs must be positive")
    if not (1 <= mc_percentile <= 99):
        raise TranslationError("mc_percentile must be in [1, 99]")
    if walkforward_cycles <= 0:
        raise TranslationError("walkforward_cycles must be positive")
    if min_trades <= 0:
        raise TranslationError("min_trades must be positive")
    if not (0.5 < confidence_level < 0.99):
        raise TranslationError("confidence_level must be in (0.5, 0.99)")

    task = BuildTask()
    task.rankings_section = RankingsConfig(
        raw_xml=f"""<Rankings>
  <MinTrades value="{min_trades}"/>
  <ConfidenceLevel value="{confidence_level}"/>
</Rankings>"""
    )
    task.cross_checks_section = CrossChecksConfig(
        raw_xml=f"""<CrossChecks>
  <MonteCarlo enabled="true" runs="{mc_runs}" percentile="{mc_percentile}"/>
  <WalkForward enabled="true" cycles="{walkforward_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
</CrossChecks>"""
    )

    # Data section (flat key-value for reader compat)
    task.data = SettingsSection(
        name="Data",
        settings={db: "true" for db in databanks},
    )

    # RetesterData section (typed config for proper serialization)
    db_items = "\n".join(
        f'    <Databank name="{db}" enabled="true"/>' for db in databanks
    )
    task.retester_data = RetesterDataConfig(
        raw_xml=f"""<RetesterData>
  <MonteCarloRuns value="{mc_runs}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
  <MinTrades value="{min_trades}"/>
  <MonteCarloPercentile value="{mc_percentile}"/>
  <Databanks>
{db_items}
  </Databanks>
</RetesterData>"""
    )

    archive = CfxArchive(
        config=CfxConfig(
            task=task,
            schema_version="144.2953",
        ),
        task_files={"Retester-Task1.xml": task},
    )
    return archive


# ── Public API ────────────────────────────────────────────────────────

__all__ = [
    "generate_cfx_archive",
    "generate_cfx_xml",
    "generate_portfolio_cfx_archive",
    "generate_optimizer_cfx_archive",
    "generate_retester_cfx_archive",
    "SUPPORTED_TIMEFRAMES",
]