"""Tests for RetesterConfig broker_profile/cost_config (Task 4.6)."""

from quantlab.phase4.retester import RetesterConfig


class TestRetesterConfigBrokerCost:
    """broker_profile and cost_config params on RetesterConfig."""

    def test_default_is_none(self) -> None:
        """GIVEN no broker_profile or cost_config
        WHEN RetesterConfig is created
        THEN both are None by default.
        """
        config = RetesterConfig(
            strategy_id="test",
            databanks=["EURUSD_H1"],
        )
        assert config.broker_profile is None
        assert config.cost_config is None

    def test_accepts_explicit_none(self) -> None:
        """GIVEN explicit broker_profile=None and cost_config=None
        WHEN RetesterConfig is created
        THEN it stores them as None.
        """
        config = RetesterConfig(
            strategy_id="test",
            databanks=["EURUSD_H1"],
            broker_profile=None,
            cost_config=None,
        )
        assert config.broker_profile is None
        assert config.cost_config is None

    def test_accepts_broker_profile_dict(self) -> None:
        """GIVEN a broker_profile dict
        WHEN RetesterConfig is created
        THEN it stores the profile.
        """
        config = RetesterConfig(
            strategy_id="test",
            databanks=["EURUSD_H1"],
            broker_profile={"name": "dukascopy", "commission": 3.5, "spread": 0.8},
        )
        assert config.broker_profile == {"name": "dukascopy", "commission": 3.5, "spread": 0.8}

    def test_accepts_cost_config_dict(self) -> None:
        """GIVEN a cost_config dict
        WHEN RetesterConfig is created
        THEN it stores the config.
        """
        config = RetesterConfig(
            strategy_id="test",
            databanks=["EURUSD_H1"],
            cost_config={"engine": "mock", "collector": "mock"},
        )
        assert config.cost_config == {"engine": "mock", "collector": "mock"}

    def test_both_provided(self) -> None:
        """GIVEN both broker_profile and cost_config
        WHEN RetesterConfig is created
        THEN both are stored.
        """
        config = RetesterConfig(
            strategy_id="test",
            databanks=["EURUSD_H1"],
            broker_profile={"name": "ib"},
            cost_config={"spread_pips": 0.6},
        )
        assert config.broker_profile == {"name": "ib"}
        assert config.cost_config == {"spread_pips": 0.6}
