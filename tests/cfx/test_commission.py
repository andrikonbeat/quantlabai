"""Tests for CFX commission/spread models and domain methods."""

import pytest

from quantlab.cfx import BuildTask, SettingsSection
from quantlab.cfx.models import CfxConfig, CfxArchive


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


class TestDomCommissionMethods:
    """Task 4.2: set_commission_settings() and set_spread_settings()."""

    def test_set_commission_settings_creates_commission_costs_section(self) -> None:
        """GIVEN a CfxArchive with no commission_costs
        WHEN set_commission_settings() is called
        THEN commission_costs is created with the given values.
        """
        from quantlab.cfx.dom import set_commission_settings

        archive = _make_archive()
        result = set_commission_settings(
            archive,
            commission_type="fixed",
            value=3.5,
            currency="USD",
        )
        assert result is archive
        assert archive.config.task.commission_costs is not None
        assert archive.config.task.commission_costs.name == "CommissionCosts"
        assert archive.config.task.commission_costs.settings["CommissionType@value"] == "fixed"
        assert archive.config.task.commission_costs.settings["CommissionValue@value"] == "3.5"
        assert archive.config.task.commission_costs.settings["CommissionCurrency@value"] == "USD"

    def test_set_commission_settings_tiered(self) -> None:
        """GIVEN tiered commission params
        WHEN set_commission_settings is called
        THEN tier data is stored.
        """
        from quantlab.cfx.dom import set_commission_settings

        archive = _make_archive()
        set_commission_settings(
            archive,
            commission_type="tiered",
            value=0.0,
            currency="USD",
            tiers=[(0, 100000, 3.0), (100000, 1000000000, 2.0)],
        )
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["CommissionType@value"] == "tiered"
        assert cc.settings["CommissionTiers@value"] == "0-100000:3.0,100000-1000000000:2.0"

    def test_set_commission_settings_overwrites_existing(self) -> None:
        """GIVEN an archive with existing commission_costs
        WHEN set_commission_settings is called again
        THEN the settings are overwritten.
        """
        from quantlab.cfx.dom import set_commission_settings

        archive = _make_archive()
        set_commission_settings(archive, "fixed", 3.5, "USD")
        set_commission_settings(archive, "percent", 0.1, "USD")
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["CommissionType@value"] == "percent"

    def test_set_spread_settings_creates_commission_costs_section(self) -> None:
        """GIVEN a CfxArchive
        WHEN set_spread_settings() is called
        THEN spread values are stored on commission_costs.
        """
        from quantlab.cfx.dom import set_spread_settings

        archive = _make_archive()
        result = set_spread_settings(archive, base_spread=1.2, slippage_pips=0.5)
        assert result is archive
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["BaseSpread@value"] == "1.2"
        assert cc.settings["SlippagePips@value"] == "0.5"

    def test_set_spread_settings_with_sessions(self) -> None:
        """GIVEN session multipliers
        WHEN set_spread_settings is called
        THEN session data is stored.
        """
        from quantlab.cfx.dom import set_spread_settings

        archive = _make_archive()
        set_spread_settings(
            archive,
            base_spread=0.8,
            slippage_pips=0.3,
            session_multipliers={"London": 1.0, "NewYork": 1.2, "Asia": 1.5},
        )
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["SessionLondon@multiplier"] == "1.0"
        assert cc.settings["SessionNewYork@multiplier"] == "1.2"
        assert cc.settings["SessionAsia@multiplier"] == "1.5"

    def test_set_spread_settings_overwrites_existing(self) -> None:
        """GIVEN existing spread settings
        WHEN set_spread_settings is called again
        THEN previous settings are replaced.
        """
        from quantlab.cfx.dom import set_spread_settings

        archive = _make_archive()
        set_spread_settings(archive, base_spread=1.5, slippage_pips=1.0)
        set_spread_settings(archive, base_spread=0.6, slippage_pips=0.3)
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["BaseSpread@value"] == "0.6"
        assert cc.settings["SlippagePips@value"] == "0.3"


class TestDomCommissionMethodsEdgeCases:
    """Edge cases for dom commission/spread methods."""

    def test_set_commission_no_tiers_omits_tier_field(self) -> None:
        """GIVEN no tiers argument
        WHEN set_commission_settings is called
        THEN no CommissionTiers key is set.
        """
        from quantlab.cfx.dom import set_commission_settings

        archive = _make_archive()
        set_commission_settings(archive, "fixed", 3.5, "USD")
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert "CommissionTiers@value" not in cc.settings

    def test_set_spread_no_session_multipliers(self) -> None:
        """GIVEN no session_multipliers
        WHEN set_spread_settings is called
        THEN no Session keys are set.
        """
        from quantlab.cfx.dom import set_spread_settings

        archive = _make_archive()
        set_spread_settings(archive, base_spread=1.0, slippage_pips=0.5)
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert not any(k.startswith("Session") for k in cc.settings)

    def test_set_commission_zero_value(self) -> None:
        """GIVEN a zero commission value
        WHEN set_commission_settings is called
        THEN the value is stored as '0.0'.
        """
        from quantlab.cfx.dom import set_commission_settings

        archive = _make_archive()
        set_commission_settings(archive, "fixed", 0.0, "USD")
        cc = archive.config.task.commission_costs
        assert cc is not None
        assert cc.settings["CommissionValue@value"] == "0.0"


class TestCommissionCosts:
    """Task 4.1: CommissionCosts optional SettingsSection on BuildTask."""

    def test_commission_costs_is_optional_and_none_by_default(self) -> None:
        """GIVEN a new BuildTask
        WHEN no commission_costs is set
        THEN commission_costs is None by default.
        """
        task = BuildTask()
        assert task.commission_costs is None

    def test_commission_costs_accepts_settings_section(self) -> None:
        """GIVEN a BuildTask
        WHEN commission_costs is set to a SettingsSection
        THEN it stores the section with the right name and settings.
        """
        task = BuildTask(
            commission_costs=SettingsSection(
                name="CommissionCosts",
                settings={
                    "CommissionType@value": "fixed",
                    "CommissionValue@value": "3.5",
                    "CommissionCurrency@value": "USD",
                },
            )
        )
        assert task.commission_costs is not None
        assert task.commission_costs.name == "CommissionCosts"
        assert task.commission_costs.settings["CommissionType@value"] == "fixed"
        assert task.commission_costs.settings["CommissionValue@value"] == "3.5"
        assert task.commission_costs.settings["CommissionCurrency@value"] == "USD"

    def test_commission_costs_empty_settings(self) -> None:
        """GIVEN a BuildTask with an empty CommissionCosts section
        WHEN accessed
        THEN it stores the empty section correctly.
        """
        task = BuildTask(
            commission_costs=SettingsSection(name="CommissionCosts", settings={})
        )
        assert task.commission_costs is not None
        assert task.commission_costs.settings == {}

    def test_commission_costs_roundtrips_through_archive(self) -> None:
        """GIVEN a CfxArchive with commission_costs set
        WHEN serialized and deserialized
        THEN commission_costs is preserved.
        """
        task = BuildTask(
            commission_costs=SettingsSection(
                name="CommissionCosts",
                settings={
                    "CommissionType@value": "tiered",
                    "CommissionTiers@value": "0-100000:3.0,100000+:2.0",
                },
            )
        )
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)

        retrieved = archive.config.task
        assert retrieved.commission_costs is not None
        assert retrieved.commission_costs.settings["CommissionType@value"] == "tiered"
