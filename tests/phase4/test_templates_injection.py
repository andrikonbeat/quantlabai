"""Tests for commission/spread injection in templates (Task 4.7).

Uses ``CfxTemplateBuilder._build_retester_task`` to verify model-level
injection without serialization round-trips.
"""

from quantlab.cfx.models import BuildTask, SettingsSection
from quantlab.phase4.templates import CfxTemplateBuilder


class TestRetesterCfxInjection:
    """Commission/spread injection in build_retester_cfx."""

    def test_no_profile_no_injection(self) -> None:
        """GIVEN no broker_profile
        WHEN _build_retester_task is called
        THEN commission_costs is None.
        """
        task = CfxTemplateBuilder._build_retester_task(
            strategy_id="test_strat",
            databanks=["EURUSD_H1"],
        )
        assert task.commission_costs is None

    def test_with_profile_sets_commission_costs(self) -> None:
        """GIVEN a broker_profile dict
        WHEN _build_retester_task is called
        THEN commission_costs SettingsSection is populated.
        """
        profile = {
            "name": "dukascopy",
            "commission": 3.5,
            "spread": 0.8,
            "slippage": 0.5,
        }
        task = CfxTemplateBuilder._build_retester_task(
            strategy_id="test_strat",
            databanks=["EURUSD_H1"],
            broker_profile=profile,
        )
        assert task.commission_costs is not None
        assert task.commission_costs.name == "CommissionCosts"
        assert task.commission_costs.settings["BaseSpread@value"] == "0.8"
        assert task.commission_costs.settings["SlippagePips@value"] == "0.5"
        assert task.commission_costs.settings["CommissionValue@value"] == "3.5"
        assert task.commission_costs.settings["CommissionCurrency@value"] == "USD"

    def test_with_profile_updates_data_section(self) -> None:
        """GIVEN a broker_profile with spread
        WHEN _build_retester_task is called
        THEN the Data section includes BaseSpread/SlippagePips.
        """
        profile = {"name": "ib", "commission": 2.0, "spread": 0.6, "slippage": 0.3}
        task = CfxTemplateBuilder._build_retester_task(
            strategy_id="test_rt",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
            broker_profile=profile,
        )
        assert task.data is not None
        assert task.data.settings["BaseSpread@value"] == "0.6"
        assert task.data.settings["SlippagePips@value"] == "0.3"

    def test_zero_commission_is_handled(self) -> None:
        """GIVEN a profile with zero commission (OANDA-like)
        WHEN _build_retester_task is called
        THEN commission is stored as 0.0.
        """
        profile = {"name": "oanda", "commission": 0.0, "spread": 1.2, "slippage": 0.4}
        task = CfxTemplateBuilder._build_retester_task(
            strategy_id="test_oanda",
            databanks=["EURUSD_H1"],
            broker_profile=profile,
        )
        assert task.commission_costs is not None
        assert task.commission_costs.settings["CommissionValue@value"] == "0.0"

    def test_build_retester_cfx_with_profile_returns_valid_archive(self) -> None:
        """GIVEN a broker_profile
        WHEN build_retester_cfx is called
        THEN the returned bytes form a valid CFX (ZIP) archive.
        """
        profile = {"name": "oanda", "commission": 0.0, "spread": 1.2, "slippage": 0.4}
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="test_retest",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
            mc_runs=50,
            mc_percentile=90,
            broker_profile=profile,
        )
        assert cfx_bytes[:2] == b"PK"
        assert len(cfx_bytes) > 100
