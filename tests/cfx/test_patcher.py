"""Tests for CfxPatcher — validate-then-apply semantics and domain methods."""

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