"""Bridge DSL building blocks/strategies into BuildConfig block constraints.

REQ-03 / REQ-04: maps a ``ResearchConfig``'s building blocks and strategies
into ``BuildConfig.enabled_blocks`` / ``block_weights`` before dispatch, and
validates exported strategies against the intended blocks after dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass

from quantlab.dsl.models import ResearchConfig
from quantlab.sqx.project_builder import BuildConfig


@dataclass(frozen=True)
class BlockMismatchReport:
    """Post-dispatch validation result (REQ-04)."""

    missing: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing


def build_build_config(config: ResearchConfig) -> BuildConfig:
    """Map DSL building blocks/strategies into BuildConfig block constraints.

    ``enabled_blocks`` lists the building-block names in DSL order.
    ``block_weights`` weights each block by its strategy usage count
    (minimum 1.0, so unused blocks stay enabled at base weight).
    """
    enabled = [b.name for b in config.building_blocks]
    if not enabled:
        return BuildConfig()

    usage: dict[str, int] = {}
    for strategy in config.strategies:
        for name in strategy.building_blocks:
            usage[name] = usage.get(name, 0) + 1

    weights = {name: max(1.0, float(usage.get(name, 0))) for name in enabled}
    return BuildConfig(enabled_blocks=enabled, block_weights=weights)


def validate_exported_blocks(
    exports: list[str], intended: list[str]
) -> BlockMismatchReport:
    """Report intended blocks missing from the exported strategies (REQ-04)."""
    exported = set(exports)
    missing = [name for name in intended if name not in exported]
    return BlockMismatchReport(missing=missing)
