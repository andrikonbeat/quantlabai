"""DSL-to-CFX XML translator.

Generates StrategyQuant X ``.cfx`` XML from a validated ``ResearchConfig``
model, encoding market, timeframe, strategy parameters, and entry/exit rules.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from quantlab.dsl.models import AcceptanceCriterion, BuildingBlock, ResearchConfig, Strategy
from quantlab.tools.exceptions import TranslationError, ValidationError

#: Timeframes that SQX supports natively.
SUPPORTED_TIMEFRAMES: set[str] = {
    "M1", "M5", "M15", "M30",
    "H1", "H4",
    "D1", "W1", "MN",
}


def _sanitize_xml_text(value: object) -> str:
    """Convert a value to its XML-safe string representation."""
    if isinstance(value, float):
        # Strip trailing zeros from floats for cleaner output
        s = f"{value:g}"
        return s
    return str(value)


def _build_parameters_xml(parent: ET.Element, params: dict) -> None:
    """Append ``<Parameters>`` child with ``<Parameter>`` elements."""
    if not params:
        return
    params_el = ET.SubElement(parent, "Parameters")
    for key, value in params.items():
        param = ET.SubElement(params_el, "Parameter")
        param.set("name", key)
        param.text = _sanitize_xml_text(value)


def _build_building_blocks_xml(parent: ET.Element, blocks: list[BuildingBlock]) -> None:
    """Append ``<BuildingBlocks>`` to ``parent``."""
    blocks_el = ET.SubElement(parent, "BuildingBlocks")
    for block in blocks:
        bb = ET.SubElement(blocks_el, "BuildingBlock")
        bb.set("name", block.name)

        # Indicator
        ind = ET.SubElement(bb, "Indicator")
        ind.set("name", block.indicator.name)
        _build_parameters_xml(ind, block.indicator.params)

        # Entry rule (optional)
        if block.entry is not None:
            entry = ET.SubElement(bb, "EntryRule")
            entry.text = block.entry.description

        # Exit rule (optional)
        if block.exit is not None:
            exit_el = ET.SubElement(bb, "ExitRule")
            exit_el.text = block.exit.description


def _build_strategies_xml(parent: ET.Element, strategies: list[Strategy]) -> None:
    """Append ``<Strategies>`` to ``parent``."""
    strats_el = ET.SubElement(parent, "Strategies")
    for strategy in strategies:
        s = ET.SubElement(strats_el, "Strategy")
        s.set("name", strategy.name)
        s.set("direction", strategy.direction.value)
        for ref_name in strategy.building_blocks:
            ref = ET.SubElement(s, "BuildingBlockRef")
            ref.set("name", ref_name)


def _build_criteria_xml(parent: ET.Element, criteria: list[AcceptanceCriterion]) -> None:
    """Append ``<AcceptanceCriteria>`` to ``parent`` if any criteria exist."""
    if not criteria:
        return
    crit_el = ET.SubElement(parent, "AcceptanceCriteria")
    for criterion in criteria:
        c = ET.SubElement(crit_el, "Criterion")
        c.set("metric", criterion.metric)
        c.set("operator", criterion.operator)
        c.set("value", _sanitize_xml_text(criterion.value))


def generate_cfx_xml(config: ResearchConfig) -> str:
    """Translate a validated ``ResearchConfig`` into a CFX XML string.

    Args:
        config: A validated ``ResearchConfig`` instance.

    Returns:
        Pretty-printed XML string with declaration.

    Raises:
        TranslationError: Required fields (market, timeframe) are missing.
        ValidationError: An unsupported timeframe was provided.
    """
    if config.market is None:
        raise TranslationError("Market is required for CFX generation")

    if config.timeframe is None:
        raise TranslationError("Timeframe is required for CFX generation")

    if config.timeframe.value not in SUPPORTED_TIMEFRAMES:
        raise ValidationError(
            f"Unsupported timeframe '{config.timeframe.value}'. "
            f"Supported timeframes: {', '.join(sorted(SUPPORTED_TIMEFRAMES))}"
        )

    # Build the XML tree
    root = ET.Element("StrategyQuantX")
    project = ET.SubElement(root, "Project")

    name_el = ET.SubElement(project, "Name")
    name_el.text = config.campaign

    # Markets
    markets_el = ET.SubElement(project, "Markets")
    market_el = ET.SubElement(markets_el, "Market")
    market_el.set("symbol", config.market.value)

    # Timeframes
    tfs_el = ET.SubElement(project, "Timeframes")
    tf_el = ET.SubElement(tfs_el, "Timeframe")
    tf_el.set("value", config.timeframe.value)

    # Building blocks
    _build_building_blocks_xml(project, config.building_blocks)

    # Strategies
    _build_strategies_xml(project, config.strategies)

    # Acceptance criteria
    _build_criteria_xml(project, config.criteria)

    # Serialize to pretty-printed string
    raw_xml = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(raw_xml)
    pretty: str = dom.toprettyxml(indent="  ", encoding=None)

    return pretty
