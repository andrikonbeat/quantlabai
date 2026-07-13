"""YAML parser for the QuantLab research DSL.

Parses YAML campaign files into ``ResearchConfig`` models with full
validation, and serialises models back to round-trip YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from quantlab.dsl.models import ResearchConfig
from quantlab.tools.exceptions import ParseError, ValidationError

#: Known market identifiers for semantic validation.
KNOWN_MARKETS: set[str] = {
    # FX
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY",
    # Indices
    "SP500", "NASDAQ", "DOWJONES", "DAX", "FTSE100",
    # Commodities / Crypto
    "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
}

#: Known timeframe identifiers.
KNOWN_TIMEFRAMES: set[str] = {
    "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN",
}


def parse_yaml(path: str | Path) -> ResearchConfig:
    """Parse a YAML file and return a validated ``ResearchConfig``.

    Args:
        path: Filesystem path to the YAML file.

    Returns:
        A fully validated ``ResearchConfig`` instance.

    Raises:
        ParseError: The file cannot be read or contains invalid YAML.
        ValidationError: Semantic validation fails.
    """
    try:
        with open(path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ParseError(f"Campaign file not found: {path}", cause=e)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML in {path}: {e}", cause=e)

    if not isinstance(data, dict):
        raise ParseError(
            f"Expected a YAML mapping (dict) at root, got {type(data).__name__}"
        )

    return _build_config(data)


def parse_yaml_string(content: str) -> ResearchConfig:
    """Parse a YAML string and return a validated ``ResearchConfig``.

    Useful for testing and for in-memory parsing without filesystem I/O.

    Args:
        content: A valid YAML string.

    Returns:
        A fully validated ``ResearchConfig`` instance.
    """
    try:
        data: dict[str, Any] = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML string: {e}", cause=e)

    if not isinstance(data, dict):
        raise ParseError(
            f"Expected a YAML mapping (dict) at root, got {type(data).__name__}"
        )

    return _build_config(data)


def _build_config(data: dict[str, Any]) -> ResearchConfig:
    """Build and validate a ``ResearchConfig`` from raw parsed data.

    Performs spec-required semantic checks before constructing the model
    so that Pydantic validators get clean input.
    """
    market = data.get("market")
    if market is not None and market.upper() not in KNOWN_MARKETS:
        raise ValidationError(
            f"Unknown market '{market}'. "
            f"Recognised markets: {', '.join(sorted(KNOWN_MARKETS))}"
        )

    timeframe = data.get("timeframe")
    if timeframe is not None and timeframe.upper() not in KNOWN_TIMEFRAMES:
        raise ValidationError(
            f"Unknown timeframe '{timeframe}'. "
            f"Recognised timeframes: {', '.join(sorted(KNOWN_TIMEFRAMES))}"
        )

    try:
        return ResearchConfig.model_validate(data)
    except Exception as e:
        raise ValidationError(str(e), cause=e)


def serialize(config: ResearchConfig) -> str:
    """Serialise a ``ResearchConfig`` back to YAML string.

    The output is a round-trip safe representation that can be re-parsed
    by ``parse_yaml_string`` to yield an identical model.

    Args:
        config: A validated ``ResearchConfig`` instance.

    Returns:
        YAML string.
    """
    return yaml.safe_dump(
        config.model_dump(mode="json", by_alias=True),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def validate(config: ResearchConfig) -> ResearchConfig:
    """Re-validate a ``ResearchConfig`` in place.

    Calls Pydantic's validation pipeline which triggers all model validators
    (duplicate names, building-block references, etc.).

    Returns the same model on success. Raises ``ValidationError`` on failure.
    """
    try:
        ResearchConfig.model_validate(config.model_dump(mode="python"))
    except Exception as e:
        raise ValidationError(str(e), cause=e)
    return config
