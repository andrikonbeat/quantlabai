"""Tests for the DSL YAML parser."""

from pathlib import Path

import pytest
import yaml

from quantlab.dsl.models import ResearchConfig
from quantlab.dsl.parser import parse_yaml, parse_yaml_string, serialize, validate
from quantlab.tools.exceptions import ParseError, ValidationError


class TestParseYamlString:
    """Tests for parse_yaml_string() — in-memory parsing."""

    SAMPLE = """\
campaign: "Test"
market: EURUSD
timeframe: H1
strategies:
  - name: StratA
    direction: LONG
"""

    def test_parses_valid_yaml(self) -> None:
        config = parse_yaml_string(self.SAMPLE)
        assert isinstance(config, ResearchConfig)
        assert config.campaign == "Test"
        assert config.market.value == "EURUSD"

    def test_invalid_yaml_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_yaml_string("{invalid: yaml: [broken}")

    def test_non_dict_root_raises_parse_error(self) -> None:
        with pytest.raises(ParseError, match="mapping"):
            parse_yaml_string("- just a list")

    def test_unknown_market_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="Unknown market"):
            parse_yaml_string(
                "campaign: Bad\nmarket: INVALID\nmarket: INVALID\ntimeframe: H1\n"
            )

    def test_empty_string_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_yaml_string("")

    def test_minimal_config(self) -> None:
        config = parse_yaml_string(
            "campaign: Mini\nmarket: BTCUSD\ntimeframe: D1\n"
        )
        assert config.campaign == "Mini"
        assert config.market.value == "BTCUSD"


class TestParseYamlFile:
    """Tests for parse_yaml() — filesystem parsing."""

    def test_file_not_found_raises_parse_error(self) -> None:
        with pytest.raises(ParseError, match="not found"):
            parse_yaml("/nonexistent/path/campaign.yaml")

    def test_parses_valid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "campaign.yaml"
        path.write_text("campaign: FileTest\nmarket: EURUSD\ntimeframe: H1\n")
        config = parse_yaml(path)
        assert config.campaign == "FileTest"


class TestSerialize:
    """Tests for serialize() — round-trip YAML."""

    def test_round_trip(self) -> None:
        original = ResearchConfig(
            campaign="RoundTrip",
            market="EURUSD",
            timeframe="H1",
        )
        yaml_str = serialize(original)
        restored = parse_yaml_string(yaml_str)
        assert restored.campaign == original.campaign
        assert restored.market == original.market
        assert restored.timeframe == original.timeframe

    def test_serialize_with_building_blocks(self) -> None:
        config = ResearchConfig(
            campaign="WithBlocks",
            market="EURUSD",
            timeframe="H1",
        )
        yaml_str = serialize(config)
        reparsed = yaml.safe_load(yaml_str)
        assert reparsed["campaign"] == "WithBlocks"
        assert reparsed["market"] == "EURUSD"


class TestValidate:
    """Tests for validate() — re-validation."""

    def test_valid_config_passes(self) -> None:
        config = ResearchConfig(
            campaign="Valid",
            market="EURUSD",
            timeframe="H1",
        )
        result = validate(config)
        assert result is config

    def test_invalid_config_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResearchConfig(
                campaign="Dups",
                market="EURUSD",
                timeframe="H1",
                strategies=[
                    {"name": "S1", "direction": "LONG"},
                    {"name": "S1", "direction": "SHORT"},
                ],
            )
