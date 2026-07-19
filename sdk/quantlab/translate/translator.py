"""DSL-to-CFX archive translator using cfx-editor models.

Generates StrategyQuant X ``.cfx`` archives from a validated ``ResearchConfig``
model using CfxArchive, CfxPatcher, and CfxWriter from quantlab.cfx.
"""

from __future__ import annotations

from quantlab.cfx import (
    BuildTask,
    CfxArchive,
    CfxConfig,
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


# ── Public API ────────────────────────────────────────────────────────

__all__ = [
    "generate_cfx_archive",
    "generate_cfx_xml",
    "SUPPORTED_TIMEFRAMES",
]