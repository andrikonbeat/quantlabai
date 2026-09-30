"""Slice A: typed ``RiskConfig`` ⇄ CFX ``risk_money_mgmt`` mapping.

Spec requirement "Typed RiskConfig → CFX risk_money_mgmt Mapping (Issue 2)":

- ``RiskConfigMapper.to_cfx`` serialises a typed ``RiskConfig`` into a
  ``SettingsSection`` using the known SQX ``RiskMoneyManagement`` keys.
- ``RiskConfigMapper.from_cfx`` is its inverse and round-trips every field.
- Values are validated before serialisation; invalid ranges raise
  ``RiskConfigError`` and no partial section is produced.
- An unsupported CFX schema version raises ``VersionError`` before a
  ``RiskConfig`` is built.

Strict TDD: written first — RED until Slice A lands.
"""

from __future__ import annotations

import pytest

from quantlab.cfx.models import BuildTask, CfxConfig, SettingsSection
from quantlab.cfx.reader import _MAX_VERSION
from quantlab.cfx.risk_mapper import RiskConfig, RiskConfigError, RiskConfigMapper

MAPPER = RiskConfigMapper()


def _risk_config(**overrides: object) -> RiskConfig:
    base: dict = {
        "max_portfolio_drawdown": 0.15,
        "max_strategy_correlation": 0.7,
        "max_single_strategy_weight": 0.4,
        "kelly_fraction_cap": 0.25,
        "var_confidence": 0.95,
    }
    base.update(overrides)
    return RiskConfig(**base)


def _unchecked_risk_config(**overrides: object) -> RiskConfig:
    """Build a ``RiskConfig`` bypassing pydantic field validation.

    The mapper must defend itself against values that never passed the
    model's own constraints (config loaded via ``model_construct``, a
    differently-bounded model, or hand-edited data).
    """
    base: dict = {
        "max_portfolio_drawdown": 0.15,
        "max_strategy_correlation": 0.7,
        "max_single_strategy_weight": 0.4,
        "kelly_fraction_cap": 0.25,
        "var_confidence": 0.95,
    }
    base.update(overrides)
    return RiskConfig.model_construct(**base)


class TestToCfx:
    """``to_cfx`` emits the known SQX ``RiskMoneyManagement`` keys."""

    def test_section_name_is_risk_money_management(self) -> None:
        section = MAPPER.to_cfx(_risk_config())

        assert isinstance(section, SettingsSection)
        assert section.name == "RiskMoneyManagement"

    def test_every_risk_field_is_mapped_to_a_known_key(self) -> None:
        section = MAPPER.to_cfx(_risk_config())

        assert set(section.settings) == set(RiskConfigMapper.CFX_KEYS.values())

    def test_values_are_emitted_verbatim_as_ratios(self) -> None:
        section = MAPPER.to_cfx(_risk_config(max_portfolio_drawdown=0.15))

        assert section.settings[RiskConfigMapper.CFX_KEYS["max_portfolio_drawdown"]] == "0.15"
        assert section.settings[RiskConfigMapper.CFX_KEYS["kelly_fraction_cap"]] == "0.25"

    def test_default_config_maps_its_defaults(self) -> None:
        section = MAPPER.to_cfx(RiskConfig())

        assert section.settings[RiskConfigMapper.CFX_KEYS["max_portfolio_drawdown"]] == "0.2"
        assert section.settings[RiskConfigMapper.CFX_KEYS["var_confidence"]] == "0.95"


class TestRoundTrip:
    """CFX → RiskConfig → CFX preserves every non-conflicting field."""

    def test_round_trip_preserves_all_fields(self) -> None:
        original = _risk_config()

        restored = MAPPER.from_cfx(MAPPER.to_cfx(original))

        assert restored == original

    def test_round_trip_through_a_build_task_is_stable(self) -> None:
        original = _risk_config()
        task = BuildTask(risk_money_mgmt=MAPPER.to_cfx(original))

        first = MAPPER.to_cfx(MAPPER.from_cfx(task))
        second = MAPPER.to_cfx(MAPPER.from_cfx(BuildTask(risk_money_mgmt=first)))

        assert first == second
        assert MAPPER.from_cfx(first) == original

    def test_from_cfx_accepts_a_whole_cfx_config(self) -> None:
        original = _risk_config()
        config = CfxConfig(
            task=BuildTask(risk_money_mgmt=MAPPER.to_cfx(original)),
            schema_version="144.2953",
        )

        assert MAPPER.from_cfx(config) == original

    def test_from_cfx_accepts_a_settings_section(self) -> None:
        original = _risk_config()

        assert MAPPER.from_cfx(MAPPER.to_cfx(original)) == original


class TestVersionSafety:
    """An unsupported schema version is rejected before deserialisation."""

    def test_unsupported_schema_version_raises(self) -> None:
        config = CfxConfig(
            task=BuildTask(risk_money_mgmt=MAPPER.to_cfx(_risk_config())),
            schema_version=_MAX_VERSION,
        )
        config.schema_version = "1.0"

        with pytest.raises(Exception) as exc_info:
            MAPPER.from_cfx(config)

        assert type(exc_info.value).__name__ == "VersionError"


class TestValidation:
    """Invalid ranges fail closed before serialisation."""

    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_portfolio_drawdown", 2.0),
            ("max_strategy_correlation", 1.5),
            ("max_single_strategy_weight", 0.0),
            ("kelly_fraction_cap", -0.1),
            ("var_confidence", 1.0),
        ],
    )
    def test_out_of_range_value_raises(self, field: str, value: object) -> None:
        """Range violations are reported as RiskConfigError, not ValidationError."""
        invalid = _unchecked_risk_config(**{field: value})

        with pytest.raises(RiskConfigError):
            MAPPER.to_cfx(invalid)

    def test_non_numeric_value_raises(self) -> None:
        invalid = _unchecked_risk_config(max_portfolio_drawdown="not-a-number")

        with pytest.raises(RiskConfigError):
            MAPPER.to_cfx(invalid)

    def test_missing_risk_section_raises(self) -> None:
        with pytest.raises(RiskConfigError):
            MAPPER.from_cfx(BuildTask())

    def test_unparseable_cfx_value_raises(self) -> None:
        section = MAPPER.to_cfx(_risk_config())
        section.settings[RiskConfigMapper.CFX_KEYS["var_confidence"]] = "not-a-number"

        with pytest.raises(RiskConfigError):
            MAPPER.from_cfx(section)
