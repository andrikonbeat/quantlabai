"""Integration tests: DSL parsing with costs section, valid/invalid broker validation.

Covers spec scenarios from:
- openspec/specs/cost-pipeline-integration/spec.md (DSL Costs Section)
- openspec/changes/broker-cost-engine/specs/research-dsl/spec.md (delta)
"""

import pytest

from quantlab.dsl.parser import parse_yaml_string
from quantlab.tools.exceptions import ValidationError as QuantLabValError


class TestParseYamlWithCosts:
    """DSL parsing with costs section — valid broker, invalid broker, optional absence."""

    def test_valid_broker_dukascopy(self):
        """GIVEN costs: {broker: dukascopy} WHEN parsed THEN costs is populated."""
        yaml = """
campaign: test-costs
market: EURUSD
timeframe: H1
costs:
  broker: dukascopy
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.broker == "dukascopy"

    def test_valid_broker_ib(self):
        """GIVEN costs: {broker: ib} WHEN parsed THEN costs.broker == 'ib'."""
        yaml = """
campaign: test-ib
market: EURUSD
timeframe: H1
costs:
  broker: ib
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.broker == "ib"

    def test_valid_broker_oanda(self):
        """GIVEN costs: {broker: oanda} WHEN parsed THEN costs.broker == 'oanda'."""
        yaml = """
campaign: test-oanda
market: GBPUSD
timeframe: H4
costs:
  broker: oanda
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.broker == "oanda"

    def test_no_costs_section_optional(self):
        """GIVEN YAML without costs WHEN parsed THEN costs is None (backward compatible)."""
        yaml = """
campaign: test-no-costs
market: EURUSD
timeframe: D1
"""
        config = parse_yaml_string(yaml)
        assert config.costs is None

    def test_invalid_broker_raises_error(self):
        """GIVEN costs: {broker: unknown_broker} WHEN parsed THEN ValidationError."""
        yaml = """
campaign: test-invalid
market: EURUSD
timeframe: H1
costs:
  broker: unknown_broker
"""
        with pytest.raises(QuantLabValError):
            parse_yaml_string(yaml)

    def test_costs_with_commission_override(self):
        """GIVEN costs with commission_override WHEN parsed THEN overrides present."""
        yaml = """
campaign: test-override
market: EURUSD
timeframe: H1
costs:
  broker: dukascopy
  commission_override:
    type: fixed
    value: 10.0
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.broker == "dukascopy"
        assert config.costs.commission_override is not None
        assert config.costs.commission_override.value == 10.0

    def test_costs_with_slippage_mode(self):
        """GIVEN costs with slippage_mode WHEN parsed THEN mode is set."""
        yaml = """
campaign: test-slippage
market: EURUSD
timeframe: H1
costs:
  broker: oanda
  slippage_mode: session
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.slippage_mode == "session"

    def test_costs_with_spread_config(self):
        """GIVEN costs with spread_config WHEN parsed THEN spread is set."""
        yaml = """
campaign: test-spread
market: EURUSD
timeframe: H1
costs:
  broker: ib
  spread_config:
    base_spread: 0.5
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.spread_config is not None
        assert config.costs.spread_config.base_spread == 0.5


class TestAllBrokerProfilesValid:
    """Every known broker profile is accepted by the parser."""

    def test_all_known_brokers(self):
        """ALL known brokers: dukascopy, ib, oanda → accepted."""
        for broker in ("dukascopy", "ib", "oanda"):
            yaml = f"""
campaign: test-{broker}
market: EURUSD
timeframe: H1
costs:
  broker: {broker}
"""
            config = parse_yaml_string(yaml)
            assert config.costs is not None
            assert config.costs.broker == broker


class TestCostsEdgeCases:
    """Edge cases for costs section parsing."""

    def test_empty_costs_block_raises_error(self):
        """GIVEN costs: {} WHEN parsed THEN ValidationError (broker is required)."""
        yaml = """
campaign: test-empty
market: EURUSD
timeframe: H1
costs: {}
"""
        with pytest.raises(QuantLabValError):
            parse_yaml_string(yaml)

    def test_broker_name_is_case_sensitive(self):
        """GIVEN costs: {broker: Dukascopy} (capitalised) WHEN parsed THEN ValidationError."""
        yaml = """
campaign: test-case
market: EURUSD
timeframe: H1
costs:
  broker: Dukascopy
"""
        with pytest.raises(QuantLabValError):
            parse_yaml_string(yaml)

    def test_unknown_broker_error_message_contains_known_brokers(self):
        """Error message for unknown broker lists known brokers."""
        yaml = """
campaign: test-msg
market: EURUSD
timeframe: H1
costs:
  broker: nonexistent_broker
"""
        with pytest.raises(QuantLabValError, match="dukascopy|ib|oanda"):
            parse_yaml_string(yaml)

    def test_existing_validators_still_work_with_costs(self):
        """Duplicate strategy names still detected with costs section present."""
        yaml = """
campaign: test-dup
market: EURUSD
timeframe: H1
costs:
  broker: dukascopy
strategies:
  - name: same_name
    direction: LONG
  - name: same_name
    direction: SHORT
"""
        with pytest.raises(QuantLabValError, match="Duplicate strategy"):
            parse_yaml_string(yaml)

    def test_unknown_market_still_rejected_with_costs(self):
        """Unknown market still rejected when costs section is present."""
        yaml = """
campaign: test-market
market: UNKNOWN
timeframe: H1
costs:
  broker: ib
"""
        with pytest.raises(QuantLabValError, match="Unknown market"):
            parse_yaml_string(yaml)

    def test_costs_broker_only_minimal(self):
        """Minimal costs section with only broker works."""
        yaml = """
campaign: test-minimal
market: EURUSD
timeframe: H1
costs:
  broker: oanda
"""
        config = parse_yaml_string(yaml)
        assert config.costs is not None
        assert config.costs.broker == "oanda"
        assert config.costs.commission_override is None
        assert config.costs.slippage_mode == "static"  # default
        assert config.costs.spread_config is None  # default


class TestFullCampaignWithCosts:
    """Full campaign definition with costs section — spec scenario."""

    def test_full_campaign_parses_with_costs(self):
        """Complete campaign with market, timeframe, building blocks, criteria, and costs."""
        yaml = """
campaign: full-campaign
market: EURUSD
timeframe: H1
building_blocks:
  - name: rsi_entry
    indicator:
      name: RSI
      params: {period: 14}
    entry:
      description: RSI oversold
      conditions:
        - "rsi < 30"
strategies:
  - name: rsi_reversal
    direction: LONG
    building_blocks:
      - rsi_entry
criteria:
  - metric: profit_factor
    operator: ">"
    value: 1.5
costs:
  broker: dukascopy
  slippage_mode: static
"""
        config = parse_yaml_string(yaml)
        assert config.campaign == "full-campaign"
        assert config.costs is not None
        assert config.costs.broker == "dukascopy"
        assert config.costs.slippage_mode == "static"
        assert len(config.building_blocks) == 1
        assert len(config.strategies) == 1
        assert len(config.criteria) == 1
