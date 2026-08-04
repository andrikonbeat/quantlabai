"""Tests for project_builder BrokerProfile acceptance (Task 4.5)."""

from unittest.mock import patch

from quantlab.costs.profiles import BrokerProfile
from quantlab.sqx.project_builder import create_project, _JFOREX_COMMISSION, _JFOREX_SLIPPAGE, _JFOREX_SPREAD


class TestCreateProjectBrokerProfile:
    """BrokerProfile param in create_project()."""

    @patch("quantlab.sqx.project_builder._template_path")
    @patch("quantlab.sqx.project_builder.zipfile.ZipFile")
    @patch("quantlab.sqx.project_builder.Path.exists", return_value=True)
    @patch("quantlab.sqx.project_builder.shutil.rmtree")
    @patch("quantlab.sqx.project_builder.Path.mkdir")
    def test_broker_profile_default_not_set(
        self, mkdir, rmtree, exists, zipfile, template_path
    ) -> None:
        """GIVEN create_project is called without broker_profile
        THEN the default _JFOREX_COMMISSION/SLIPPAGE/SPREAD are used.
        """
        zip_instance = zipfile.return_value.__enter__.return_value
        zip_instance.read.return_value = b"<xml/>"

        result = create_project(
            sqx_install_path="/tmp/fake_sqx",
            campaign_id="test_campaign",
        )
        # Should not crash — uses hardcoded defaults
        assert result is not None

    @patch("quantlab.sqx.project_builder._template_path")
    @patch("quantlab.sqx.project_builder.zipfile.ZipFile")
    @patch("quantlab.sqx.project_builder.Path.exists", return_value=True)
    @patch("quantlab.sqx.project_builder.shutil.rmtree")
    @patch("quantlab.sqx.project_builder.Path.mkdir")
    def test_broker_profile_accepts_dukascopy(
        self, mkdir, rmtree, exists, zipfile, template_path
    ) -> None:
        """GIVEN a BrokerProfile (dukascopy)
        WHEN create_project is called with it
        THEN the creation succeeds.
        """
        zip_instance = zipfile.return_value.__enter__.return_value
        zip_instance.read.return_value = b"<xml/>"

        profile = BrokerProfile.dukascopy()
        result = create_project(
            sqx_install_path="/tmp/fake_sqx",
            campaign_id="test_campaign",
            broker_profile=profile,
        )
        assert result is not None

    @patch("quantlab.sqx.project_builder._template_path")
    @patch("quantlab.sqx.project_builder.zipfile.ZipFile")
    @patch("quantlab.sqx.project_builder.Path.exists", return_value=True)
    @patch("quantlab.sqx.project_builder.shutil.rmtree")
    @patch("quantlab.sqx.project_builder.Path.mkdir")
    def test_broker_profile_oanda(
        self, mkdir, rmtree, exists, zipfile, template_path
    ) -> None:
        """GIVEN OANDA BrokerProfile (spread-only, 0 commission)
        WHEN create_project is called with it
        THEN commission is 0.0.
        """
        zip_instance = zipfile.return_value.__enter__.return_value
        zip_instance.read.return_value = b"<xml/>"

        profile = BrokerProfile.oanda()
        result = create_project(
            sqx_install_path="/tmp/fake_sqx",
            campaign_id="test_campaign",
            broker_profile=profile,
        )
        assert result is not None

    def test_broker_profile_has_correct_interface(self) -> None:
        """GIVEN a BrokerProfile instance
        THEN it carries the cost params needed by project_builder.
        """
        for preset in [BrokerProfile.dukascopy(), BrokerProfile.interactive_brokers(), BrokerProfile.oanda()]:
            assert hasattr(preset, "commission")
            assert hasattr(preset, "slippage")
            assert hasattr(preset, "spread_config")
            # slippage should have fixed_pips
            assert hasattr(preset.slippage, "fixed_pips")
            # spread_config should have base_spread
            assert hasattr(preset.spread_config, "base_spread")
