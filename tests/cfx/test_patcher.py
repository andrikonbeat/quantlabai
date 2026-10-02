"""Tests for CfxPatcher — validate-then-apply semantics and domain methods."""

import xml.etree.ElementTree as ET

import pytest

from quantlab.cfx import (
    CfxArchive,
    CfxConfig,
    BuildTask,
    SettingsSection,
    CfxPatcher,
    ValidationError,
    set_market,
    add_timeframe,
    enable_block,
    disable_block,
    set_genetic,
    set_date_range,
    add_ranking_condition,
    enable_crosscheck,
)
from quantlab.cfx.models import (
    SetMarketInstruction,
    AddTimeframeInstruction,
    EnableBlockInstruction,
    DisableBlockInstruction,
    SetGeneticInstruction,
    SetDateRangeInstruction,
    AddRankingConditionInstruction,
    EnableCrosscheckInstruction,
    SetCrossChecksInstruction,
    CrossChecksConfig,
    CrossChecksGeneric,
)


def _make_archive() -> CfxArchive:
    """Create a minimal valid archive for testing."""
    task = BuildTask(
        options=SettingsSection(name="Options", settings={"Campaign@name": "Test"}),
        what_to_build=SettingsSection(name="WhatToBuild", settings={}),
        risk_money_mgmt=SettingsSection(name="RiskMoneyManagement", settings={}),
        data=SettingsSection(name="Data", settings={}),
        rankings=SettingsSection(name="Rankings", settings={}),
        parts_to_improve=SettingsSection(name="PartsToImprove", settings={}),
        cross_checks=SettingsSection(name="CrossChecks", settings={}),
        notes=SettingsSection(name="Notes", settings={}),
    )
    config = CfxConfig(task=task, schema_version="141.2219")
    return CfxArchive(config=config)


class TestPatcherValidateAll:
    """Tests for validate-then-apply semantics."""

    def test_valid_sequence_all_applied(self) -> None:
        """GIVEN a list of valid instructions
        WHEN apply() is called
        THEN all instructions are applied and patcher returns self.
        """
        archive = _make_archive()
        patcher = CfxPatcher(archive)

        instructions = [
            SetMarketInstruction(symbol="EURUSD"),
            AddTimeframeInstruction(timeframe="H1"),
            EnableBlockInstruction(block_key="block1", weight=100),
        ]

        result = patcher.apply(instructions)

        # Should return self for chaining
        assert result is patcher

        # Market should be set
        assert archive.config.task.data.settings.get("Symbol@symbol") == "EURUSD"
        assert archive.config.task.data.settings.get("Symbol@name") == "EURUSD"

        # Timeframe should be added
        assert archive.config.task.data.settings.get("Timeframe1@value") == "H1"
        assert archive.config.task.what_to_build.settings.get("Timeframe1@value") == "H1"

    def test_invalid_instruction_raises_and_rolls_back(self) -> None:
        """GIVEN a list with an invalid instruction
        WHEN apply() is called
        THEN ValidationError is raised and NO mutations are applied.
        """
        archive = _make_archive()

        instructions = [
            SetMarketInstruction(symbol="EURUSD"),  # Valid
            AddTimeframeInstruction(timeframe="INVALID_TF"),  # Invalid
        ]

        with pytest.raises(ValidationError, match="unsupported timeframe"):
            CfxPatcher(archive).apply(instructions)

        # Verify rollback: market should NOT be set
        assert "Symbol@symbol" not in archive.config.task.data.settings
        assert "Timeframe1@value" not in archive.config.task.data.settings

    def test_empty_instructions_succeeds(self) -> None:
        """Empty instruction list should succeed without changes."""
        archive = _make_archive()
        result = CfxPatcher(archive).apply([])
        assert result is not None


class TestPatcherIndividualValidators:
    """Tests for individual instruction validators."""

    def test_set_market_empty_symbol_raises(self) -> None:
        archive = _make_archive()
        instr = SetMarketInstruction(symbol="")
        with pytest.raises(ValidationError, match="symbol must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_set_market_whitespace_symbol_raises(self) -> None:
        archive = _make_archive()
        instr = SetMarketInstruction(symbol="   ")
        with pytest.raises(ValidationError, match="symbol must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_add_timeframe_unsupported_raises(self) -> None:
        archive = _make_archive()
        instr = AddTimeframeInstruction(timeframe="X1")
        with pytest.raises(ValidationError, match="unsupported timeframe"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_enable_block_empty_key_raises(self) -> None:
        archive = _make_archive()
        instr = EnableBlockInstruction(block_key="")
        with pytest.raises(ValidationError, match="block_key must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_enable_block_negative_weight_raises(self) -> None:
        archive = _make_archive()
        instr = EnableBlockInstruction(block_key="test", weight=-1)
        with pytest.raises(ValidationError, match="weight must be non-negative"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_disable_block_empty_key_raises(self) -> None:
        archive = _make_archive()
        instr = DisableBlockInstruction(block_key="")
        with pytest.raises(ValidationError, match="block_key must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_set_genetic_invalid_generations_raises(self) -> None:
        archive = _make_archive()
        instr = SetGeneticInstruction(enabled=True, generations=0, population=100)
        with pytest.raises(ValidationError, match="generations must be positive"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_set_genetic_invalid_population_raises(self) -> None:
        archive = _make_archive()
        instr = SetGeneticInstruction(enabled=True, generations=50, population=0)
        with pytest.raises(ValidationError, match="population must be positive"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_set_date_range_empty_start_raises(self) -> None:
        archive = _make_archive()
        instr = SetDateRangeInstruction(start="", end="2023.12.31")
        with pytest.raises(ValidationError, match="start must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_add_ranking_condition_invalid_operator_raises(self) -> None:
        archive = _make_archive()
        instr = AddRankingConditionInstruction(metric="pf", operator=">>", value=1.0)
        with pytest.raises(ValidationError, match="invalid operator"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_add_ranking_condition_empty_metric_raises(self) -> None:
        archive = _make_archive()
        instr = AddRankingConditionInstruction(metric="", operator=">=", value=1.0)
        with pytest.raises(ValidationError, match="metric must not be empty"):
            CfxPatcher(archive)._validate_instruction(instr)

    def test_enable_crosscheck_invalid_cycles_raises(self) -> None:
        archive = _make_archive()
        instr = EnableCrosscheckInstruction(wf_enabled=True, mc_enabled=False, wf_cycles=0)
        with pytest.raises(ValidationError, match="wf_cycles must be positive"):
            CfxPatcher(archive)._validate_instruction(instr)


class TestDomainMethods:
    """Tests for the 8 domain convenience methods (via CfxPatcher)."""

    def test_set_market_updates_data_section(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).set_market("GBPUSD")

        assert archive.config.task.data.settings["Symbol@symbol"] == "GBPUSD"
        assert archive.config.task.data.settings["Symbol@name"] == "GBPUSD"

    def test_add_timeframe_updates_data_and_what_to_build(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).add_timeframe("M15")

        assert archive.config.task.data.settings["Timeframe1@value"] == "M15"
        assert archive.config.task.what_to_build.settings["Timeframe1@value"] == "M15"

    def test_enable_block_returns_patcher_for_chaining(self) -> None:
        archive = _make_archive()
        result = CfxPatcher(archive).enable_block("my_block", weight=50)
        assert result is not None

    def test_disable_block_returns_patcher_for_chaining(self) -> None:
        archive = _make_archive()
        result = CfxPatcher(archive).disable_block("my_block")
        assert result is not None

    def test_set_genetic_updates_what_to_build(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).set_genetic(enabled=True, generations=100, population=200)

        wtb = archive.config.task.what_to_build
        assert wtb.settings["UseGenetic@value"] == "true"
        assert wtb.settings["Generations@value"] == "100"
        assert wtb.settings["Population@value"] == "200"

    def test_set_genetic_disabled_updates_what_to_build(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).set_genetic(enabled=False, generations=50, population=100)

        wtb = archive.config.task.what_to_build
        assert wtb.settings["UseGenetic@value"] == "false"

    def test_set_date_range_updates_data_section(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).set_date_range("2020.01.01", "2023.12.31")

        data = archive.config.task.data
        assert data.settings["FromDate@value"] == "2020.01.01"
        assert data.settings["ToDate@value"] == "2023.12.31"

    def test_add_ranking_condition_adds_to_rankings(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).add_ranking_condition("profit_factor", ">=", 1.5)

        rankings = archive.config.task.rankings
        assert rankings.settings["Criterion1@metric"] == "profit_factor"
        assert rankings.settings["Criterion1@operator"] == ">="
        assert rankings.settings["Criterion1@value"] == "1.5"

    def test_add_multiple_ranking_conditions_increments_index(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).add_ranking_condition("pf", ">=", 1.5)
        CfxPatcher(archive).add_ranking_condition("sharpe", ">", 1.0)

        rankings = archive.config.task.rankings
        assert rankings.settings["Criterion1@metric"] == "pf"
        assert rankings.settings["Criterion2@metric"] == "sharpe"
        assert rankings.settings["Criterion1@value"] == "1.5"
        assert rankings.settings["Criterion2@value"] == "1"

    def test_enable_crosscheck_updates_cross_checks(self) -> None:
        archive = _make_archive()
        CfxPatcher(archive).enable_crosscheck(wf_enabled=True, mc_enabled=True, wf_cycles=100)

        cc = archive.config.task.cross_checks
        assert cc.settings["WalkForward@enabled"] == "true"
        assert cc.settings["MonteCarlo@enabled"] == "true"
        assert cc.settings["WalkForward@cycles"] == "100"


class TestDomModule:
    """Tests for the dom.py module functions."""

    def test_set_market_via_dom(self) -> None:
        archive = _make_archive()
        set_market(archive, "AUDUSD")
        assert archive.config.task.data.settings["Symbol@symbol"] == "AUDUSD"

    def test_add_timeframe_via_dom(self) -> None:
        archive = _make_archive()
        add_timeframe(archive, "H4")
        assert archive.config.task.data.settings["Timeframe1@value"] == "H4"

    def test_enable_block_via_dom(self) -> None:
        archive = _make_archive()
        enable_block(archive, "bb1", weight=75)

    def test_disable_block_via_dom(self) -> None:
        archive = _make_archive()
        disable_block(archive, "bb1")

    def test_set_genetic_via_dom(self) -> None:
        archive = _make_archive()
        set_genetic(archive, True, 200, 300)
        wtb = archive.config.task.what_to_build
        assert wtb.settings["UseGenetic@value"] == "true"
        assert wtb.settings["Generations@value"] == "200"
        assert wtb.settings["Population@value"] == "300"

    def test_set_date_range_via_dom(self) -> None:
        archive = _make_archive()
        set_date_range(archive, "2021.01.01", "2022.12.31")
        data = archive.config.task.data
        assert data.settings["FromDate@value"] == "2021.01.01"
        assert data.settings["ToDate@value"] == "2022.12.31"

    def test_add_ranking_condition_via_dom(self) -> None:
        archive = _make_archive()
        add_ranking_condition(archive, "net_profit", ">", 1000)
        rankings = archive.config.task.rankings
        assert rankings.settings["Criterion1@metric"] == "net_profit"
        assert rankings.settings["Criterion1@operator"] == ">"
        assert rankings.settings["Criterion1@value"] == "1000"

    def test_enable_crosscheck_via_dom(self) -> None:
        archive = _make_archive()
        enable_crosscheck(archive, wf_enabled=False, mc_enabled=True, wf_cycles=25)
        cc = archive.config.task.cross_checks
        assert cc.settings["WalkForward@enabled"] == "false"
        assert cc.settings["MonteCarlo@enabled"] == "true"
        assert cc.settings["WalkForward@cycles"] == "25"

    def test_dom_functions_return_archive_for_chaining(self) -> None:
        """All dom functions should return the archive for chaining."""
        archive = _make_archive()
        result = set_market(archive, "EURUSD")
        assert result is archive

        result = add_timeframe(archive, "H1")
        assert result is archive

        result = enable_block(archive, "bb1")
        assert result is archive

        result = disable_block(archive, "bb1")
        assert result is archive

        result = set_genetic(archive, True, 50, 100)
        assert result is archive

        result = set_date_range(archive, "2020.01.01", "2020.12.31")
        assert result is archive

        result = add_ranking_condition(archive, "pf", ">=", 1.0)
        assert result is archive

        result = enable_crosscheck(archive, True, True, 50)
        assert result is archive


class TestSetCrossChecksTyped:
    """Tests for typed CrossChecks patching."""

    def test_set_crosschecks_creates_typed_model(self) -> None:
        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetCrossChecksInstruction(
            mc_enabled=True,
            wf_enabled=True,
            mc_runs=100,
            mc_percentile=95,
            wf_cycles=5,
            confidence_level=0.95,
        )
        patcher.apply([instr])

        section = archive.config.task.cross_checks_section
        assert section is not None
        assert section.dialect == "generic"
        assert isinstance(section.generic, CrossChecksGeneric)
        assert section.generic.mc_enabled is True
        assert section.generic.mc_runs == 100
        assert section.generic.wf_enabled is True
        assert section.generic.wf_cycles == 5
        assert section.generic.confidence_level == 0.95
        assert section.raw_xml == ""

    def test_set_crosschecks_invalid_confidence_raises(self) -> None:
        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetCrossChecksInstruction(
            mc_enabled=False,
            wf_enabled=False,
            confidence_level=0.999,
        )
        with pytest.raises(ValidationError, match="confidence_level must be in"):
            patcher.apply([instr])

    def test_set_crosschecks_round_trip_via_writer(self) -> None:
        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetCrossChecksInstruction(
            mc_enabled=True,
            wf_enabled=False,
            mc_runs=250,
            mc_percentile=90,
            wf_cycles=10,
            confidence_level=0.90,
        )
        patcher.apply([instr])

        section = archive.config.task.cross_checks_section
        assert section is not None
        xml = section.to_xml()
        assert '<MonteCarlo enabled="true" runs="250" percentile="90"/>' in xml
        assert '<WalkForward enabled="false" cycles="10"/>' in xml
        assert '<ConfidenceLevel value="0.9"/>' in xml


# ═══════════════════════════════════════════════════════════════════════════
# EnableCrosscheck — the lane actually present on a real SQX read
# ═══════════════════════════════════════════════════════════════════════════


# Shaped like a real SQX <CrossChecks> block: from_xml recognises the three
# generic children, keeps their source markup verbatim in ``generic.raw_xml``
# and leaves ``raw_xml`` for unrecognised children only (none here).
_SQX_CROSS_CHECKS_XML = (
    "<CrossChecks>"
    '<MonteCarlo enabled="false" runs="200" percentile="99"/>'
    '<WalkForward enabled="false" cycles="3"/>'
    '<ConfidenceLevel value="0.9"/>'
    "</CrossChecks>"
)


def _make_typed_cross_checks_archive() -> CfxArchive:
    """An archive whose task carries ONLY the complex CrossChecks lane.

    This is the shape a real SQX archive has: the reader populates
    ``cross_checks_section`` and leaves ``cross_checks`` empty, so the flat
    lane the applier used to require is absent.
    """
    task = BuildTask(
        options=SettingsSection(name="Options", settings={"Campaign@name": "Test"}),
        what_to_build=SettingsSection(name="WhatToBuild", settings={}),
    )
    task.cross_checks_section = CrossChecksConfig.from_xml(_SQX_CROSS_CHECKS_XML)
    return CfxArchive(config=CfxConfig(task=task, schema_version="141.2219"))


class TestEnableCrossChecksOnTypedLane:
    """``_apply_enable_crosscheck`` was guarded by ``if self._task.cross_checks``.

    On any real SQX archive that lane is absent — the reader fills
    ``cross_checks_section`` instead — so the instruction was discarded with no
    error, no trace and no effect on the task.
    """

    def test_typed_fields_are_updated_when_only_the_complex_lane_exists(self) -> None:
        """GIVEN a task carrying only ``cross_checks_section`` (dialect generic)
        WHEN enable_crosscheck is applied
        THEN the typed generic fields take the instruction's values instead of
        the instruction being silently dropped.
        """
        archive = _make_typed_cross_checks_archive()

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=True, wf_cycles=10
        )

        generic = archive.config.task.cross_checks_section.generic
        assert generic.mc_enabled is True
        assert generic.wf_enabled is True
        assert generic.wf_cycles == 10

    def test_typed_update_reaches_the_emitted_xml(self) -> None:
        """The typed fields must not be write-only: ``to_xml()`` re-emits the
        verbatim source children it kept, so the instruction is only effective
        if the values actually land in the serialised document.

        Asserted on the parsed element rather than on the markup text, because
        the stored children are re-serialised (``<WalkForward ... />`` with a
        space) while a freshly synthesised one is not (``<WalkForward .../>``).
        """
        archive = _make_typed_cross_checks_archive()

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=True, wf_cycles=10
        )

        root = ET.fromstring(archive.config.task.cross_checks_section.to_xml())

        assert dict(root.find("MonteCarlo").attrib) == {
            "enabled": "true",
            "runs": "200",
            "percentile": "99",
        }
        assert dict(root.find("WalkForward").attrib) == {
            "enabled": "true",
            "cycles": "10",
        }
        # An untouched value must survive the update.
        assert root.find("ConfidenceLevel").get("value") == "0.9"

    def test_nested_child_dialect_is_preserved_and_patched(self) -> None:
        """Older SQX blocks spell the same fields as nested children
        (``<WalkForward><Use/><Cycles/></WalkForward>``). Patching must write that
        form, not convert it to the attribute form and rewrite the dialect.
        """
        archive = CfxArchive(
            config=CfxConfig(task=BuildTask(), schema_version="141.2219")
        )
        archive.config.task.cross_checks_section = CrossChecksConfig.from_xml(
            "<CrossChecks>"
            "<MonteCarlo><Use>false</Use><NumberOfSimulations>250</NumberOfSimulations></MonteCarlo>"
            "<WalkForward><Use>false</Use><Cycles>3</Cycles></WalkForward>"
            '<ConfidenceLevel value="0.9"/>'
            "</CrossChecks>"
        )

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=False, wf_cycles=11
        )

        root = ET.fromstring(archive.config.task.cross_checks_section.to_xml())

        assert root.find("MonteCarlo").find("Use").text == "false"
        assert root.find("MonteCarlo").find("NumberOfSimulations").text == "250"
        assert root.find("WalkForward").find("Use").text == "true"
        assert root.find("WalkForward").find("Cycles").text == "11"

    def test_flat_lane_is_created_on_demand_for_a_bare_task(self) -> None:
        """A bare task has neither lane, so the flat lane is created and filled —
        the instruction must always have an effect.
        """
        archive = CfxArchive(
            config=CfxConfig(task=BuildTask(), schema_version="141.2219")
        )

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=True, wf_cycles=10
        )

        settings = archive.config.task.cross_checks.settings
        assert settings["WalkForward@enabled"] == "true"
        assert settings["MonteCarlo@enabled"] == "true"
        assert settings["WalkForward@cycles"] == "10"

    def test_flat_lane_is_created_on_demand_when_only_a_bare_section_exists(
        self,
    ) -> None:
        """An empty-but-present flat lane must be filled, not treated as absent."""
        archive = _make_archive()
        archive.config.task.cross_checks = SettingsSection(
            name="CrossChecks", settings={}
        )

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=False, wf_cycles=25
        )

        settings = archive.config.task.cross_checks.settings
        assert settings["WalkForward@enabled"] == "true"
        assert settings["MonteCarlo@enabled"] == "false"
        assert settings["WalkForward@cycles"] == "25"

    def test_automatic_retest_dialect_still_reaches_the_flat_lane(self) -> None:
        """Only the generic dialect carries mc_enabled/wf_enabled/wf_cycles. A
        section in another dialect has no typed fields to update, so the flat
        lane is still created rather than discarding the instruction.
        """
        archive = _make_archive()
        archive.config.task.cross_checks_section = CrossChecksConfig(
            dialect="automatic_retest", raw_xml='<CrossChecks use="false"/>'
        )

        CfxPatcher(archive).enable_crosscheck(
            wf_enabled=True, mc_enabled=True, wf_cycles=7
        )

        settings = archive.config.task.cross_checks.settings
        assert settings["WalkForward@enabled"] == "true"
        assert settings["MonteCarlo@enabled"] == "true"
        assert settings["WalkForward@cycles"] == "7"


# ═══════════════════════════════════════════════════════════════════════════
# Advanced Ranking Filters — models + patcher
# ═══════════════════════════════════════════════════════════════════════════


class TestAdvancedRankingModels:
    """Tests for ColumnValue, AdvancedRankingCondition, AdvancedRankingsConfig."""

    def test_column_value_round_trip_full_attributes(self) -> None:
        """GIVEN a ColumnValue with all attributes
        WHEN model_dump and model_validate round-trip
        THEN all attributes are preserved with alias 'class'.
        """
        from quantlab.cfx.models import ColumnValue

        cv = ColumnValue(
            column="ProfitFactor",
            column_type="0",
            format="Decimal2",
            result_type="main",
            direction="0",
            sample_type="127",
            pl_type="10",
            confidence_level="50",
            market="1",
            subresult="30",
            pct_ratio="0",
            class_="ProfitFactor",
            name="PF",
        )
        data = cv.model_dump(by_alias=True)
        assert data["column"] == "ProfitFactor"
        assert data["class"] == "ProfitFactor"
        assert data["format"] == "Decimal2"
        assert data["resultType"] == "main"
        assert data["pctRatio"] == "0"

        restored = ColumnValue.model_validate(data)
        assert restored.column == "ProfitFactor"
        assert restored.class_ == "ProfitFactor"

    def test_column_value_defaults(self) -> None:
        """GIVEN a ColumnValue with only required fields
        WHEN dumped
        THEN defaults are populated.
        """
        from quantlab.cfx.models import ColumnValue

        cv = ColumnValue(column="Sharpe", format="Decimal2", class_="Sharpe")
        data = cv.model_dump(by_alias=True)
        assert data["columnType"] == "0"
        assert data["sampleType"] == "127"
        assert data["plType"] == "10"
        assert data["confidenceLevel"] == "50"
        assert data["market"] == "1"
        assert data["subresult"] == "30"
        assert data["pctRatio"] == "0"
        assert data["name"] is None

    def test_advanced_ranking_condition_round_trip_full(self) -> None:
        """GIVEN a condition with full attributes and two ColumnValue entries
        WHEN serializes to XML and parses back
        THEN all attributes and children are preserved exactly.
        """
        from quantlab.cfx.models import AdvancedRankingCondition, ColumnValue

        cond = AdvancedRankingCondition(
            use=True,
            result_type="main",
            sample_type="127",
            direction="0",
            pct_ratio="0",
            confidence_level="50",
            market="1",
            pl_type="10",
            subresult="30",
            class_="MyClass",
            name="MyCond",
            column_values=[
                ColumnValue(column="ProfitFactor", format="Decimal2", class_="ProfitFactor"),
                ColumnValue(column="SharpeRatio", format="Decimal2", class_="SharpeRatio"),
            ],
        )
        data = cond.model_dump(by_alias=True)
        assert data["use"] is True
        assert data["class"] == "MyClass"
        assert data["name"] == "MyCond"
        assert len(data["column_values"]) == 2
        assert data["column_values"][0]["column"] == "ProfitFactor"

        restored = AdvancedRankingCondition.model_validate(data)
        assert restored.use is True
        assert restored.class_ == "MyClass"
        assert len(restored.column_values) == 2
        assert restored.column_values[0].column == "ProfitFactor"

    def test_advanced_ranking_condition_minimal(self) -> None:
        """GIVEN a condition with only use and one ColumnValue
        WHEN serialized
        THEN optional attributes use defaults and model validates.
        """
        from quantlab.cfx.models import AdvancedRankingCondition, ColumnValue

        cond = AdvancedRankingCondition(
            use=True,
            column_values=[
                ColumnValue(column="NetProfit", format="Decimal2", class_="NetProfit"),
            ],
        )
        data = cond.model_dump(by_alias=True)
        assert data["use"] is True
        assert data["resultType"] == "main"
        assert data["sampleType"] == "127"
        assert data["pctRatio"] == "0"
        assert data["class"] is None
        assert data["name"] is None
        assert len(data["column_values"]) == 1

    def test_advanced_rankings_config_round_trip(self) -> None:
        """GIVEN an AdvancedRankingsConfig with conditions
        WHEN model_dump and model_validate round-trip
        THEN conditions list is preserved.
        """
        from quantlab.cfx.models import AdvancedRankingCondition, AdvancedRankingsConfig, ColumnValue

        config = AdvancedRankingsConfig(
            conditions=[
                AdvancedRankingCondition(
                    use=True,
                    result_type="main",
                    column_values=[
                        ColumnValue(column="ProfitFactor", format="Decimal2", class_="ProfitFactor"),
                    ],
                ),
            ],
        )
        data = config.model_dump(by_alias=True)
        assert data["conditions"] is not None
        assert len(data["conditions"]) == 1
        assert data["conditions"][0]["use"] is True
        assert data["raw_xml"] == ""

        restored = AdvancedRankingsConfig.model_validate(data)
        assert restored.conditions is not None
        assert len(restored.conditions) == 1
        assert restored.conditions[0].use is True
        assert restored.raw_xml == ""


class TestAdvancedRankingPatcher:
    """Tests for AddAdvancedRankingConditionInstruction and SetAdvancedRankingsInstruction."""

    def test_set_advanced_rankings_generates_nested_xml(self) -> None:
        """GIVEN a SetAdvancedRankingsInstruction with one condition
        WHEN applied
        THEN rankings_section.raw_xml contains nested Conditions/Condition/Column-Value.
        """
        from quantlab.cfx.models import (
            AdvancedRankingCondition,
            AdvancedRankingsConfig,
            ColumnValue,
            SetAdvancedRankingsInstruction,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetAdvancedRankingsInstruction(
            conditions=[
                AdvancedRankingCondition(
                    use=True,
                    result_type="main",
                    sample_type="127",
                    direction="desc",
                    pct_ratio="10",
                    confidence_level="95",
                    market="1",
                    pl_type="10",
                    subresult="30",
                    class_="Advanced",
                    name="Main",
                    column_values=[
                        ColumnValue(column="ProfitFactor", column_type="0", format="Decimal2", class_="ProfitFactor"),
                    ],
                ),
            ],
        )
        patcher.apply([instr])

        section = archive.config.task.rankings_section
        assert section is not None
        xml = section.raw_xml
        assert "<Rankings>" in xml
        assert "<Conditions>" in xml
        assert '<Condition use="true"' in xml
        assert 'resultType="main"' in xml
        assert 'sampleType="127"' in xml
        assert 'direction="desc"' in xml
        assert 'pctRatio="10"' in xml
        assert 'confidenceLevel="95"' in xml
        assert 'market="1"' in xml
        assert 'plType="10"' in xml
        assert 'subresult="30"' in xml
        assert 'class="Advanced"' in xml
        assert 'name="Main"' in xml
        assert "<Column-Value" in xml
        assert 'column="ProfitFactor"' in xml
        assert 'format="Decimal2"' in xml

    def test_set_advanced_rankings_multiple_conditions(self) -> None:
        """GIVEN two advanced ranking conditions
        WHEN applied
        THEN both conditions appear under the same Conditions parent.
        """
        from quantlab.cfx.models import (
            AdvancedRankingCondition,
            AdvancedRankingsConfig,
            ColumnValue,
            SetAdvancedRankingsInstruction,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetAdvancedRankingsInstruction(
            conditions=[
                AdvancedRankingCondition(
                    use=True,
                    column_values=[ColumnValue(column="PF", format="Decimal2", class_="PF")],
                ),
                AdvancedRankingCondition(
                    use=False,
                    column_values=[ColumnValue(column="Sharpe", format="Decimal2", class_="Sharpe")],
                ),
            ],
        )
        patcher.apply([instr])

        xml = archive.config.task.rankings_section.raw_xml
        # "<Condition " (with trailing space) counts only the opening elements;
        # a bare "<Condition" also matches the required <Conditions> parent.
        assert xml.count("<Condition ") == 2
        assert xml.count("<Conditions>") == 1
        assert 'use="true"' in xml
        assert 'use="false"' in xml

    def test_add_advanced_ranking_condition_appends_to_existing(self) -> None:
        """GIVEN an existing advanced rankings section with one condition
        WHEN AddAdvancedRankingConditionInstruction is applied
        THEN a second condition is appended to the same Conditions block.
        """
        from quantlab.cfx.models import (
            AdvancedRankingCondition,
            AdvancedRankingsConfig,
            ColumnValue,
            AddAdvancedRankingConditionInstruction,
            SetAdvancedRankingsInstruction,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        set_instr = SetAdvancedRankingsInstruction(
            conditions=[
                AdvancedRankingCondition(
                    use=True,
                    column_values=[ColumnValue(column="PF", format="Decimal2", class_="PF")],
                ),
            ],
        )
        patcher.apply([set_instr])

        add_instr = AddAdvancedRankingConditionInstruction(
            condition=AdvancedRankingCondition(
                use=True,
                column_values=[ColumnValue(column="Sharpe", format="Decimal2", class_="Sharpe")],
            ),
        )
        patcher.apply([add_instr])

        xml = archive.config.task.rankings_section.raw_xml
        # "<Condition " (with trailing space) counts only the opening elements;
        # a bare "<Condition" also matches the required <Conditions> parent.
        assert xml.count("<Condition ") == 2
        assert xml.count("<Conditions>") == 1
        assert 'column="PF"' in xml
        assert 'column="Sharpe"' in xml

    def test_set_advanced_rankings_empty_conditions_raises(self) -> None:
        """GIVEN a SetAdvancedRankingsInstruction with no conditions
        WHEN applied
        THEN ValidationError is raised.
        """
        from quantlab.cfx.models import SetAdvancedRankingsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetAdvancedRankingsInstruction(conditions=[])
        with pytest.raises(ValidationError, match="conditions must not be empty"):
            patcher.apply([instr])

    def test_add_advanced_ranking_condition_without_existing_section(self) -> None:
        """GIVEN no existing advanced rankings section
        WHEN AddAdvancedRankingConditionInstruction is applied
        THEN a new Rankings section is created with the condition.
        """
        from quantlab.cfx.models import (
            AddAdvancedRankingConditionInstruction,
            AdvancedRankingCondition,
            ColumnValue,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = AddAdvancedRankingConditionInstruction(
            condition=AdvancedRankingCondition(
                use=True,
                column_values=[ColumnValue(column="NetProfit", format="Decimal2", class_="NetProfit")],
            ),
        )
        patcher.apply([instr])

        section = archive.config.task.rankings_section
        assert section is not None
        xml = section.raw_xml
        assert "<Rankings>" in xml
        assert "<Conditions>" in xml
        assert "<Condition" in xml
        assert "<Column-Value" in xml

    def test_column_value_matches_real_sqx_cfx_attribute_set(self) -> None:
        """GIVEN a ColumnValue mirroring a real SQX 144/2953 CFX export
        WHEN the patcher renders it
        THEN the emitted attribute string is byte-identical to the CFX evidence,
        including defaults and attribute order.
        """
        from quantlab.cfx.models import (
            AdvancedRankingCondition,
            ColumnValue,
            SetAdvancedRankingsInstruction,
        )

        # Verbatim from sdk/quantlab/customproject/renderers.py CFX evidence.
        expected = (
            '<Column-Value column="NetProfit" columnType="0" format="Decimal2PL" '
            'resultType="OptProfileSysParamPermutation" direction="0" sampleType="127" '
            'plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" '
            'class="NetProfit" />'
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        patcher.apply(
            [
                SetAdvancedRankingsInstruction(
                    conditions=[
                        AdvancedRankingCondition(
                            use=True,
                            column_values=[
                                ColumnValue(
                                    column="NetProfit",
                                    format="Decimal2PL",
                                    result_type="OptProfileSysParamPermutation",
                                    class_="NetProfit",
                                )
                            ],
                        )
                    ]
                )
            ]
        )

        xml = archive.config.task.rankings_section.raw_xml
        assert expected in xml
        # Defaults must survive even though they were never set explicitly.
        assert 'columnType="0"' in xml
        assert 'direction="0"' in xml
        assert 'pctRatio="0"' in xml

    def test_repeated_appends_preserve_earlier_condition_attributes(self) -> None:
        """GIVEN two sequential appends with different non-default attributes
        WHEN the block is rebuilt after each append
        THEN no earlier condition loses an attribute.
        """
        from quantlab.cfx.models import (
            AddAdvancedRankingConditionInstruction,
            AdvancedRankingCondition,
            ColumnValue,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)

        patcher.apply(
            [
                AddAdvancedRankingConditionInstruction(
                    condition=AdvancedRankingCondition(
                        use=True,
                        direction="desc",
                        pct_ratio="60",
                        class_="First",
                        column_values=[
                            ColumnValue(column="ProfitFactor", format="Decimal2", class_="ProfitFactor")
                        ],
                    )
                )
            ]
        )
        first_xml = archive.config.task.rankings_section.raw_xml
        assert 'direction="desc"' in first_xml
        assert 'pctRatio="60"' in first_xml
        assert 'class="First"' in first_xml

        patcher.apply(
            [
                AddAdvancedRankingConditionInstruction(
                    condition=AdvancedRankingCondition(
                        use=False,
                        name="Second",
                        column_values=[
                            ColumnValue(column="Sharpe", format="Decimal2", class_="Sharpe")
                        ],
                    )
                )
            ]
        )

        xml = archive.config.task.rankings_section.raw_xml
        assert xml.count("<Condition ") == 2
        assert xml.count("<Conditions>") == 1
        # First condition survived the parse/rebuild round-trip intact.
        assert 'direction="desc"' in xml
        assert 'pctRatio="60"' in xml
        assert 'class="First"' in xml
        # Second condition carries its own distinct attributes.
        assert 'use="false"' in xml
        assert 'name="Second"' in xml
        assert 'column="Sharpe"' in xml

    def test_add_advanced_ranking_condition_refuses_to_clobber_simple_rankings(self) -> None:
        """GIVEN a simple <Rankings> block written by SetRankingsInstruction
        WHEN AddAdvancedRankingConditionInstruction is applied
        THEN a ValidationError is raised and the simple block is left intact.
        """
        from quantlab.cfx.models import (
            AddAdvancedRankingConditionInstruction,
            AdvancedRankingCondition,
            ColumnValue,
            SetRankingsInstruction,
        )

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        patcher.apply([SetRankingsInstruction(metrics=["ProfitFactor"], min_trades=50)])

        simple_xml = archive.config.task.rankings_section.raw_xml
        assert "<Conditions" not in simple_xml

        instr = AddAdvancedRankingConditionInstruction(
            condition=AdvancedRankingCondition(
                use=True,
                column_values=[ColumnValue(column="NetProfit", format="Decimal2", class_="NetProfit")],
            ),
        )
        with pytest.raises(ValidationError, match="no <Conditions> block to append to"):
            patcher.apply([instr])

        # No silent data loss: the simple rankings block survives untouched.
        assert archive.config.task.rankings_section.raw_xml == simple_xml


# Data Range Parts — typed model + patcher
# ═══════════════════════════════════════════════════════════════════════════


class TestDataRangePartsModel:
    """Tests for DataRangeParts: typed fields, raw_xml bridge, split semantics."""

    def test_data_range_parts_typed_fields_round_trip(self) -> None:
        """GIVEN every known typed segment set
        WHEN serialized to XML and parsed back
        THEN each field emits its element and survives the round-trip.
        """
        from quantlab.cfx.models import DataRangeParts

        parts = DataRangeParts(
            ist="2005.01.01-2010.12.31",
            isc="2011.01.01-2012.12.31",
            isv_1="2013.01.01-2013.12.31",
            isv_2="2014.01.01-2014.12.31",
            isv_3="2015.01.01-2015.12.31",
            isv_4="2016.01.01-2016.12.31",
            isv_5="2017.01.01-2017.12.31",
            isv_6="2018.01.01-2018.12.31",
            isv_7="2019.01.01-2019.12.31",
            isv_8="2020.01.01-2020.12.31",
            isv_9="2021.01.01-2021.12.31",
            isv_10="2022.01.01-2022.12.31",
            oos_1="2023.01.01-2023.12.31",
            isv_every="true",
            oos_every="true",
            validation_ratio=0.2,
            test_ratio=0.1,
            date_from="2005.01.01",
            date_to="2023.12.31",
        )
        xml = parts.to_xml()

        # Typed fields emit alongside each other, inside one <Data> structure.
        assert xml.count("<Data>") == 1
        assert '<IST value="2005.01.01-2010.12.31" />' in xml
        assert '<ISC value="2011.01.01-2012.12.31" />' in xml
        assert '<ISV1 value="2013.01.01-2013.12.31" />' in xml
        assert '<ISV10 value="2022.01.01-2022.12.31" />' in xml
        assert '<OOS1 value="2023.01.01-2023.12.31" />' in xml
        assert '<ISVEvery value="true" />' in xml
        assert '<OOSEvery value="true" />' in xml
        assert '<ValidationRatio value="0.2" />' in xml
        assert '<TestRatio value="0.1" />' in xml
        assert '<DateFrom value="2005.01.01" />' in xml
        assert '<DateTo value="2023.12.31" />' in xml

        restored = DataRangeParts.from_xml(xml)
        assert restored.ist == "2005.01.01-2010.12.31"
        assert restored.isv_1 == "2013.01.01-2013.12.31"
        assert restored.isv_10 == "2022.01.01-2022.12.31"
        assert restored.oos_1 == "2023.01.01-2023.12.31"
        assert restored.isv_every == "true"
        assert restored.oos_every == "true"
        assert restored.validation_ratio == 0.2
        assert restored.test_ratio == 0.1
        assert restored.date_from == "2005.01.01"
        assert restored.date_to == "2023.12.31"

    def test_data_range_parts_defaults_emit_no_typed_elements(self) -> None:
        """GIVEN a DataRangeParts with nothing set
        WHEN serialized and parsed back
        THEN no typed element is emitted and every field stays None.

        Companion to test_data_range_parts_typed_fields_round_trip: same code
        path, opposite branch (every field unset).
        """
        from quantlab.cfx.models import DataRangeParts

        parts = DataRangeParts()
        xml = parts.to_xml()

        assert xml == "<Data />"
        for element in ("IST", "ISC", "ISV1", "ISV10", "OOS1", "ValidationRatio", "DateFrom"):
            assert element not in xml

        restored = DataRangeParts.from_xml(xml)
        assert restored.ist is None
        assert restored.isv_1 is None
        assert restored.validation_ratio is None
        assert restored.date_from is None
        assert restored.raw_xml == ""

    def test_data_range_parts_raw_xml_only_is_verbatim(self) -> None:
        """GIVEN raw_xml holding a complete custom <Data> block and no typed fields
        WHEN serialized
        THEN the output is exactly the raw_xml content.
        """
        from quantlab.cfx.models import DataRangeParts

        custom = (
            "<Data>\n"
            '  <InSample length="3000" />\n'
            '  <OutOfSample showGraph="false" />\n'
            "</Data>"
        )
        parts = DataRangeParts(raw_xml=custom)

        assert parts.to_xml() == custom

    def test_data_range_parts_typed_and_raw_xml_coexist(self) -> None:
        """GIVEN IST/ISC plus a proprietary raw_xml sub-range
        WHEN serialized
        THEN typed elements and the raw content appear together, unduplicated.
        """
        from quantlab.cfx.models import DataRangeParts

        parts = DataRangeParts(
            ist="2005.01.01-2010.12.31",
            isc="2011.01.01-2012.12.31",
            raw_xml='  <ProprietaryRange mode="turbo" />',
        )
        xml = parts.to_xml()

        assert xml.count("<Data>") == 1
        assert xml.count("</Data>") == 1
        assert '<IST value="2005.01.01-2010.12.31" />' in xml
        assert '<ISC value="2011.01.01-2012.12.31" />' in xml
        assert '<ProprietaryRange mode="turbo" />' in xml

    def test_data_range_parts_unknown_range_lands_in_raw_xml(self) -> None:
        """GIVEN XML carrying an unrecognised <Data> child
        WHEN parsed through the bridge
        THEN the typed fields populate and the unknown element survives in raw_xml.
        """
        from quantlab.cfx.models import DataRangeParts

        parts = DataRangeParts.from_xml(
            "<Data>"
            '<IST value="2005.01.01-2010.12.31" />'
            '<FutureSQXRange version="9" />'
            "</Data>"
        )

        assert parts.ist == "2005.01.01-2010.12.31"
        assert 'FutureSQXRange' in parts.raw_xml
        assert 'version="9"' in parts.raw_xml
        # The unknown range is not silently dropped on re-serialization.
        assert 'FutureSQXRange' in parts.to_xml()

    def test_data_range_parts_split_ratios_are_not_training_ratios(self) -> None:
        """GIVEN validation ratio 0.2 and test ratio 0.1
        WHEN serialized and re-parsed
        THEN both ratios are unchanged, distinct, and never folded into a training ratio.
        """
        from quantlab.cfx.models import DataRangeParts

        parts = DataRangeParts(validation_ratio=0.2, test_ratio=0.1)
        xml = parts.to_xml()

        assert '<ValidationRatio value="0.2" />' in xml
        assert '<TestRatio value="0.1" />' in xml
        assert "TrainingRatio" not in xml
        assert "training" not in xml.lower()

        restored = DataRangeParts.from_xml(xml)
        assert restored.validation_ratio == 0.2
        assert restored.test_ratio == 0.1
        assert restored.validation_ratio != restored.test_ratio


class TestSetDataRangePartsPatcher:
    """Tests for SetDataRangePartsInstruction."""

    def test_set_data_range_parts_writes_data_range_parts_section(self) -> None:
        """GIVEN a SetDataRangePartsInstruction with typed segments
        WHEN applied
        THEN the task's data_range_parts section holds the built XML.
        """
        from quantlab.cfx.models import DataRangeParts, SetDataRangePartsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        patcher.apply(
            [
                SetDataRangePartsInstruction(
                    parts=DataRangeParts(
                        ist="2005.01.01-2010.12.31",
                        isv_1="2011.01.01-2011.12.31",
                        oos_1="2012.01.01-2012.12.31",
                        validation_ratio=0.2,
                        test_ratio=0.1,
                    )
                )
            ]
        )

        section = archive.config.task.data_range_parts
        assert section is not None
        # The typed model is stored, not a pre-rendered blob: raw_xml is the
        # lane for content that has no typed field, so to_xml() is the
        # serialization contract and the typed fields stay queryable for PR 2.
        assert section.ist == "2005.01.01-2010.12.31"
        assert section.isv_1 == "2011.01.01-2011.12.31"
        assert section.oos_1 == "2012.01.01-2012.12.31"
        assert section.raw_xml == ""

        xml = section.to_xml()
        assert xml.startswith("<Data>")
        assert '<IST value="2005.01.01-2010.12.31" />' in xml
        assert '<ISV1 value="2011.01.01-2011.12.31" />' in xml
        assert '<OOS1 value="2012.01.01-2012.12.31" />' in xml
        assert '<ValidationRatio value="0.2" />' in xml
        assert '<TestRatio value="0.1" />' in xml

    def test_set_data_range_parts_raw_xml_only_preserved(self) -> None:
        """GIVEN an instruction carrying only raw_xml
        WHEN applied
        THEN the custom <Data> block reaches the section unchanged.
        """
        from quantlab.cfx.models import DataRangeParts, SetDataRangePartsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        custom = '<Data><OutOfSample showGraph="false" /></Data>'
        patcher.apply(
            [SetDataRangePartsInstruction(parts=DataRangeParts(raw_xml=custom))]
        )

        section = archive.config.task.data_range_parts
        assert section is not None
        assert section.raw_xml == custom
        assert section.to_xml() == custom

    def test_set_data_range_parts_rejects_ratio_outside_unit_interval(self) -> None:
        """GIVEN a validation ratio outside (0, 1)
        WHEN applied
        THEN ValidationError is raised and no mutation is applied.
        """
        from quantlab.cfx.models import DataRangeParts, SetDataRangePartsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetDataRangePartsInstruction(
            parts=DataRangeParts(validation_ratio=1.5, test_ratio=0.1)
        )

        with pytest.raises(ValidationError, match="validation_ratio must be in"):
            patcher.apply([instr])

        assert archive.config.task.data_range_parts is None

    def test_set_data_range_parts_rejects_zero_ratio(self) -> None:
        """GIVEN a test ratio of 0.0
        WHEN applied
        THEN ValidationError is raised, because a zero split is not a real split.
        """
        from quantlab.cfx.models import DataRangeParts, SetDataRangePartsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        instr = SetDataRangePartsInstruction(
            parts=DataRangeParts(validation_ratio=0.2, test_ratio=0.0)
        )

        with pytest.raises(ValidationError, match="test_ratio must be in"):
            patcher.apply([instr])

        assert archive.config.task.data_range_parts is None

    def test_set_data_range_parts_does_not_clobber_simple_data_section(self) -> None:
        """GIVEN the flat <Data> SettingsSection written by set_date_range
        WHEN SetDataRangePartsInstruction is applied
        THEN the simple Data section survives untouched beside the new typed one.
        """
        from quantlab.cfx.models import DataRangeParts, SetDataRangePartsInstruction

        archive = _make_archive()
        patcher = CfxPatcher(archive)
        patcher.apply([SetDateRangeInstruction(start="2005.01.01", end="2023.12.31")])
        simple_data = archive.config.task.data
        assert simple_data is not None
        assert simple_data.settings.get("FromDate@value") == "2005.01.01"

        patcher.apply(
            [SetDataRangePartsInstruction(parts=DataRangeParts(ist="2005.01.01-2010.12.31"))]
        )

        assert archive.config.task.data is simple_data
        assert archive.config.task.data.settings.get("FromDate@value") == "2005.01.01"
        assert archive.config.task.data_range_parts is not None
        assert (
            '<IST value="2005.01.01-2010.12.31" />'
            in archive.config.task.data_range_parts.to_xml()
        )
