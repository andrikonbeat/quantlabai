"""Tests for the DSL building-blocks bridge (REQ-03, REQ-04).

Covers:
- ``build_build_config``: mapping DSL building_blocks/strategies into
  ``BuildConfig`` block constraints (REQ-18/REQ-03).
- ``_apply_build_config``: emitting block entries into template XML with
  template-probe fallback (REQ-03).
- ``validate_exported_blocks``: post-dispatch mismatch report (REQ-04).
"""

from pathlib import Path

import pytest

from quantlab.dsl.models import (
    BuildingBlock,
    IndicatorConfig,
    ResearchConfig,
    Strategy,
)
from quantlab.sqx.blocks_bridge import (
    BlockMismatchReport,
    build_build_config,
    validate_exported_blocks,
)
from quantlab.sqx.project_builder import BuildConfig, _apply_build_config

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_CFX = REPO_ROOT / "tests" / "cfx" / "fixtures" / "Builder.cfx"

_TEMPLATE_WITH_BLOCKS = """<Blocks type="simple">
  <Block key="bb1" weight="1" use="false" category="signals">
    <Value>1</Value>
  </Block>
  <Block key="bb2" weight="1" use="false" category="signals">
    <Value>2</Value>
  </Block>
</Blocks>"""


def _dsl_config(*block_names: str) -> ResearchConfig:
    return ResearchConfig(
        campaign="Bridge",
        market="EURUSD",
        timeframe="H1",
        building_blocks=[
            BuildingBlock(name=n, indicator=IndicatorConfig(name="RSI", params={"period": 14}))
            for n in block_names
        ],
    )


class TestBuildBuildConfig:
    """REQ-18/REQ-03: DSL building_blocks/strategies map into BuildConfig."""

    def test_building_blocks_map_to_enabled_blocks(self) -> None:
        config = _dsl_config("bb1", "bb2")
        bc = build_build_config(config)
        assert bc.enabled_blocks == ["bb1", "bb2"]
        assert bc.block_weights is not None
        assert "bb1" in bc.block_weights
        assert "bb2" in bc.block_weights

    def test_no_building_blocks_falls_back_to_empty(self) -> None:
        config = ResearchConfig(campaign="Empty", market="EURUSD", timeframe="H1")
        bc = build_build_config(config)
        assert bc.enabled_blocks is None
        assert bc.block_weights is None

    def test_block_weights_reflect_strategy_usage(self) -> None:
        config = _dsl_config("bb1", "bb2")
        config.strategies = [
            Strategy(name="S1", building_blocks=["bb1"]),
            Strategy(name="S2", building_blocks=["bb1", "bb2"]),
        ]
        bc = build_build_config(config)
        # bb1 referenced by both strategies → higher weight than bb2
        assert bc.block_weights is not None
        assert bc.block_weights["bb1"] >= bc.block_weights["bb2"]
        assert bc.block_weights["bb1"] >= 1.0
        assert bc.block_weights["bb2"] >= 1.0


class TestApplyBuildConfigBlocks:
    """REQ-03: _apply_build_config emits block entries on probe match."""

    def test_emits_use_true_and_weight_on_probe_match(self) -> None:
        bc = BuildConfig(
            enabled_blocks=["bb1"],
            block_weights={"bb1": 3.0},
        )
        result = _apply_build_config(_TEMPLATE_WITH_BLOCKS, bc)
        assert 'key="bb1"' in result
        assert 'use="true"' in result
        assert 'weight="3"' in result
        # untouched block keeps its template state
        assert 'key="bb2"' in result
        assert 'use="false"' in result

    def test_probe_failure_returns_xml_unchanged(self) -> None:
        bc = BuildConfig(
            enabled_blocks=["missing-block"],
            block_weights={"missing-block": 1.0},
        )
        result = _apply_build_config(_TEMPLATE_WITH_BLOCKS, bc)
        assert result == _TEMPLATE_WITH_BLOCKS

    def test_no_blocks_returns_xml_unchanged(self) -> None:
        bc = BuildConfig()
        result = _apply_build_config(_TEMPLATE_WITH_BLOCKS, bc)
        assert result == _TEMPLATE_WITH_BLOCKS

    def test_non_block_build_config_fields_still_apply(self) -> None:
        template = '<PopulationSize>100</PopulationSize>\n<Blocks type="simple">\n</Blocks>'
        bc = BuildConfig(population=250)
        result = _apply_build_config(template, bc)
        assert "<PopulationSize>250</PopulationSize>" in result


class TestValidateExportedBlocks:
    """REQ-04: post-dispatch mismatch report."""

    def test_mismatch_report_lists_missing_blocks(self) -> None:
        report = validate_exported_blocks(
            exports=["S1", "S2"],
            intended=["S1", "S2", "bb1"],
        )
        assert isinstance(report, BlockMismatchReport)
        assert report.missing == ["bb1"]
        assert not report.ok

    def test_match_report_is_empty(self) -> None:
        report = validate_exported_blocks(
            exports=["S1", "S2"],
            intended=["S1", "S2"],
        )
        assert report.missing == []
        assert report.ok

    def test_fixture_fallback_remains_available(self) -> None:
        """REQ-04: the fixture fallback path SHALL remain for untrusted CFX."""
        assert FIXTURE_CFX.exists(), (
            f"fixture fallback missing at {FIXTURE_CFX}"
        )
